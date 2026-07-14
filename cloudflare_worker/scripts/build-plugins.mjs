// Bundles chart_plugins/*.json into src/plugins.json so the Worker (which has no
// filesystem at runtime) can serve them. Mirrors load_plugins() in
// ../../mcp_server/server.py: sorted, skips files starting with "_", requires a "type".
import { readdirSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pluginsDir = resolve(here, "../../chart_plugins");
const outFile = resolve(here, "../src/plugins.json");

const plugins = {};
let skipped = 0;
for (const file of readdirSync(pluginsDir).sort()) {
  if (!file.endsWith(".json") || file.startsWith("_")) continue;
  try {
    const p = JSON.parse(readFileSync(join(pluginsDir, file), "utf-8"));
    if (p && typeof p === "object" && "type" in p) {
      plugins[p.type] = p;
    } else {
      skipped++;
    }
  } catch (err) {
    skipped++;
    console.warn(`skip ${file}: ${err.message}`);
  }
}

mkdirSync(dirname(outFile), { recursive: true });
writeFileSync(outFile, JSON.stringify(plugins));
console.log(`Bundled ${Object.keys(plugins).length} plugins -> src/plugins.json${skipped ? ` (${skipped} skipped)` : ""}`);
