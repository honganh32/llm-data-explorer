import json, os

os.chdir(r'e:\multi-agent\llm-data-explorer')

with open('data-explorer.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract renderDynet3D body (between function declaration and Chart registry comment)
start_marker = 'function renderDynet3D(wrap, spec) {'
end_marker = '\n// ── Chart registry ──'

func_start = content.index(start_marker)
func_end = content.index(end_marker)
func_text = content[func_start:func_end].rstrip()

# Strip the function declaration and closing brace
body = func_text[len(start_marker):]
body = body.rstrip()
if body.endswith('}'):
    body = body[:-1]

# Replace palette const with inlined colors
old_palette = "  const palette = (typeof CHART_COLORS !== 'undefined' && CHART_COLORS.length)\n    ? CHART_COLORS\n    : ['#534AB7', '#E85858', '#2E9CDB', '#27AE60', '#F2994A', '#9B51E0', '#56CCF2', '#F2C94C'];"
new_palette = "  var palette = ['#534AB7','#7F77DD','#2E9CDB','#4BC1A8','#E8833A','#E85858','#9B59B6','#27AE60','#F39C12','#1ABC9C','#3498DB','#E74C3C','#2ECC71','#F1C40F','#8E44AD'];"
body = body.replace(old_palette, new_palette)

# Find bounds of panel HTML section to replace
panel_start_marker = "  const visualizingOptions = ["
panel_end_marker = "  panel.querySelector('[data-out=\"totalLinks\"]').textContent = totalLinks;"

p_start = body.index(panel_start_marker)
p_end = body.index(panel_end_marker) + len(panel_end_marker)

# DOM API replacement for the panel construction (no HTML strings / no double quotes)
new_panel = """  var iStyle = 'font-size:11px;padding:2px 4px;background:var(--bg,#fff);color:var(--text,#000);border:0.5px solid var(--border2,#ccc);border-radius:3px;';
  function makeRow(lbl,ctrlEl){var d=document.createElement('div');d.style.cssText='display:flex;justify-content:space-between;align-items:center;padding:3px 0;gap:8px;';var sp=document.createElement('span');sp.style.color='var(--text2,#666)';sp.textContent=lbl;d.appendChild(sp);if(ctrlEl instanceof Element){d.appendChild(ctrlEl);}else{var s2=document.createElement('span');s2.style.fontWeight='500';s2.textContent=String(ctrlEl);d.appendChild(s2);}return d;}
  function makeCb(key){var inp=document.createElement('input');inp.type='checkbox';inp.dataset.key=key;return inp;}
  function makeSel(key,opts){var se=document.createElement('select');se.dataset.key=key;se.style.cssText=iStyle;opts.forEach(function(o){var op=document.createElement('option');op.value=o.v;op.textContent=o.l;se.appendChild(op);});return se;}
  function makeRng(key,min,max,step,val){var inp=document.createElement('input');inp.type='range';inp.dataset.key=key;inp.min=min;inp.max=max;inp.step=step;inp.value=val;inp.style.width='110px';return inp;}
  function makeSect(text){var d=document.createElement('div');d.style.cssText='font-size:10px;color:var(--text3,#999);text-transform:uppercase;letter-spacing:0.05em;margin:10px 0 4px;';d.textContent=text;return d;}
  var ptitle=document.createElement('div');ptitle.style.cssText='font-weight:600;font-size:12px;margin-bottom:8px;color:var(--text,#000);';ptitle.textContent='Control panel';panel.appendChild(ptitle);
  panel.appendChild(makeSect('Input'));
  if(nodeTypes.length>1){panel.appendChild(makeRow('Visualizing',makeSel('visualizing',[{v:'all',l:'All'}].concat(nodeTypes.map(function(typ){return{v:String(typ),l:String(typ)};})))));}
  var tsEl=document.createElement('span');tsEl.style.fontWeight='500';tsEl.textContent=T;panel.appendChild(makeRow('# Time-steps',tsEl));
  panel.appendChild(makeSect('Settings'));
  panel.appendChild(makeRow('Show Variations',makeCb('showVariations')));
  panel.appendChild(makeRow('Show timelines',makeCb('showTimelines')));
  panel.appendChild(makeRow('Show users',makeCb('showUsers')));
  panel.appendChild(makeRow('Show nodes',makeCb('showNodes')));
  panel.appendChild(makeRow('Show labels',makeCb('showLabels')));
  panel.appendChild(makeRow('Show time labels',makeCb('showTimeLabels')));
  panel.appendChild(makeRow('Labels near camera',makeCb('labelsNearOnly')));
  panel.appendChild(makeRow('Label cutoff',makeRng('labelNearDist',0.1,2,0.05,state.labelNearDist)));
  panel.appendChild(makeRow('Node size',makeRng('nodeSize',0.2,4,0.1,state.nodeSize)));
  panel.appendChild(makeRow('Label size',makeRng('labelSize',0.3,3,0.1,state.labelSize)));
  panel.appendChild(makeRow('Max node labels',makeRng('maxNodeLabels',0,Math.max(50,allNodes.length),1,state.maxNodeLabels)));
  panel.appendChild(makeRow('Link type',makeSel('linkType',[{v:'straight',l:'Straight'},{v:'curved',l:'Curved'}])));
  panel.appendChild(makeRow('Link opacity',makeRng('linkOpacity',0,1,0.05,state.linkOpacity)));
  panel.appendChild(makeRow('Network Expand',makeRng('networkExpand',10,1200,10,state.networkExpand)));
  panel.appendChild(makeRow('Time Resolution',makeSel('timeResolution',[{v:'1',l:'1x'},{v:'2',l:'2x'},{v:'3',l:'3x'},{v:'5',l:'5x'}])));
  panel.appendChild(makeSect('Output'));
  var tnEl=document.createElement('span');tnEl.dataset.out='totalNodes';tnEl.style.fontWeight='500';panel.appendChild(makeRow('Total nodes',tnEl));
  var tlEl=document.createElement('span');tlEl.dataset.out='totalLinks';tlEl.style.fontWeight='500';panel.appendChild(makeRow('Total links',tlEl));
  var searchInp=document.createElement('input');searchInp.type='text';searchInp.placeholder='Search e.g. node1';searchInp.dataset.key='searchTerm';searchInp.style.cssText='width:100%;margin-top:10px;padding:5px 8px;'+iStyle;panel.appendChild(searchInp);
  if(linkCatList.length){var catHdr=document.createElement('div');catHdr.style.cssText='display:flex;justify-content:space-between;align-items:baseline;margin:10px 0 4px;';var catTitle2=document.createElement('span');catTitle2.style.cssText='font-size:10px;color:var(--text3,#999);text-transform:uppercase;letter-spacing:0.05em;';catTitle2.textContent='Link types';var catToggleEl=document.createElement('a');catToggleEl.id='dyn-legend-toggle';catToggleEl.textContent='Hide all';catToggleEl.style.cssText='cursor:pointer;color:var(--accent,#534AB7);font-size:10px;user-select:none;';catHdr.appendChild(catTitle2);catHdr.appendChild(catToggleEl);panel.appendChild(catHdr);var legendDivEl=document.createElement('div');legendDivEl.id='dyn-legend';legendDivEl.style.cssText='display:flex;flex-wrap:wrap;gap:3px 8px;';linkCatList.forEach(function(c){var cSpan=document.createElement('span');cSpan.dataset.cat=String(c);cSpan.style.cssText='display:inline-flex;align-items:center;gap:4px;cursor:pointer;user-select:none;font-size:10px;';var swatch=document.createElement('span');swatch.style.cssText='display:inline-block;width:10px;height:10px;border-radius:2px;background:'+catColor.get(c)+';';cSpan.appendChild(swatch);cSpan.appendChild(document.createTextNode(c));legendDivEl.appendChild(cSpan);});panel.appendChild(legendDivEl);}
  var totalLinks=snapshots.reduce(function(acc,s){return acc+s.links.length;},0);
  tnEl.textContent=allNodes.length;
  tlEl.textContent=totalLinks;"""

body = body[:p_start] + new_panel + body[p_end:]

# Verify no double quotes remain (they'd cause JSON escaping issues if unexpected)
dq_count = body.count('"')
print(f"Double quotes remaining in body: {dq_count}")
if dq_count > 0:
    # Find context around each double quote
    idx = 0
    found = 0
    while found < 5:
        pos = body.find('"', idx)
        if pos == -1:
            break
        print(f"  at pos {pos}: ...{repr(body[max(0,pos-30):pos+30])}...")
        idx = pos + 1
        found += 1

# Wrap in CDN-loading outer function
render_script = (
    'function(wrap,spec){'
    'function loadScript(url,cb){if(url.indexOf(\'OrbitControls\')>=0&&typeof THREE!==\'undefined\'&&typeof THREE.OrbitControls===\'function\'&&THREE.OrbitControls.prototype){cb();return;}if(url.indexOf(\'d3\')>=0&&typeof d3!==\'undefined\'){cb();return;}if(url.indexOf(\'build/three\')>=0&&typeof THREE!==\'undefined\'&&typeof THREE.Scene===\'function\'){cb();return;}for(var i=0;i<document.scripts.length;i++){if(document.scripts[i].src.indexOf(url)>=0){if(document.scripts[i]._ld){cb();return;}document.scripts[i].addEventListener(\'load\',cb);return;}}var s=document.createElement(\'script\');s.src=url;s.onload=function(){s._ld=true;cb();};document.head.appendChild(s);}'
    'loadScript(\'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js\',function(){'
    'loadScript(\'https://cdn.jsdelivr.net/npm/three@0.131.0/build/three.min.js\',function(){'
    'loadScript(\'https://cdn.jsdelivr.net/npm/three@0.131.0/examples/js/controls/OrbitControls.js\',function(){'
    + body +
    '});});});}'
)

prompt_desc = (
    '- **dynet3d** — 3D dynamic-network visualization. Each time step renders as a parallel 2D network '
    'plane stacked along the z-axis; same-id nodes are connected across slices to form entity timelines. '
    'Drag to orbit, scroll to zoom; Reset to Front view collapses to 2D; Side view exposes the time axis. '
    'Best for showing how a network evolves over time. '
    'Spec (lazy SQL form): { "type":"dynet3d", "title":"...", "sql":"SELECT day::text AS time, src_ip AS source, dst_ip AS target, attack_type AS category, COUNT(*) AS value FROM events GROUP BY day, src_ip, dst_ip, attack_type ORDER BY day" }. '
    'Spec (inline snapshots form): { "type":"dynet3d", "title":"...", "timeLabels":["Jan","Feb"], '
    '"nodes":[{"id":"u1","name":"Alice","type":"user"}], '
    '"snapshots":[{"time":"Jan","links":[{"source":"u1","target":"r1","value":5}]}] }. '
    'Spec (flat events form — preferred when data is a list of timestamped edges): '
    '{ "type":"dynet3d", "title":"...", "events":[{"year":2023,"source":"Alice","target":"Bob","category":"collab","value":1}] }. '
    'The events form accepts year/time/period/date/month as the time key, source/src/from and target/dst/to as endpoints, '
    'category/type for link color, value/count for weight. '
    'Recognised columns: time (or period/date/day/month), source (or src/from), target (or dst/to), '
    'optional value/count, optional category/type (link color), optional source_type/target_type. '
    'IMPORTANT — do not write custom Three.js rendering code. Always produce a spec object and pass it to '
    'the renderScript. If you must reference OrbitControls in any standalone Three.js snippet, use '
    'THREE.OrbitControls (not a bare OrbitControls global) — the Three.js r131 examples/js build attaches '
    'it to the THREE namespace.'
)

plugin = {
    'type': 'dynet3d',
    'promptDescription': prompt_desc,
    'renderScript': render_script,
}

out_path = r'chart_plugins/dynet3d.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(plugin, f, ensure_ascii=False)

size = os.path.getsize(out_path)
print(f"Written {out_path} ({size:,} bytes)")
