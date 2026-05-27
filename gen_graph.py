import json, os, sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

os.chdir(r'e:\multi-agent\llm-data-explorer')

with open('data-explorer.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract graph helpers + renderGraph (lines 663-2209)
graph_start = content.index('// ── Graph grouping helpers ──')
plotly_start = content.index('\nfunction renderPlotly(')
graph_body = content[graph_start:plotly_start].rstrip()

# Check double quotes
dq_count = graph_body.count('"')
print(f'Double quotes in graph body: {dq_count}')
idx = 0
for _ in range(dq_count):
    pos = graph_body.find('"', idx)
    if pos == -1: break
    line_no = graph_body[:pos].count('\n') + 663
    ctx = graph_body[max(0,pos-50):pos+60].replace('\n', ' ')
    print(f'  line ~{line_no}: {ctx}')
    idx = pos + 1

# Replace CHART_COLORS reference in renderGraph
old_ref = 'buildHierarchicalGroups(allNodes, links, CHART_COLORS, activeGroupMethod)'
new_ref = 'buildHierarchicalGroups(allNodes, links, _C, activeGroupMethod)'
graph_body = graph_body.replace(old_ref, new_ref)

# Also replace other CHART_COLORS references
chart_colors_count = graph_body.count('CHART_COLORS')
print(f'CHART_COLORS references: {chart_colors_count}')
if chart_colors_count > 0:
    idx2 = 0
    for _ in range(chart_colors_count):
        pos2 = graph_body.find('CHART_COLORS', idx2)
        if pos2 == -1: break
        line_no2 = graph_body[:pos2].count('\n') + 663
        ctx2 = graph_body[max(0,pos2-30):pos2+50].replace('\n',' ')
        print(f'  CHART_COLORS at line ~{line_no2}: {ctx2}')
        idx2 = pos2 + 1
# Replace remaining CHART_COLORS
graph_body = graph_body.replace('CHART_COLORS', '_C')

# Also replace getThemeColors() calls
graph_body = graph_body.replace('getThemeColors()', '_getT()')

# Wrap in self-contained function with CDN loaders and helper definitions
render_script = (
    'function(wrap,spec){'
    "var _C=['#534AB7','#7F77DD','#2E9CDB','#4BC1A8','#E8833A','#E85858','#9B59B6','#27AE60','#F39C12','#1ABC9C','#3498DB','#E74C3C','#2ECC71','#F1C40F','#8E44AD'];"
    "function _getT(){return{text:'#1a1a18',text2:'#5a5a56',grid:'rgba(0,0,0,0.06)',edge:'rgba(30,30,30,0.4)'}; }"
    "function loadScript(url,cb){for(var i=0;i<document.scripts.length;i++){if(document.scripts[i].src.indexOf(url)>=0){if(document.scripts[i]._ld){cb();return;}document.scripts[i].addEventListener('load',cb);return;}}var s=document.createElement('script');s.src=url;s.onload=function(){s._ld=true;cb();};document.head.appendChild(s);}"
    "loadScript('https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js',function(){"
    "loadScript('https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js',function(){"
    + graph_body +
    '});});}'
)

print(f'\nDouble quotes in final renderScript: {render_script.count(chr(34))}')
print(f'renderScript length: {len(render_script):,} chars')

prompt_desc = (
    '- **graph** — network/relationship diagram with nodes and edges. Set `directed:true` for arrows. '
    'Optional `curved:true` for arc edges. Nodes support optional `size` (px) and `color` (hex). '
    'Links support optional `label` (edge text), `color` (hex), and `value` (numeric weight — thickness scales proportionally). '
    'Spec: { "type":"graph", "title":"...", "directed":true, "layout":"force", '
    '"nodes":[{"id":"1","name":"Node A"},{"id":"2","name":"Node B","size":50,"color":"#e05c5c"}], '
    '"links":[{"source":"1","target":"2","label":"conn","value":5,"color":"#e05c5c"}] }. '
    'Use `layout:"circular"` for ring topology. Node ids in links must match node id values exactly. '
    'Render-side: nodes sharing identical (partner, label) sets auto-collapse into a group node; '
    'degree-1 nodes sharing the same single partner auto-collapse into a Leaves node. Click to expand.'
)

plugin = {
    'type': 'graph',
    'promptDescription': prompt_desc,
    'renderScript': render_script,
}

out_path = r'chart_plugins/graph.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(plugin, f, ensure_ascii=False)

size = os.path.getsize(out_path)
print(f'Written {out_path} ({size:,} bytes)')
