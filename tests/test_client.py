import io
import json
import time
import urllib.error
from dataclasses import replace

import pytest
from harness.client import Client, ModelConfig, APIError, BudgetExceeded
from harness.trace import Trace


def response(usage=True):
    data={"id":"test","choices":[{"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}
    if usage: data['usage']={'prompt_tokens':13,'completion_tokens':7,'total_tokens':20}
    return io.BytesIO(json.dumps(data).encode())


def test_usage_measures_all_calls_without_leaking_key(tmp_path,monkeypatch):
    trace=Trace(tmp_path/'trace.jsonl');client=Client(ModelConfig('test'),trace,time.monotonic()+10)
    seen=[]
    def query(req,timeout):
        seen.append(json.loads(req.data))
        assert req.get_header('Authorization')=='Bearer secret-for-test'
        return response()
    monkeypatch.setenv('HARNESS_API_KEY','secret-for-test')
    monkeypatch.setattr('urllib.request.urlopen',query)
    client.query([{'role':'user','content':'hello','extra':{'secret':'metadata'}}])
    client.query([{'role':'user','content':'repair'}])
    assert client.stats()['prompt_tokens']==26 and client.stats()['completion_tokens']==14
    assert client.calls==2 and client.http_attempts==2
    assert 'extra' not in seen[0]['messages'][0]
    assert 'secret-for-test' not in trace.path.read_text()


def test_missing_usage_is_unknown_not_estimated(tmp_path,monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen',lambda *a,**k:response(False))
    client=Client(ModelConfig('test'),Trace(tmp_path/'t.jsonl'),time.monotonic()+10)
    client.query([{'role':'user','content':'hello'}])
    assert client.stats()['prompt_tokens'] is None
    assert not client.stats()['usage_complete']


def test_http_retry_is_bounded_and_accounting_marks_uncertainty(tmp_path,monkeypatch):
    calls=[]
    def query(*a,**k):
        calls.append(1)
        if len(calls)==1: raise urllib.error.HTTPError('http://local',503,'unavailable',{},None)
        return response()
    monkeypatch.setattr('urllib.request.urlopen',query)
    monkeypatch.setattr('time.sleep',lambda _:None)
    client=Client(ModelConfig('test'),Trace(tmp_path/'t.jsonl'),time.monotonic()+10)
    client.query([{'role':'user','content':'hello'}])
    assert client.http_attempts==2 and client.calls==1
    assert client.stats()['prompt_tokens'] is None
    assert client.stats()['observed_prompt_tokens']==13


def test_deadline_prevents_request(tmp_path,monkeypatch):
    def no_request(*a,**k): raise AssertionError('expired request sent')
    monkeypatch.setattr('urllib.request.urlopen',no_request)
    client=Client(ModelConfig('test'),Trace(tmp_path/'t.jsonl'),time.monotonic()-1)
    with pytest.raises(BudgetExceeded): client.query([])


def test_timeout_is_not_retried_and_usage_unknown(tmp_path,monkeypatch):
    def timeout(*a,**k): raise TimeoutError()
    monkeypatch.setattr('urllib.request.urlopen',timeout)
    client=Client(ModelConfig('test'),Trace(tmp_path/'t.jsonl'),time.monotonic()+10)
    with pytest.raises(APIError): client.query([])
    assert client.http_attempts==1 and not client.stats()['usage_complete']
