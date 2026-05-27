# MCP Chart Plugin Server — Deployment Guide

## What this is

An MCP (Model Context Protocol) server that exposes 31 self-contained visualization chart plugins to any MCP-compatible AI model. Each plugin contains a `renderScript` — a browser-executable JS function that loads its own CDN dependencies and renders the chart into a given DOM element.

## Running locally

```bash
pip install fastmcp
python mcp_server/server.py
# → http://localhost:8000/sse
```

Set `PORT` env var to change the port (default: 8000).

## MCP tools exposed

| Tool | Description |
|------|-------------|
| `list_charts` | Returns all 31 chart types with their prompt descriptions |
| `get_chart(chart_type)` | Returns the full plugin JSON including `renderScript` |
| `suggest_chart(data_description)` | Keyword-based ranking of best chart types for your data |

## Connecting from Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "chart-plugins": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

Or for a deployed URL:

```json
{
  "mcpServers": {
    "chart-plugins": {
      "url": "https://YOUR-APP.railway.app/sse"
    }
  }
}
```

## Deploying on Railway (free tier)

1. Push this repo to GitHub.
2. Create a new Railway project → **Deploy from GitHub repo**.
3. Railway auto-detects `railway.toml` and runs `python mcp_server/server.py`.
4. Set the `PORT` environment variable if needed (Railway injects it automatically).
5. Your MCP endpoint will be at `https://YOUR-APP.railway.app/sse`.

## Deploying on Render (free tier)

1. Create a **Web Service** pointing to this repo.
2. Build command: `pip install -r mcp_server/requirements.txt`
3. Start command: `python mcp_server/server.py`
4. Set environment variable `PORT` (Render injects it automatically).

## Chart types available

**Chart.js:** bar, line, pie, doughnut, scatter  
**ECharts:** rose, radar, heatmap, treemap, sunburst, parallel, sankey, funnel, graph  
**Plotly:** box, violin, waterfall, candlestick  
**ApexCharts:** timeline, rangebar, rangearea  
**LineUpJS:** lineup  
**Three.js + D3:** dynet3d  
**Custom:** aardvark, crossset, gauge, pad, swimlane, timearcs, timearcs-gl, timelighting  

## Plugin JSON schema

Each file in `chart_plugins/` follows this schema:

```json
{
  "type": "bar",
  "promptDescription": "- **bar** — ...",
  "renderScript": "function(wrap,spec){ ... }"
}
```

- `type` — unique chart identifier
- `promptDescription` — markdown snippet describing the chart type and spec format for LLM system prompts
- `renderScript` — self-contained JS function string; call as `fn(domElement, specObject)`

The `renderScript` is safe to eval in any browser context. It dynamically loads its own CDN script(s) and renders the chart. Multiple calls to `renderScript` with the same CDN URLs reuse already-loaded scripts.
