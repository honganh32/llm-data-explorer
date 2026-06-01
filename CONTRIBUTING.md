# Contributing a New Chart Plugin

Chart plugins are single JSON files in `chart_plugins/`. Adding a new chart type means adding one file and submitting a PR. No Python or server knowledge required.

---

## Quick start: use an AI chatbot (recommended)

If you have access to any AI chatbot (ChatGPT, Claude, Gemini, etc.) you can generate a complete plugin from your existing visualization code in minutes — no knowledge of the plugin format required.

**Step 1 — Generate the prompt:**

```bash
# From a local file
python scripts/make_prompt.py my_chart.js

# From a GitHub repo (script auto-selects relevant files)
python scripts/make_prompt.py https://github.com/user/repo

# From a single file on GitHub
python scripts/make_prompt.py https://github.com/user/repo/blob/main/src/chart.js
```

This fetches the source and produces a ready-to-paste prompt. The prompt is printed to the terminal and also saved to `scripts/_last_prompt.txt`.

> If your source is a snippet rather than a file, run the script with no arguments and paste your code interactively (end with Ctrl+D on macOS/Linux, Ctrl+Z + Enter on Windows).

When given a GitHub repo URL the script automatically filters out `node_modules`, build artifacts, config files, and oversized bundles — only the visualization source files are included. Files are ranked by relevance (source directories, visualization-related names, reasonable size) and fetching stops once roughly 80 KB of source is collected.

**Step 2 — Paste into a chatbot:**

Copy the prompt into ChatGPT, Claude, Gemini, or any AI chat. The AI will return a complete plugin JSON.

**Step 3 — Save and strip fences:**

Save the JSON response as `chart_plugins/<type>.json` (the `type` field in the JSON tells you the filename). If the AI wrapped its output in ` ``` ` code fences, remove those before saving.

**Step 4 — Validate:**

```bash
python mcp_server/validate_plugin.py chart_plugins/<type>.json
```

Fix any errors the validator reports (most are small formatting issues the AI occasionally misses), then skip to [Test locally](#step-4-test-locally) below.

---

## Manual path: fill in the template yourself

Use this if you prefer to write the plugin by hand or want full control.

### Prerequisites

- Python 3.8+ (for running the server and validator)
- `pip install fastmcp`
- A browser for testing the renderScript

---

## Step 1: Copy the template

```bash
cp chart_plugins/_template.json chart_plugins/YOUR_CHART_TYPE.json
```

Name the file after the chart type (lowercase, hyphens allowed, e.g. `chord.json`, `force-directed.json`).

---

## Step 2: Fill in the three required fields

Open your new file and set:

### `type` (string)
A unique, lowercase identifier for your chart. Must match the filename without `.json`.

```json
"type": "chord"
```

### `promptDescription` (string)
A markdown snippet that tells an LLM what this chart does and what the spec looks like. Follow this pattern exactly — it is injected directly into LLM system prompts:

```
- **chord** — circular diagram showing flows or relationships between categories. Spec: { "type":"chord", "title":"...", "labels":["A","B","C"], "matrix":[[0,10,5],[10,0,8],[5,8,0]] }
```

Tips:
- Start with `- **type** —`
- One sentence describing when to use it
- Include a minimal `Spec:` example with all required fields

### `renderScript` (string)
A self-contained JS function as a string:

```js
"renderScript": "function(wrap, spec) { ... }"
```

Requirements:
- **Self-contained**: load any CDN libraries inside the function using the `load()` pattern (see below)
- **No global state**: do not assume any globals except `window` and `document`
- **Resize-aware**: call `window.addEventListener('resize', ...)` if the chart needs it
- **Height**: if the chart needs a fixed height, set it only if `wrap.style.height` is not already set: `if (!wrap.style.height) wrap.style.height = '400px';`

#### Loading CDN scripts inside renderScript

Use this helper pattern (copy it into your function):

```js
function load(url, globalName, callback) {
  if (window[globalName]) { callback(); return; }
  var s = document.createElement('script');
  s.src = url;
  s.onload = callback;
  document.head.appendChild(s);
}
load('https://cdn.jsdelivr.net/npm/YOUR-LIB/dist/lib.min.js', 'LibGlobalName', function() {
  // render here
});
```

This pattern is safe to call multiple times — it reuses already-loaded scripts.

---

## Step 3: Validate your plugin

```bash
python mcp_server/validate_plugin.py chart_plugins/YOUR_CHART_TYPE.json
```

Fix any errors reported before proceeding.

---

<a name="step-4-test-locally"></a>
## Step 4: Test locally

Start the MCP server:

```bash
python mcp_server/server.py
```

Then in a browser console (or Node.js), call your chart:

```js
// Fetch the plugin from the running server
const res = await fetch('http://localhost:8000/sse'); // or use an MCP client
```

Or test the renderScript directly in a browser:

1. Open `data-explorer.html` in your browser.
2. Open the browser console and paste:

```js
const plugin = /* paste your plugin JSON here */;
const renderFn = new Function("return (" + plugin.renderScript + ")")();
const wrap = document.createElement('div');
wrap.style.cssText = 'width:600px;height:400px;border:1px solid #ccc';
document.body.appendChild(wrap);
renderFn(wrap, { /* your example spec */ });
```

---

## Step 5: Submit a PR

1. Fork the repo on GitHub.
2. Create a branch: `git checkout -b chart/YOUR_CHART_TYPE`
3. Add your plugin file.
4. Commit: `git commit -m "Add YOUR_CHART_TYPE chart plugin"`
5. Open a pull request against `main`.

In the PR description, include:
- A screenshot or description of what the chart looks like
- The library/CDN it depends on
- An example spec

---

## Plugin JSON schema reference

```json
{
  "type": "string — unique lowercase identifier",
  "promptDescription": "string — markdown snippet for LLM system prompts",
  "renderScript": "string — JS function(wrap, spec) { ... }"
}
```

All three fields are required. No other fields are used by the server.

---

## Tips

- **Keep renderScript minified or compact** — it's loaded into LLM context, so shorter is better.
- **Avoid external fetch calls** at render time; load everything via `<script>` tags.
- **Test with bad/empty spec values** to make sure the chart doesn't throw unhandled errors.
- Look at existing plugins like `chart_plugins/gauge.json` (simple, readable) or `chart_plugins/bar.json` (handles multiple datasets) as references.
