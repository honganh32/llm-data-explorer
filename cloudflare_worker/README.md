# LLM Chart Plugin MCP Server — Cloudflare Worker

A cost-free, always-on replacement for the Railway deployment. This is a faithful
TypeScript port of [`../mcp_server/server.py`](../mcp_server/server.py): the same
three tools (`list_charts`, `get_chart`, `suggest_chart`) serving the same
`../chart_plugins/*.json` library.

**Why Cloudflare Workers:** the Workers free plan has no credit-card requirement,
no cold-start sleep (unlike Render/Railway free tiers), and runs globally. Because
this server is stateless and read-only, it uses `createMcpHandler` (no Durable
Objects needed) and stays entirely within the free plan.

## What changed from the Python server

| | Python (Railway) | This Worker |
|---|---|---|
| Transport | SSE (`/sse`) — deprecated in the MCP spec | Streamable HTTP (`/mcp`) — current standard |
| Plugins loaded | read from disk at runtime | bundled at build time into `src/plugins.json` |
| Hosting | Railway (free trial expired) | Cloudflare Workers free plan |

The chart plugins are the single source of truth in `../chart_plugins/`.
`npm run gen` bundles them into `src/plugins.json`; this runs automatically before
every `dev` and `deploy`, so editing a plugin and redeploying is all it takes.

## Deploy (first time, ~2 minutes)

```bash
cd cloudflare_worker
npm install
npx wrangler login          # opens a browser; free Cloudflare account, no card
npm run deploy
```

Wrangler prints your endpoint, e.g.:

```
https://llm-chart-mcp.honganh32.workers.dev
```

Your MCP endpoint is that URL + `/mcp`:

```
https://llm-chart-mcp.honganh32.workers.dev/mcp
```

Redeploy after any plugin change with `npm run deploy`.

## Connect a client

**Claude Code**

```bash
claude mcp add chart-plugins --transport http https://llm-chart-mcp.honganh32.workers.dev/mcp
```

**Claude Desktop** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "chart-plugins": {
      "type": "streamable-http",
      "url": "https://llm-chart-mcp.honganh32.workers.dev/mcp"
    }
  }
}
```

Older clients that only speak stdio can bridge with
`npx mcp-remote https://.../mcp`.

## Local development

```bash
npm run dev          # regenerates plugins.json, then wrangler dev on :8787
```

Smoke-test it (Streamable HTTP requires the dual Accept header):

```bash
curl -s -X POST http://127.0.0.1:8787/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"suggest_chart","arguments":{"data_description":"network connections over time"}}}'
```

Or point the MCP Inspector at `http://127.0.0.1:8787/mcp`:
`npx @modelcontextprotocol/inspector`.

## Endpoints

| Path | Purpose |
|---|---|
| `POST /mcp` | MCP Streamable HTTP endpoint (connect clients here) |
| `GET /` or `/health` | Plain-text landing / health check |
| `GET /sse` | `410 Gone` — the old SSE transport moved to `/mcp` |

## Files

- `src/index.ts` — the Worker: tool definitions + `suggest_chart` keyword map (ported verbatim)
- `src/plugins.json` — generated bundle of all chart plugins (do not edit by hand)
- `scripts/build-plugins.mjs` — regenerates `src/plugins.json` from `../chart_plugins/`
- `wrangler.jsonc` — Worker config (name, entry, compatibility date)
