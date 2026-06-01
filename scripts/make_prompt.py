#!/usr/bin/env python3
"""
Generate a copy-paste prompt for any AI chatbot (ChatGPT, Claude, Gemini, etc.)
to convert visualization source code into a chart plugin JSON.

No API key required — just paste the output into any AI chat window.

Usage:
    python scripts/make_prompt.py my_chart.js                         # local file
    python scripts/make_prompt.py https://github.com/user/repo        # GitHub repo (auto-filters files)
    python scripts/make_prompt.py https://github.com/user/repo/blob/main/src/chart.js  # single file
    python scripts/make_prompt.py                                      # paste source interactively

The prompt is printed to stdout and also saved to scripts/_last_prompt.txt for easy copying.
"""

import json
import sys
import urllib.request
import urllib.error
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# File filtering constants for GitHub repos
# ---------------------------------------------------------------------------

INCLUDE_EXTENSIONS = {
    ".js", ".mjs", ".ts", ".jsx", ".tsx",   # JavaScript / TypeScript
    ".py",                                   # Python (e.g. matplotlib, plotly)
    ".html",                                 # standalone examples
    ".vue", ".svelte",                       # component frameworks
    ".r", ".R",                              # R visualizations
    ".ipynb",                                # Jupyter notebooks (contain rendering code)
}

EXCLUDE_DIRS = {
    "node_modules", "dist", "build", "out", ".github",
    "test", "tests", "__tests__", "__pycache__", ".git",
    "coverage", ".nyc_output", ".cache", "vendor",
    ".next", ".nuxt", "public", "static", "assets",
}

SKIP_FILENAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "tsconfig.json", "jest.config.js", "webpack.config.js",
    "rollup.config.js", "vite.config.js", "esbuild.config.js",
    ".eslintrc.json", ".prettierrc", ".babelrc",
}

# Per-file and total size caps (in bytes / chars)
MAX_FILE_SIZE  = 40_000   # skip individual files larger than this
MAX_TOTAL_SIZE = 80_000   # stop fetching once we have this much source


# ---------------------------------------------------------------------------
# Example plugin (shown inside the prompt so the LLM understands the pattern)
# ---------------------------------------------------------------------------

EXAMPLE_PLUGIN = r"""{
  "type": "bar",
  "promptDescription": "- **bar** — comparisons, rankings, grouped side-by-side metrics. Spec: { \"type\":\"bar\", \"title\":\"...\", \"xLabel\":\"...\", \"yLabel\":\"...\", \"labels\":[\"A\",\"B\",\"C\"], \"datasets\":[{\"label\":\"Series 1\",\"data\":[10,20,30]}] }",
  "renderScript": "function(wrap,spec){if(!wrap.style.height)wrap.style.height='400px';function load(url,g,cb){if(window[g]){cb();return;}var s=document.createElement('script');s.src=url;s.onload=cb;document.head.appendChild(s);}load('https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js','Chart',function(){var canvas=document.createElement('canvas');wrap.appendChild(canvas);new Chart(canvas,{type:spec.type||'bar',data:{labels:spec.labels||[],datasets:(spec.datasets||[]).map(function(d,i){var colors=['#534AB7','#2E9CDB','#4BC1A8','#E8833A'];return{label:d.label||'',data:d.data||[],backgroundColor:colors[i%colors.length]+'BB',borderColor:colors[i%colors.length],borderWidth:1.5};})},options:{responsive:true,maintainAspectRatio:true,plugins:{title:{display:!!spec.title,text:spec.title||''}},scales:{x:{title:{display:!!spec.xLabel,text:spec.xLabel||''}},y:{title:{display:!!spec.yLabel,text:spec.yLabel||''},beginAtZero:true}}}});});}"
}"""


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """\
You are helping create a chart plugin for an open-source data visualization system called LLM Data Explorer.

## What you must produce

A single JSON object with exactly three string fields:

  "type"              — unique lowercase identifier, hyphens allowed (e.g. "chord", "force-directed")
  "promptDescription" — see format below
  "renderScript"      — see format below

---

## Field: promptDescription

A single-line markdown snippet that tells an AI assistant when to use this chart and what data it needs.
Use this EXACT format (everything on one line, no newlines):

  - **<type>** — <one sentence: when to use this chart>. Spec: {{ "type":"<type>", "field1":"...", "field2":[] }}

Rules:
- Start with `- **<type>** —`
- The sentence should say WHEN this chart is useful (not what it looks like)
- Include every required data field in the Spec example, with realistic placeholder values
- Escape all inner double-quotes as \\" because this is a JSON string value

---

## Field: renderScript

A self-contained JavaScript function, written as a compact JSON string. Always this signature:

  function(wrap, spec) {{ ... }}

- `wrap` is a DOM <div> element — render the chart inside it
- `spec` is a plain JS object with the data fields from your promptDescription Spec
- Load any required library from a public CDN using this exact helper (copy it verbatim):

  function load(url, globalName, callback) {{
    if (window[globalName]) {{ callback(); return; }}
    var s = document.createElement('script');
    s.src = url;
    s.onload = callback;
    document.head.appendChild(s);
  }}

- Set a default height only if not already set: `if (!wrap.style.height) wrap.style.height = '400px';`
- Do NOT assume any globals beyond `window` and `document`
- Keep it compact: no comments, minimal whitespace, use semicolons
- The entire value must be a valid JSON string — no literal newlines inside it

---

## Complete working example

{example}

---

## Your task

Convert the visualization source below into a plugin JSON following all rules above.

Step-by-step:
1. Choose a `type` name that is lowercase and hyphen-separated (e.g. `chord`, `arc-diagram`)
2. Identify what data fields a caller must provide — those become the spec
3. Find the library's CDN URL on jsdelivr.net or unpkg.com (if the source uses a local or npm build)
4. Write a `renderScript` that loads the library from CDN and renders using `wrap` and `spec`
5. Write a `promptDescription` in the exact format shown above

Output ONLY the JSON object. No markdown code fences, no explanation, nothing before or after the JSON.
If the source spans multiple files, synthesize them into one self-contained renderScript.

---

## Visualization source ({source_label})

{source}
"""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 403:
            sys.exit(
                f"HTTP 403 fetching {url}\n"
                "  The repo may be private, or the GitHub API rate limit was hit.\n"
                "  Unauthenticated requests are limited to 60/hour. Try again later."
            )
        if e.code == 404:
            sys.exit(f"HTTP 404: not found — {url}\n  Check that the URL is correct and the repo is public.")
        sys.exit(f"HTTP {e.code} fetching {url}")
    except urllib.error.URLError as e:
        sys.exit(f"Network error: {e.reason}")


def fetch_text(url: str) -> str:
    return _http_get(url).decode("utf-8", errors="replace")


def github_api(path: str) -> object:
    url = f"https://api.github.com/{path.lstrip('/')}"
    data = _http_get(url, headers={
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "make_prompt.py",
    })
    return json.loads(data)


# ---------------------------------------------------------------------------
# GitHub URL parsing
# ---------------------------------------------------------------------------

def parse_github_url(url: str):
    """
    Returns (owner, repo, kind, branch, path) or None if not a GitHub URL.
    kind is one of: 'repo', 'tree', 'blob', 'raw'
    """
    url = url.rstrip("/")

    if url.startswith("https://raw.githubusercontent.com/"):
        rest = url[len("https://raw.githubusercontent.com/"):]
        parts = rest.split("/", 3)
        if len(parts) < 3:
            return None
        owner, repo, branch = parts[0], parts[1], parts[2]
        path = parts[3] if len(parts) > 3 else ""
        return owner, repo, "raw", branch, path

    if "github.com/" not in url:
        return None

    rest = url.split("github.com/", 1)[1]
    parts = rest.split("/")
    if len(parts) < 2:
        return None

    owner, repo = parts[0], parts[1]

    if len(parts) == 2:
        return owner, repo, "repo", "", ""

    kind_word = parts[2] if len(parts) > 2 else ""

    if kind_word in ("blob", "tree") and len(parts) >= 4:
        branch = parts[3]
        path = "/".join(parts[4:]) if len(parts) > 4 else ""
        return owner, repo, kind_word, branch, path

    # Unrecognised suffix — treat as repo root
    return owner, repo, "repo", "", ""


# ---------------------------------------------------------------------------
# File relevance filtering and scoring
# ---------------------------------------------------------------------------

def _is_relevant(file_path: str) -> bool:
    p = PurePosixPath(file_path)
    # Exclude blacklisted directories anywhere in the path
    for part in p.parts[:-1]:
        if part.lower() in EXCLUDE_DIRS:
            return False
    # Exclude known non-visualization filenames
    if p.name.lower() in SKIP_FILENAMES:
        return False
    # Must have a recognised extension
    return p.suffix.lower() in INCLUDE_EXTENSIONS


def _score(item: dict) -> int:
    p = PurePosixPath(item["path"].lower())
    score = 0
    for part in p.parts[:-1]:
        if part in {"src", "lib", "source", "examples", "demo", "example"}:
            score += 3
        if part in {"test", "tests", "docs", "dist", "build", "coverage"}:
            score -= 5
    stem = p.stem
    for kw in ("chart", "plot", "vis", "render", "draw", "graph", "viz", "layout"):
        if kw in stem:
            score += 2
    size = item.get("size", 0)
    if size < 5_000:
        score += 2
    elif size < 20_000:
        score += 1
    elif size > 80_000:
        score -= 4   # likely a bundle / generated file
    return score


# ---------------------------------------------------------------------------
# Fetching strategies
# ---------------------------------------------------------------------------

def fetch_single_file(url: str, label: str) -> tuple[str, str]:
    print(f"Fetching {label} ...", file=sys.stderr)
    content = fetch_text(url)
    print(f"  {len(content):,} chars", file=sys.stderr)
    return content, label


def fetch_github_repo(owner: str, repo: str, branch: str, root_path: str) -> tuple[str, str]:
    label = f"github.com/{owner}/{repo}"

    # Resolve default branch if not given
    if not branch:
        info = github_api(f"repos/{owner}/{repo}")
        branch = info.get("default_branch", "main")

    print(f"Fetching file tree from {label} (branch: {branch}) ...", file=sys.stderr)
    tree_data = github_api(f"repos/{owner}/{repo}/git/trees/{branch}?recursive=1")

    if tree_data.get("truncated"):
        print("  Warning: tree was truncated (very large repo). Some files may be missing.", file=sys.stderr)

    # Filter and score
    candidates = [
        item for item in tree_data.get("tree", [])
        if item["type"] == "blob"
        and _is_relevant(item["path"])
        and item.get("size", 0) <= MAX_FILE_SIZE
        and (not root_path or item["path"].startswith(root_path.strip("/")))
    ]
    candidates.sort(key=_score, reverse=True)
    print(f"  {len(candidates)} candidate files after filtering", file=sys.stderr)

    # Fetch up to size budget
    fetched: list[tuple[str, str]] = []
    total = 0
    for item in candidates:
        if total >= MAX_TOTAL_SIZE:
            print(f"  Size budget reached — stopping early", file=sys.stderr)
            break
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{item['path']}"
        try:
            content = fetch_text(raw_url)
        except SystemExit:
            continue  # skip files that fail, keep going
        fetched.append((item["path"], content))
        total += len(content)
        print(f"  + {item['path']}  ({len(content):,} chars)", file=sys.stderr)

    if not fetched:
        sys.exit("Error: no files could be fetched. Check that the repo is public.")

    skipped = len(candidates) - len(fetched)
    print(f"\n  {len(fetched)} files fetched, {skipped} skipped ({total:,} chars total)", file=sys.stderr)

    # Bundle with file headers so the LLM sees the structure
    parts = []
    for path, content in fetched:
        ext = PurePosixPath(path).suffix.lstrip(".")
        parts.append(f"### {path}\n```{ext}\n{content.rstrip()}\n```")
    source = "\n\n".join(parts)

    return source, label


def resolve_source(arg: str) -> tuple[str, str]:
    """Return (source_text, label) from a file path, URL, or interactive input."""
    if not arg.startswith(("http://", "https://")):
        p = Path(arg)
        if not p.exists():
            sys.exit(f"Error: file not found: {arg}")
        content = p.read_text(encoding="utf-8")
        print(f"Loaded {p.name}  ({len(content):,} chars)", file=sys.stderr)
        return content, p.name

    parsed = parse_github_url(arg)
    if parsed is None:
        # Generic URL — fetch directly
        return fetch_single_file(arg, arg)

    owner, repo, kind, branch, path = parsed

    if kind == "raw":
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        return fetch_single_file(raw_url, f"github.com/{owner}/{repo}/{path}")

    if kind == "blob":
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        return fetch_single_file(raw_url, f"github.com/{owner}/{repo}/{path}")

    # "repo" or "tree" — fetch the whole directory
    return fetch_github_repo(owner, repo, branch, path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) >= 2:
        source, label = resolve_source(sys.argv[1])
    else:
        print("No argument given — paste your visualization source below.", file=sys.stderr)
        print("Press Ctrl+D (macOS/Linux) or Ctrl+Z + Enter (Windows) when done.\n", file=sys.stderr)
        try:
            source = sys.stdin.read().strip()
        except (EOFError, KeyboardInterrupt):
            source = ""
        label = "pasted source"

    if not source.strip():
        sys.exit("Error: no source provided.")

    prompt = PROMPT_TEMPLATE.format(
        example=EXAMPLE_PLUGIN,
        source_label=label,
        source=source,
    )

    out_path = Path(__file__).parent / "_last_prompt.txt"
    out_path.write_text(prompt, encoding="utf-8")
    print(prompt)

    print("\n" + "=" * 60, file=sys.stderr)
    print(f"Prompt saved to: {out_path}", file=sys.stderr)
    print("Next steps:", file=sys.stderr)
    print("  1. Copy the prompt (or open scripts/_last_prompt.txt)", file=sys.stderr)
    print("  2. Paste it into ChatGPT, Claude, Gemini, or any AI chat", file=sys.stderr)
    print("  3. Save the JSON response as  chart_plugins/<type>.json", file=sys.stderr)
    print("     (remove any ``` fences if the AI wrapped its output)", file=sys.stderr)
    print("  4. python mcp_server/validate_plugin.py chart_plugins/<type>.json", file=sys.stderr)


if __name__ == "__main__":
    main()
