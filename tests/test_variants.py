import io
import json
import time

import pytest

from harness.client import Client, ModelConfig
from harness.protocol import parse_action
from harness.sandbox import Sandbox
from harness.trace import Trace
from harness.variants import (ACTION_FORMAT, AlignedSandbox, FEATURES, features_for,
                              repair_feedback, requirement_check, run_variant,
                              workspace_version)


def test_features_are_isolated_and_combinations_explicit():
    for name in FEATURES:
        assert features_for('v0-' + name) == {name}
    assert features_for('combo-constrained-repair') == {'constrained', 'repair'}
    with pytest.raises(ValueError): features_for('combo-repair-repair')
    with pytest.raises(ValueError): features_for('combo-repair-mystery')


def test_structured_output_reaches_endpoint_without_budget_changes(tmp_path, monkeypatch):
    seen = []
    def fake(req, timeout):
        seen.append(json.loads(req.data))
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': '{"tool":"finish","args":{"message":"done"}}'}}],
                                     'usage': {'prompt_tokens': 7, 'completion_tokens': 5}}).encode())
    monkeypatch.setattr('urllib.request.urlopen', fake)
    client = Client(ModelConfig('test'), Trace(tmp_path/'trace.jsonl'), time.monotonic()+10)
    client.query([{'role':'user','content':'synthetic'}], response_format=ACTION_FORMAT)
    assert seen[0]['response_format'] == ACTION_FORMAT
    assert seen[0]['max_tokens']==1024 and seen[0]['temperature']==0 and seen[0]['seed']==17
    assert client.stats()['completion_tokens']==5


def test_repair_is_specific_and_changes_on_repeat():
    bad='{"tool":"read","args":{"path":"toy.py","start":0,"lines":900}}'
    first, example=repair_feedback(bad,'start must be positive',1)
    second, again=repair_feedback(bad,'start must be positive',2)
    assert example['tool']=='read' and example['args']=={'path':'toy.py','start':1,'lines':200}
    assert parse_action(json.dumps(example))[0]==example
    assert first!=second and example==again
    assert '"tool": "shell"' not in first and '"tool": "finish"' not in first
    feedback, example=repair_feedback('{"tool":"patch","args":{"path":"toy.py"}}','missing fields',1)
    assert example['tool']=='patch' and set(example['args'])=={'path','old','new'}


def test_raw_read_preserves_newlines_and_patch_rejects_syntax_without_mutation(tmp_path):
    trace=Trace(tmp_path/'trace.jsonl'); box=AlignedSandbox(tmp_path/'work',trace)
    box.patch('toy.py','','def triple(x):\n    return x * 3\n')
    read=box.read('toy.py',start=2,lines=1)
    assert read['code']=='    return x * 3\n' and read['start_line']==2
    original=(box.work/'toy.py').read_bytes()
    with pytest.raises(ValueError,match='syntax check'):
        box.patch('toy.py','return x * 3','return (')
    assert (box.work/'toy.py').read_bytes()==original
    with pytest.raises(ValueError,match='syntax check'): box.patch('new.py','','return 5\n')
    assert not (box.work/'new.py').exists()
    box.patch('notes.txt','','this is not python: (')
    assert sum(e['event']=='syntax_rejected' for e in trace.events)==2


def test_file_version_changes_only_after_target_mutation(tmp_path):
    box=Sandbox(tmp_path/'work');box.patch('toy.py','','n = 3\n')
    action={'tool':'read','args':{'path':'toy.py'}}
    before=workspace_version(box,action)
    box.read('toy.py')
    assert workspace_version(box,action)==before
    box.patch('other.txt','','other')
    assert workspace_version(box,action)==before
    box.patch('toy.py','n = 3','n = 4')
    assert workspace_version(box,action)!=before


def test_requirement_gate_rejects_invented_quotes_and_failing_checks(tmp_path):
    trace=Trace(tmp_path/'trace.jsonl');box=Sandbox(tmp_path/'work',trace)
    task='Create toy.py. Define triple(x) to return three times x.'
    box.patch('toy.py','','def triple(x):\n    return x * 3\n')
    plan=[{'quote':'return three times x','check':'assert triple(4) == 12'}]
    box.patch('.agent-requirements.json','',json.dumps(plan))
    box.patch('.agent-selftest.py','','from toy import triple\nassert triple(4) == 12\n')
    assert requirement_check(task,box,trace)[0]
    box.patch('.agent-selftest.py','== 12','== 15')
    assert not requirement_check(task,box,trace)[0]
    box.patch('.agent-requirements.json','three times x','four times x')
    passed,result=requirement_check(task,box,trace)
    assert not passed and 'not present in the task' in result['exception_info']


class ScriptedClient:
    def __init__(self, actions):
        self.actions=iter(actions);self.deadline=time.monotonic()+30;self.calls=0
    def query(self,messages,**kwargs):
        self.calls+=1
        return {'choices':[{'message':{'content':json.dumps(next(self.actions))},'finish_reason':'stop'}]}


def test_version_guard_allows_rereads_after_edits_but_stops_unchanged_loop(tmp_path):
    def action(tool,**args):return {'tool':tool,'args':args}
    box=Sandbox(tmp_path/'work');box.patch('toy.py','','n=0\n')
    actions=[]
    for number in range(4):
        actions += [action('read',path='toy.py'), action('patch',path='toy.py',old=f'n={number}',new=f'n={number+1}')]
    actions.append(action('finish',message='done'))
    trace=Trace(tmp_path/'changing.jsonl')
    assert run_variant('synthetic',ScriptedClient(actions),box,trace,16,{'versions'})=='submitted'
    trace=Trace(tmp_path/'unchanged.jsonl')
    client=ScriptedClient([action('read',path='toy.py')]*5)
    assert run_variant('synthetic',client,box,trace,16,{'versions'})=='loop_budget'
    assert client.calls==4


def test_phase2_refuses_budget_model_and_source_drift(tmp_path,monkeypatch):
    from harness import experiment
    from harness.bench import digest_tree
    config=ModelConfig('synthetic');suite=tmp_path/'suite';suite.mkdir()
    (suite/'toy.txt').write_text('synthetic fixture')
    fixed={'model':'synthetic','model_digest':'digest','suite_sha256':digest_tree(suite),
           'subset':'mini10','steps':16,'task_timeout_s':600,'max_tokens':1024,
           'temperature':0,'seed':17,'base_url':config.base_url,'request_timeout_s':90}
    spec={'fixed':fixed,'frozen_core_sha256':'frozen','reference_run':'unit-fixture','selection_policy':'unit-fixture'}
    (tmp_path/'research').mkdir()
    (tmp_path/'research/phase2-experiment.json').write_text(json.dumps(spec))
    monkeypatch.setattr(experiment,'ROOT',tmp_path)
    monkeypatch.setattr(experiment,'core_digest',lambda:'frozen')
    monkeypatch.delenv('HARNESS_REASONING_EFFORT',raising=False)
    assert experiment.validate_experiment(config,{'digest':'digest'},suite,'mini10',16,600,{'repair'})['features']==['repair']
    with pytest.raises(ValueError,match='steps'):
        experiment.validate_experiment(config,{'digest':'digest'},suite,'mini10',17,600,{'repair'})
    with pytest.raises(ValueError,match='model_digest'):
        experiment.validate_experiment(config,{'digest':'changed'},suite,'mini10',16,600,{'repair'})
    monkeypatch.setattr(experiment,'core_digest',lambda:'changed')
    with pytest.raises(ValueError,match='core changed'):
        experiment.validate_experiment(config,{'digest':'digest'},suite,'mini10',16,600,{'repair'})
