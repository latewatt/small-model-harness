"""Self-contained trace viewer: no server, dependencies or remote resources."""
import json
from pathlib import Path

TEMPLATE = r'''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Harness trace viewer</title>
<style>
:root{color-scheme:dark;font:15px system-ui;background:#10151d;color:#e1e7f0}body{max-width:1200px;margin:32px auto;padding:0 24px}h1{font-size:26px;margin-bottom:8px}.muted{color:#9eafc6}header{border-bottom:1px solid #334155;padding-bottom:24px}select,input,button{font:inherit;background:#1b2534;border:1px solid #465870;color:inherit;border-radius:6px;padding:9px;margin:6px 8px 6px 0}input[type=search]{width:280px}#summary{display:flex;gap:20px;flex-wrap:wrap;margin:22px 0}.stat{padding:16px 22px;background:#182332;border-radius:8px}.stat strong{display:block;font-size:25px;margin-top:4px}details{border:1px solid #334155;border-radius:7px;margin:9px 0;background:#131c28}summary{padding:12px;cursor:pointer;word-break:break-word}pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:14px;border-top:1px solid #334155;max-height:600px;overflow:auto;font:13px/1.6 ui-monospace,monospace}.bad{border-color:#b46c64}.good{color:#a8dfb4}a{color:#abd0ff}label{display:inline-block}#count{margin:12px 0;color:#9eafc6}</style>
<header><div class="muted">SMALL MODEL HARNESS / LOCAL EVIDENCE</div><h1 id="title">Trace viewer</h1><p class="muted">Measured task runs. Local mini-suite results are not Terminal-Bench scores.</p></header>
<div id="summary"></div><label>Task <select id="task"></select></label><label>Event <select id="event"><option value="">All events</option></select></label><input type="search" id="search" placeholder="Search trace text"><label>Open JSONL <input type="file" id="file" accept=".jsonl"></label><div id="count"></div><main id="events"></main>
<script id="data" type="application/json">__DATA__</script>
<script>
let data=JSON.parse(document.getElementById('data').textContent);
const $=id=>document.getElementById(id);
function init(){
 $('title').textContent=data.meta.run_id||'Imported trace';
 const s=data.meta.summary||{};$('summary').replaceChildren();
 for(const [label,value] of [['Passed',s.tasks===undefined?'—':`${s.passed}/${s.tasks}`],['Task wall time',s.task_wall_s===undefined?'—':`${s.task_wall_s.toFixed(2)}s`],['Input tokens',s.prompt_tokens??'unknown'],['Output tokens',s.completion_tokens??'unknown']]){
  const div=document.createElement('div');div.className='stat';div.textContent=label;const strong=document.createElement('strong');strong.textContent=value;div.append(strong);$('summary').append(div);
 }
 $('task').replaceChildren();for(const key of Object.keys(data.traces)){const o=document.createElement('option');o.value=key;o.textContent=key;$('task').append(o)}
 $('event').replaceChildren();for(const key of ['',...new Set(Object.values(data.traces).flat().map(x=>x.event))]){const o=document.createElement('option');o.value=key;o.textContent=key||'All events';$('event').append(o)}render();
}
function render(){
 const events=data.traces[$('task').value]||[];const q=$('search').value.toLowerCase();const kind=$('event').value;
 const selected=events.filter(e=>(!kind||e.event===kind)&&(!q||JSON.stringify(e).toLowerCase().includes(q)));
 $('count').textContent=`Showing ${selected.length} of ${events.length} events`;$('events').replaceChildren();
 for(const e of selected){const d=document.createElement('details');if(e.event.includes('error')||(e.event==='grade'&&!e.passed))d.className='bad';const head=document.createElement('summary');head.textContent=`${Number(e.elapsed_s||0).toFixed(2)}s · ${e.event}${e.tool?' · '+e.tool:''}${e.call?' · call '+e.call:''}`;const pre=document.createElement('pre');pre.textContent=JSON.stringify(e,null,2);d.append(head,pre);$('events').append(d)}
}
for(const id of ['task','event','search'])$(id).addEventListener('input',render);
$('file').addEventListener('change',async()=>{try{const f=$('file').files[0];if(!f)return;const rows=(await f.text()).trim().split('\n').filter(Boolean).map(JSON.parse);data={meta:{run_id:f.name},traces:{[f.name]:rows}};init()}catch(e){$('count').textContent='Invalid JSONL: '+e.message}});init();
</script></html>'''


def build_viewer(run: Path):
    data = {"meta": json.loads((run / "run.json").read_text()), "traces": {}}
    for trace in sorted(run.glob("*/trace.jsonl")):
        data["traces"][trace.parent.name] = [json.loads(line) for line in trace.read_text().splitlines()]
    # Escaping '<' prevents a model output containing </script> from executing.
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    path = run / "viewer.html"
    path.write_text(TEMPLATE.replace("__DATA__", payload))
    return path
