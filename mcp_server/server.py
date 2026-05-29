from fastmcp import FastMCP
import json, os
from pathlib import Path

PLUGINS_DIR = Path(os.environ.get("PLUGINS_DIR", str(Path(__file__).parent.parent / "chart_plugins")))

def load_plugins() -> dict:
    plugins = {}
    for f in sorted(f for f in PLUGINS_DIR.glob("*.json") if not f.stem.startswith("_")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
            if "type" in p:
                plugins[p["type"]] = p
        except Exception:
            pass
    return plugins

PLUGINS = load_plugins()

mcp = FastMCP("LLM Chart Plugin Library")


@mcp.tool()
def list_charts() -> list[dict]:
    """
    List all available chart types with their descriptions.
    Returns a list of {type, description} objects.
    Use this to discover which chart types are available before rendering.
    """
    return [
        {"type": p["type"], "description": p.get("promptDescription", "")}
        for p in PLUGINS.values()
    ]


@mcp.tool()
def get_chart(chart_type: str) -> dict:
    """
    Return the full plugin spec for a chart type, including its renderScript.
    The renderScript is a self-contained JS function string:
      function(wrap, spec) { ... }
    Call it with a DOM element and a resolved spec object to render the chart.
    CDN dependencies are loaded automatically inside the renderScript.
    """
    plugin = PLUGINS.get(chart_type)
    if plugin is None:
        return {"error": f"Chart type '{chart_type}' not found. Available: {sorted(PLUGINS.keys())}"}
    return plugin


@mcp.tool()
def suggest_chart(data_description: str) -> list[dict]:
    """
    Suggest the best chart types for the given data description.
    Provide a plain-English description of your data and goal, e.g.
    'show how network connections between IP addresses changed over 3 days'
    or 'compare revenue and cost across 10 products'.
    Returns up to 5 ranked suggestions with type and description.
    """
    desc = data_description.lower()

    keyword_map = [
        # network / graph
        (["network", "graph", "node", "edge", "connection", "relationship", "link", "topology", "route", "flow between"], ["graph", "dynet3d", "sankey"]),
        # time-evolving network
        (["evolv", "over time", "dynamic", "temporal", "timeline", "change", "3d", "snapshot"], ["dynet3d", "graph", "timearcs"]),
        # time arcs
        (["arc", "chord", "circular network", "timearc"], ["timearcs", "timearcs-gl", "graph"]),
        # hierarchy / tree
        (["hierarch", "tree", "parent", "child", "drill", "nested", "part of"], ["treemap", "sunburst", "sankey"]),
        # flow / process
        (["flow", "sankey", "funnel", "process", "stage", "conversion", "drop"], ["sankey", "funnel", "waterfall"]),
        # distribution / stats
        (["distribution", "outlier", "quartile", "box", "whisker", "spread", "variance", "violin"], ["box", "violin"]),
        # financial / candlestick
        (["candle", "ohlc", "open high low close", "stock", "price", "financial"], ["candlestick", "rangearea", "rangebar"]),
        # range / band
        (["range", "band", "min max", "min/max", "interval", "confidence", "forecast", "floor ceiling"], ["rangebar", "rangearea"]),
        # waterfall
        (["waterfall", "cumulative", "running total", "bridge chart"], ["waterfall", "bar"]),
        # ranking / multi-kpi
        (["rank", "ranking", "compare", "kpi", "metric", "score", "leaderboard", "lineup", "multiple numeric"], ["lineup", "bar", "parallel"]),
        # parallel coordinates
        (["parallel", "dimension", "multi-dimension", "multivariate", "axis"], ["parallel", "radar", "lineup"]),
        # radar / spider
        (["radar", "spider", "spider chart", "polygon", "competency", "skill", "profile"], ["radar", "parallel"]),
        # heatmap / calendar
        (["heatmap", "heat map", "matrix", "calendar", "activity", "2d grid", "correlation"], ["heatmap", "timearcs"]),
        # rose / polar
        (["rose", "polar", "wind", "direction", "circular bar"], ["rose"]),
        # pie / proportion
        (["proportion", "share", "percentage", "composition", "part of whole", "pie", "donut", "doughnut"], ["pie", "doughnut", "sunburst", "treemap"]),
        # trend / line
        (["trend", "time series", "over time", "historical", "growth", "line chart", "series"], ["line", "rangearea", "waterfall"]),
        # bar / comparison
        (["bar chart", "column", "compare categor", "compare value", "bar", "histogram"], ["bar", "lineup", "rose"]),
        # scatter / correlation
        (["scatter", "correlation", "x y", "xy", "regression", "bubble"], ["scatter"]),
        # gauge / kpi single
        (["gauge", "speedometer", "single value", "progress", "target"], ["gauge"]),
        # swimlane / gantt
        (["swimlane", "gantt", "schedule", "task", "project", "sprint"], ["swimlane", "timeline"]),
        # timeline / event
        (["event", "milestone", "timeline", "schedule", "calendar event", "when"], ["timeline", "swimlane"]),
        # pad / adjacency
        (["adjacency", "who talks to whom", "communication", "pad", "contact"], ["pad", "graph", "timearcs"]),
        # wordstream / text frequency over time
        (["wordstream", "word frequency", "keyword trend", "vocabulary", "text stream", "corpus", "topic word", "word over time", "text evolv", "word cloud over time"], ["wordstream"]),
    ]

    scores: dict[str, int] = {t: 0 for t in PLUGINS}

    for keywords, chart_types in keyword_map:
        matched = any(kw in desc for kw in keywords)
        if matched:
            for i, ct in enumerate(chart_types):
                if ct in scores:
                    scores[ct] += max(3 - i, 1)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = [(ct, sc) for ct, sc in ranked if sc > 0][:5]

    if not top:
        # Fallback: return most general charts
        top = [(ct, 0) for ct in ["bar", "line", "scatter", "pie", "graph"]]

    return [
        {
            "type": ct,
            "score": sc,
            "description": PLUGINS[ct].get("promptDescription", "") if ct in PLUGINS else "",
        }
        for ct, sc in top
    ]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
