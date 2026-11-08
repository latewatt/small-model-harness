import json
from pathlib import Path

import pytest
from harness import ROOT
from harness.bench import digest_tree
from harness.report import report, taxonomy, verify_run
from harness.terminal import command
from harness.viewer import build_viewer


def fake_run(path):
    """Accounting fixture, never a scored run or an input to root RESULTS.md."""
    (path/'source').mkdir();(path/'source/agent.py').write_text('pass')
    (path/'task').mkdir()
    events=[{'event':'request'},{'event':'response','response':{'usage':{'prompt_tokens':11,'completion_tokens':3}}}, {'event':'grade','passed':False}]
    (path/'task/trace.jsonl').write_text('\n'.join(map(json.dumps,events)))
    row={'task':'task','calls':1,'prompt_tokens':11,'completion_tokens':3,'usage_complete':True,'passed':False,'wall_s':1.25}
    (path/'tasks.jsonl').write_text(json.dumps(row)+'\n')
    meta={'complete':True,'code_sha256':digest_tree(path/'source'),'summary':{'tasks':1,'passed':0,'pass_rate':0.0,'calls':1,'task_wall_s':1.25,'prompt_tokens':11,'completion_tokens':3}}
    (path/'run.json').write_text(json.dumps(meta))
    return row,meta


def test_artifact_accounting_and_tamper_detection(tmp_path):
    row,meta=fake_run(tmp_path)
    assert verify_run(tmp_path)[1][0]['completion_tokens']==3
    row['completion_tokens']=4
    (tmp_path/'tasks.jsonl').write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError,match='token mismatch'): verify_run(tmp_path)


def test_report_rejects_changed_source(tmp_path):
    fake_run(tmp_path)
    (tmp_path/'source/agent.py').write_text('changed')
    with pytest.raises(ValueError,match='source'): verify_run(tmp_path)


def test_viewer_does_not_execute_trace_html(tmp_path):
    fake_run(tmp_path)
    with (tmp_path/'task/trace.jsonl').open('a') as f:
        f.write('\n'+json.dumps({'event':'tool','output':'</script><script>alert(1)</script>'}))
    html=build_viewer(tmp_path).read_text()
    assert '</script><script>alert(1)' not in html
    assert '\\u003c/script>' in html


def test_terminal_selection_matches_exactly_fifteen_public_ids():
    argv=command('tb2-fast15')
    selected=[argv[i+1] for i,x in enumerate(argv[:-1]) if x=='-i']
    meta=json.loads((ROOT/'research/tb2-dataset-metadata.json').read_text())
    actual={t['org']+'/'+t['name'] for t in meta['task_ids']}
    assert len(selected)==len(set(selected))==15
    assert set(selected)<=actual
    assert 'terminal-bench/break-filter-js-from-html' not in selected
    full=command('tb2-full')
    assert '-i' not in full and full[full.index('-k')+1]=='5'


def test_ablation_report_is_derived_from_individual_saved_runs(tmp_path):
    run=tmp_path/'runs'/'synthetic-unit-fixture';run.mkdir(parents=True)
    row,meta=fake_run(run)
    row.update(exit_status='format_budget')
    (run/'tasks.jsonl').write_text(json.dumps(row)+'\n')
    events=[json.loads(s) for s in (run/'task/trace.jsonl').read_text().splitlines()]
    events[0]['payload']={}
    events.insert(0,{'event':'variant','features':['repair']})
    events.extend([{'event':'parse_error'},{'event':'parse_error'},
                   {'event':'tool_error'},{'event':'syntax_rejected'}])
    (run/'task/trace.jsonl').write_text('\n'.join(map(json.dumps,events)))
    meta.update(agent='v0-repair',features=['repair'],phase=2,subset='mini10',model='synthetic-unit-fixture',
                model_identity={'digest':'synthetic'},suite_sha256='synthetic',steps=16,
                task_timeout_s=600,max_tokens=1024,temperature=0,seed=17,started_at='unit fixture',
                experiment={'frozen_core_sha256':meta['code_sha256']})
    meta['summary']['job_wall_s']=1.5
    (run/'run.json').write_text(json.dumps(meta))
    generated=report(tmp_path).read_text()
    assert '## Ablation table' in generated and 'v0-repair' in generated
    assert '| repair | 0 / 1 | 0.0% | 1.25 | 11 | 3 | 1 |' in generated
    assert taxonomy(run,[row])['parse']==2
    assert taxonomy(run,[row])['syntax']==1
    assert taxonomy(run,[row])['format_exit']==1
    events[1]['payload']['response_format']={}
    (run/'task/trace.jsonl').write_text('\n'.join(map(json.dumps,events)))
    with pytest.raises(ValueError,match='feature mismatch'): verify_run(run)
