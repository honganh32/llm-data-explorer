# LLM Data Explorer — MCP Chart Plugin Library

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives any AI assistant access to 31 self-contained, browser-executable chart types. Each chart plugin is a single JSON file containing a `renderScript` — a JS function that loads its own CDN dependencies and renders into any DOM element.

## Live MCP endpoint

The server runs on the **Cloudflare Workers free plan** (always-on, no cold-start
sleep). After deploying your own (see [Deploy your own](#deploy-your-own)), your
endpoint is:

```
https://llm-chart-mcp.honganh32.workers.dev/mcp
```

> Uses the current **Streamable HTTP** transport at `/mcp`. (The retired Railway
> deployment used the deprecated SSE transport at `/sse`.)
>
> **Deploy your own:** See [Deploy your own](#deploy-your-own) below.

---

## Connect to any MCP-compatible client

### Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac):

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

Restart Claude Desktop. The tools appear automatically.

### Claude Code (CLI)

```bash
claude mcp add chart-plugins --transport http https://llm-chart-mcp.honganh32.workers.dev/mcp
```

### Cursor / other MCP clients

Add the Streamable HTTP URL `https://llm-chart-mcp.honganh32.workers.dev/mcp` in your client's MCP server settings.

### Local development

```bash
pip install fastmcp
python mcp_server/server.py
# → http://localhost:8000/sse
```

---

## Tools exposed

| Tool | Description |
|------|-------------|
| `list_charts` | Returns all chart types with prompt descriptions |
| `get_chart(chart_type)` | Returns the full plugin JSON including `renderScript` |
| `suggest_chart(data_description)` | Ranks the best chart types for your data (plain-English input) |

### Example prompts

- *"I have sales data for 10 products over 4 quarters — suggest a chart and render it."*
- *"Show me how network connections between IP addresses evolved over 3 days."*
- *"Give me a gauge showing CPU utilization at 73%."*

The AI will call `suggest_chart`, pick the best type, retrieve the `renderScript` via `get_chart`, and generate the code to render it in your app.

---

## Available chart types

| Library | Chart types |
|---------|-------------|
| Chart.js | bar, line, pie, doughnut, scatter |
| ECharts | rose, radar, heatmap, treemap, sunburst, parallel, sankey, funnel, graph, gauge |
| Plotly | box, violin, waterfall, candlestick |
| ApexCharts | timeline, rangebar, rangearea |
| LineUpJS | lineup |
| D3 | storyline, nodetrix, swimlane, wordstream |
| Three.js + D3 | dynet3d |
| Custom (self-contained) | crossset, timearcs, timearcs-gl |

---

## Using the renderScript in your app

Each `renderScript` is a self-contained `function(wrap, spec)` string. Call it like this:

```js
const plugin = await mcpClient.callTool("get_chart", { chart_type: "bar" });
const renderFn = new Function("return (" + plugin.renderScript + ")")();
renderFn(document.getElementById("my-chart"), {
  type: "bar",
  title: "Sales by Region",
  labels: ["North", "South", "East", "West"],
  datasets: [{ label: "Q1", data: [120, 85, 200, 60] }]
});
```

The function loads its own CDN scripts on first call and renders immediately. Multiple calls reuse already-loaded scripts.

---

## Deploy your own

### Cloudflare Workers (recommended — free, always-on)

A TypeScript port of the server lives in [`cloudflare_worker/`](cloudflare_worker/).
It runs on the Workers free plan with no credit card and no cold-start sleep.

```bash
cd cloudflare_worker
npm install
npx wrangler login
npm run deploy
```

Your endpoint is the printed URL + `/mcp`. Full guide: [cloudflare_worker/README.md](cloudflare_worker/README.md).

### Render (Python server, free tier)

1. Create a **Web Service** pointing to this repo.
2. Build command: `pip install -r mcp_server/requirements.txt`
3. Start command: `python mcp_server/server.py`

> Note: Render's free web services sleep after 15 minutes of inactivity and cold-start on the next request.

---

## Contributing a new chart plugin

Want to add a chart type? See [CONTRIBUTING.md](CONTRIBUTING.md).
