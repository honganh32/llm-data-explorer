// Cloudflare Worker port of mcp_server/server.py.
// Stateless, read-only MCP server exposing the chart-plugin library over the
// Streamable HTTP transport at /mcp. Never sleeps; runs on the Workers free plan.
import { createMcpHandler } from "agents/mcp";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import pluginsData from "./plugins.json";

interface Plugin {
  type: string;
  promptDescription?: string;
  renderScript?: string;
  [key: string]: unknown;
}

// Insertion order is preserved, matching the sorted order from build-plugins.mjs.
const PLUGINS = pluginsData as Record<string, Plugin>;

// --- suggest_chart keyword map (ported verbatim from mcp_server/server.py) ----
const KEYWORD_MAP: Array<[string[], string[]]> = [
  // network / graph
  [["network", "graph", "node", "edge", "connection", "relationship", "link", "topology", "route", "flow between"], ["graph", "dynet3d", "sankey"]],
  // time-evolving network
  [["evolv", "over time", "dynamic", "temporal", "timeline", "change", "3d", "snapshot"], ["dynet3d", "graph", "timearcs"]],
  // time arcs
  [["arc", "circular network", "timearc"], ["timearcs", "timearcs-gl", "graph"]],
  // chord / circular flow matrix
  [["chord", "chord diagram", "circular flow", "flow matrix", "ribbon", "migration", "migration matrix", "who goes to whom", "who moves to", "circular relationship", "transition matrix", "bidirectional flow", "back and forth", "interchange"], ["chord", "sankey", "graph"]],
  // hierarchy / tree
  [["hierarch", "tree", "parent", "child", "drill", "nested", "part of"], ["treemap", "sunburst", "sankey"]],
  // flow / process
  [["flow", "sankey", "funnel", "process", "stage", "conversion", "drop"], ["sankey", "funnel", "waterfall"]],
  // distribution / stats
  [["distribution", "outlier", "quartile", "box", "whisker", "spread", "variance", "violin"], ["box", "violin", "beeswarm"]],
  // beeswarm / individual points
  [["beeswarm", "swarm", "jitter", "strip plot", "dot plot", "individual point", "every value", "each observation"], ["beeswarm", "box", "violin", "scatter"]],
  // financial / candlestick
  [["candle", "ohlc", "open high low close", "stock", "price", "financial"], ["candlestick", "rangearea", "rangebar"]],
  // range / band
  [["range", "band", "min max", "min/max", "interval", "confidence", "forecast", "floor ceiling"], ["rangebar", "rangearea"]],
  // waterfall
  [["waterfall", "cumulative", "running total", "bridge chart"], ["waterfall", "bar"]],
  // ranking / multi-kpi
  [["rank", "ranking", "compare", "kpi", "metric", "score", "leaderboard", "lineup", "multiple numeric"], ["lineup", "bar", "parallel"]],
  // parallel coordinates
  [["parallel", "dimension", "multi-dimension", "multivariate", "axis"], ["parallel", "radar", "lineup"]],
  // radar / spider
  [["radar", "spider", "spider chart", "polygon", "competency", "skill", "profile"], ["radar", "parallel"]],
  // heatmap / calendar
  [["heatmap", "heat map", "matrix", "calendar", "activity", "2d grid", "correlation"], ["heatmap", "timearcs"]],
  // rose / polar
  [["rose", "polar", "wind", "direction", "circular bar"], ["rose"]],
  // pie / proportion
  [["proportion", "share", "percentage", "composition", "part of whole", "pie", "donut", "doughnut"], ["pie", "doughnut", "sunburst", "treemap"]],
  // trend / line
  [["trend", "time series", "over time", "historical", "growth", "line chart", "series"], ["line", "rangearea", "waterfall"]],
  // bar / comparison
  [["bar chart", "column", "compare categor", "compare value", "bar", "histogram"], ["bar", "lineup", "rose"]],
  // scatter / correlation
  [["scatter", "correlation", "x y", "xy", "regression", "bubble"], ["scatter"]],
  // gauge / kpi single
  [["gauge", "speedometer", "single value", "progress", "target"], ["gauge"]],
  // swimlane / gantt
  [["swimlane", "gantt", "schedule", "task", "project", "sprint"], ["swimlane", "timeline"]],
  // timeline / event
  [["event", "milestone", "timeline", "schedule", "calendar event", "when"], ["timeline", "swimlane"]],
  // pad / adjacency
  [["adjacency", "who talks to whom", "communication", "pad", "contact"], ["pad", "graph", "timearcs"]],
  // wordstream / text frequency over time
  [["wordstream", "word frequency", "keyword trend", "vocabulary", "text stream", "corpus", "topic word", "word over time", "text evolv", "word cloud over time"], ["wordstream"]],
];

function suggestChart(dataDescription: string): Array<{ type: string; score: number; description: string }> {
  const desc = dataDescription.toLowerCase();

  // Seed scores in PLUGINS insertion order so ties keep a stable, deterministic order.
  const scores = new Map<string, number>();
  for (const type of Object.keys(PLUGINS)) scores.set(type, 0);

  for (const [keywords, chartTypes] of KEYWORD_MAP) {
    if (keywords.some((kw) => desc.includes(kw))) {
      chartTypes.forEach((ct, i) => {
        if (scores.has(ct)) scores.set(ct, (scores.get(ct) ?? 0) + Math.max(3 - i, 1));
      });
    }
  }

  // Stable sort by score descending (Array.prototype.sort is stable in V8).
  const ranked = [...scores.entries()].sort((a, b) => b[1] - a[1]);
  let top = ranked.filter(([, sc]) => sc > 0).slice(0, 5);

  if (top.length === 0) {
    top = ["bar", "line", "scatter", "pie", "graph"].map((ct) => [ct, 0] as [string, number]);
  }

  return top.map(([ct, sc]) => ({
    type: ct,
    score: sc,
    description: PLUGINS[ct]?.promptDescription ?? "",
  }));
}

// --- MCP result helper: return structured data as pretty-printed JSON text ----
function jsonResult(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

function createServer(): McpServer {
  const server = new McpServer({
    name: "LLM Chart Plugin Library",
    version: "1.0.0",
  });

  server.tool(
    "list_charts",
    "List all available chart types with their descriptions. Returns a list of {type, description} objects. Use this to discover which chart types are available before rendering.",
    {},
    async () =>
      jsonResult(
        Object.values(PLUGINS).map((p) => ({
          type: p.type,
          description: p.promptDescription ?? "",
        })),
      ),
  );

  server.tool(
    "get_chart",
    "Return the full plugin spec for a chart type, including its renderScript. The renderScript is a self-contained JS function string: function(wrap, spec) { ... }. Call it with a DOM element and a resolved spec object to render the chart. CDN dependencies are loaded automatically inside the renderScript.",
    { chart_type: z.string().describe("The chart type identifier, e.g. 'bar' or 'sankey'.") },
    async ({ chart_type }) => {
      const plugin = PLUGINS[chart_type];
      if (!plugin) {
        return jsonResult({
          error: `Chart type '${chart_type}' not found. Available: ${Object.keys(PLUGINS).sort()}`,
        });
      }
      return jsonResult(plugin);
    },
  );

  server.tool(
    "suggest_chart",
    "Suggest the best chart types for the given data description. Provide a plain-English description of your data and goal, e.g. 'show how network connections between IP addresses changed over 3 days' or 'compare revenue and cost across 10 products'. Returns up to 5 ranked suggestions with type and description.",
    { data_description: z.string().describe("Plain-English description of your data and goal.") },
    async ({ data_description }) => jsonResult(suggestChart(data_description)),
  );

  return server;
}

const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, mcp-session-id, mcp-protocol-version, last-event-id",
  "Access-Control-Expose-Headers": "mcp-session-id",
  "Access-Control-Max-Age": "86400",
};

const LANDING = `LLM Chart Plugin Library — MCP server (Cloudflare Worker)

Transport: Streamable HTTP
Endpoint:  POST /mcp
Charts:    ${Object.keys(PLUGINS).length} plugins

Connect an MCP client to  <this-url>/mcp
  claude mcp add chart-plugins --transport http <this-url>/mcp
`;

export default {
  async fetch(request: Request, env: unknown, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // CORS preflight (lets browser-based MCP clients connect).
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // Friendly landing page / health check.
    if (url.pathname === "/" || url.pathname === "/health") {
      return new Response(LANDING, {
        headers: { "content-type": "text/plain; charset=utf-8", ...CORS_HEADERS },
      });
    }

    // The old Railway server used the deprecated SSE transport at /sse.
    // Point stragglers at the new endpoint instead of 404ing silently.
    if (url.pathname === "/sse") {
      return new Response(
        "This server moved to the Streamable HTTP transport. Connect to /mcp instead.",
        { status: 410, headers: { "content-type": "text/plain; charset=utf-8", ...CORS_HEADERS } },
      );
    }

    const response = await createMcpHandler(createServer(), { route: "/mcp" })(
      request,
      env as never,
      ctx,
    );

    // Re-emit with permissive CORS while preserving streaming + MCP headers.
    const headers = new Headers(response.headers);
    for (const [k, v] of Object.entries(CORS_HEADERS)) headers.set(k, v);
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
} satisfies ExportedHandler;
