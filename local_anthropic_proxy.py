import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

HOST = "127.0.0.1"
PORT = 8787
TARGET_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TOOL_ITERATIONS = 15
COMPACT_THRESHOLD = 50   # rows above this → send summary to LLM, browser fetches full data via /query
BROWSER_ROW_LIMIT = int(os.getenv("BROWSER_ROW_LIMIT", "2000000"))  # cap for /query (browser renders, not LLM)

# ── PostgreSQL connection (override via env vars) ──────────────────────────────
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

# DB_NAME = os.getenv("DB_NAME", "AdventureWorks")
DB_NAME = os.getenv("DB_NAME", "AdventureWorks2019")

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "458213")
DB_ROW_LIMIT = int(os.getenv("DB_ROW_LIMIT", "500"))

# ── Tool definition (description is built dynamically per-request) ─────────────
QUERY_DATABASE_TOOL_SCHEMA = {
    "name": "query_database",
    "input_schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "A read-only SQL SELECT statement. No INSERT, UPDATE, DELETE, DROP, or DDL."
            },
            "description": {
                "type": "string",
                "description": "One-line description of what this query retrieves, shown to the user."
            }
        },
        "required": ["sql"]
    }
}


def build_query_tool(db_name: str) -> dict:
    tool = dict(QUERY_DATABASE_TOOL_SCHEMA)
    tool["description"] = (
        f"Execute a read-only SQL SELECT query against the {db_name} PostgreSQL database. "
        "Use this to retrieve real data to answer the user's question. "
        "Results are returned as a list of row objects. "
        "Do NOT add a LIMIT or TOP clause unless the user explicitly asks for one — the proxy enforces its own row cap."
    )
    return tool


def load_api_key():
    env_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if env_key:
        return env_key

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates = [
        os.path.join(base_dir, "llm-data-explorer", "api-key.txt"),
        os.path.join(base_dir, "api-key.txt"),
    ]

    for path in candidates:
        if not os.path.isfile(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if line and not line.startswith("#"):
                    return line

    return ""


def get_chart_plugins() -> list:
    """Load chart plugin definitions from chart_plugins/*.json next to this script."""
    plugins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chart_plugins")
    plugins = []
    if not os.path.isdir(plugins_dir):
        return plugins
    for fname in sorted(os.listdir(plugins_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(plugins_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                plugin = json.load(f)
            required = ("type", "promptDescription", "renderScript")
            if all(k in plugin for k in required):
                plugins.append(plugin)
            else:
                missing = [k for k in required if k not in plugin]
                print(f"  [warn] Chart plugin '{fname}' skipped — missing fields: {missing}")
        except Exception as exc:
            print(f"  [warn] Failed to load chart plugin '{fname}': {exc}")
    return plugins


def get_available_databases() -> list:
    """Return user-created databases from PostgreSQL, excluding system databases."""
    if not PSYCOPG2_AVAILABLE:
        return [DB_NAME]
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname="postgres",
            user=DB_USER, password=DB_PASS,
            connect_timeout=10,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT datname FROM pg_database "
                "WHERE datistemplate = false AND datname <> 'postgres' "
                "ORDER BY datname"
            )
            dbs = [row[0] for row in cur.fetchall()]
        conn.close()
        return dbs or [DB_NAME]
    except Exception as exc:
        print(f"  [warn] Could not list databases: {exc}")
        return [DB_NAME]


def execute_sql(sql: str, db_name: str = None, limit: int = None) -> dict:
    """Execute a read-only SQL query and return rows as a list of dicts."""
    if not PSYCOPG2_AVAILABLE:
        return {"error": "psycopg2 not installed. Run: pip install psycopg2-binary"}

    target_db = db_name if db_name else DB_NAME

    # Rudimentary safety check — reject non-SELECT statements
    normalized = sql.strip().lstrip("(").upper()
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        return {"error": "Only SELECT / WITH queries are permitted."}

    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=target_db,
            user=DB_USER, password=DB_PASS,
            connect_timeout=10,
        )
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            raw_rows = cur.fetchmany(limit if limit is not None else DB_ROW_LIMIT)
            rows = []
            for row in raw_rows:
                clean = {}
                for k, v in row.items():
                    if hasattr(v, "isoformat"):           # date/datetime
                        clean[k] = v.isoformat()
                    elif hasattr(v, "__float__"):          # Decimal
                        clean[k] = float(v)
                    else:
                        clean[k] = v
                rows.append(clean)
        conn.close()
        return {"rows": rows, "row_count": len(rows)}
    except Exception as exc:
        return {"error": str(exc)}


def call_anthropic(payload: dict, api_key: str) -> dict:
    """Forward a single request to the Anthropic Messages API."""
    req = urllib.request.Request(
        TARGET_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            raw = res.read()
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            detail = body or f"HTTP {err.code}"
        raise RuntimeError(f"Anthropic API error {err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Network error reaching Anthropic: {err.reason}") from err
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Unexpected non-JSON response from Anthropic: {err}") from err


def run_agentic_loop(body: dict, api_key: str) -> dict:
    """
    Run the tool-use agentic loop:
      1. Inject tool definitions into the request.
      2. If Claude returns stop_reason=tool_use, execute the tools and continue.
      3. Return the final response when stop_reason=end_turn (or max iterations reached).
      4. Attach _meta.queries to the final response so the browser can show query traces.
    """
    db_name = body.get("database", DB_NAME)
    payload = {
        "model": body.get("model", DEFAULT_MODEL),
        "max_tokens": body.get("max_tokens", 4096),
        "system": body.get("system", ""),
        "messages": list(body.get("messages", [])),
        "tools": [build_query_tool(db_name)],
    }

    executed_queries = []   # accumulate for _meta
    first_turn = True

    for _ in range(MAX_TOOL_ITERATIONS):
        # Force the first turn to call a tool so Claude can't answer from training memory.
        # After the first tool result comes back, revert to "auto" for the summary turn.
        if first_turn:
            payload["tool_choice"] = {"type": "any"}
        else:
            payload.pop("tool_choice", None)

        try:
            response = call_anthropic(payload, api_key)
        except RuntimeError as err:
            # Propagate with enough context to diagnose (rate limits, auth errors, etc.)
            print(f"  [error] Anthropic call failed: {err}")
            raise

        first_turn = False
        stop_reason = response.get("stop_reason")
        content = response.get("content", [])

        # If the model hit max_tokens mid-tool-use the content may be only tool_use blocks
        # with no text.  Detect this and return a readable error instead of empty content.
        if stop_reason == "max_tokens":
            has_text = any(b.get("type") == "text" and b.get("text", "").strip() for b in content)
            if not has_text:
                response["content"] = [{
                    "type": "text",
                    "text": (
                        "I reached the token limit while preparing my response. "
                        "Please try asking a more specific question or request fewer items "
                        "(e.g. 'top 5' instead of 'top 20')."
                    )
                }]
                response["_meta"] = {"queries": executed_queries}
                return response

        if stop_reason != "tool_use":
            response["_meta"] = {"queries": executed_queries}
            return response          # end_turn, max_tokens, stop_sequence, etc.

        # Collect all tool_use blocks from this turn
        tool_use_blocks = [b for b in content if b.get("type") == "tool_use"]
        if not tool_use_blocks:
            response["_meta"] = {"queries": executed_queries}
            return response

        # Build tool result messages
        tool_results = []
        for tu in tool_use_blocks:
            if tu["name"] == "query_database":
                sql = tu.get("input", {}).get("sql", "").strip()
                desc = tu.get("input", {}).get("description", "")
                label = desc or (sql[:72] + "…" if len(sql) > 72 else sql)
                print(f"  [tool] query_database — {label}")
                result = execute_sql(sql, db_name, limit=BROWSER_ROW_LIMIT)
                row_count = result.get("row_count", "error")
                executed_queries.append({"sql": sql, "description": desc, "row_count": row_count})
                # Large result sets: send a compact summary so the LLM doesn't burn tokens on
                # raw rows. The browser re-runs the same SQL via POST /query at render time.
                if (isinstance(row_count, int) and row_count > COMPACT_THRESHOLD
                        and result.get("rows")):
                    cols = list(result["rows"][0].keys())
                    content = json.dumps({
                        "row_count": row_count,
                        "columns": cols,
                        "preview": result["rows"][:3],
                        "note": (
                            f"Full {row_count}-row dataset omitted to save tokens. "
                            "To visualize: embed this exact SQL in the chart spec as "
                            "\"sql\":\"...\" — the browser fetches the full data via POST /query."
                        ),
                    })
                else:
                    content = json.dumps(result)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": content,
                })
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": json.dumps({"error": f"Unknown tool: {tu['name']}"}),
                })

        # Extend the conversation with assistant turn + tool results
        payload["messages"] = payload["messages"] + [
            {"role": "assistant", "content": response["content"]},
            {"role": "user", "content": tool_results},
        ]

    # Fallback: exhausted MAX_TOOL_ITERATIONS — last response is still tool_use with no text.
    print(f"  [warn] Hit MAX_TOOL_ITERATIONS ({MAX_TOOL_ITERATIONS}) — returning error message")
    return {
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "I reached the maximum number of database queries for one request. Please try breaking your question into smaller parts."}],
        "_meta": {"queries": executed_queries},
    }


class ProxyHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status_code, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            status = {
                "proxy": "ok",
                "db_driver": "psycopg2" if PSYCOPG2_AVAILABLE else "missing",
                "db": f"{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
                "model": DEFAULT_MODEL,
            }
            try:
                test = execute_sql("SELECT 1 AS ping")
                status["db_status"] = "connected" if "rows" in test else f"error: {test.get('error')}"
            except Exception as e:
                status["db_status"] = f"error: {e}"
            self._send_json(200, status)
        elif self.path == "/databases":
            self._send_json(200, {"databases": get_available_databases()})
        elif self.path == "/chart-plugins":
            self._send_json(200, {"plugins": get_chart_plugins()})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == "/query":
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            try:
                body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON body."})
                return
            sql = body.get("sql", "").strip()
            db_name = body.get("database", DB_NAME)
            if not sql:
                self._send_json(400, {"error": "Missing 'sql' field."})
                return
            self._send_json(200, execute_sql(sql, db_name, limit=BROWSER_ROW_LIMIT))
            return

        if self.path != "/messages":
            self._send_json(404, {"error": "Not found"})
            return

        api_key = load_api_key()
        if not api_key:
            self._send_json(500, {
                "error": "No API key found. Set ANTHROPIC_API_KEY or add it to llm-data-explorer/api-key.txt."
            })
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body."})
            return

        try:
            result = run_agentic_loop(body, api_key)
            self._send_json(200, result)
        except urllib.error.HTTPError as err:
            details = err.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(details)
            except json.JSONDecodeError:
                parsed = {"error": details or f"Upstream HTTP {err.code}"}
            self._send_json(err.code, parsed)
        except Exception as err:
            self._send_json(502, {"error": f"Request failed: {err}"})

    def log_message(self, format, *args):
        # Print tool calls but suppress routine HTTP noise
        pass


if __name__ == "__main__":
    db_status = "psycopg2 ready" if PSYCOPG2_AVAILABLE else "psycopg2 MISSING — install psycopg2-binary"
    server = ThreadingHTTPServer((HOST, PORT), ProxyHandler)
    print(f"Proxy listening on http://{HOST}:{PORT}")
    print(f"Database : {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"DB driver: {db_status}")
    print(f"Model    : {DEFAULT_MODEL}")
    print("Route    : POST /messages")
    server.serve_forever()
