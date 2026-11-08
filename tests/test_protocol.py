import json
import pytest

from harness.protocol import ParseError, parse_action
from harness.trace import Trace
from harness.v0 import compact, truncate, run_v0


@pytest.mark.parametrize("content", [
    '{}', '[]', '{"tool":"shell","args":{"command":3}}',
    '{"tool":"read","args":{"path":"a","lines":true}}',
    '{"tool":"read","args":{"path":"a","start":0}}',
    '{"tool":"read","args":{"path":"a","lines":201}}',
    '{"tool":"delete","args":{}}',
    '{"tool":"shell","args":{"command":"ls","unexpected":1}}',
    '{"tool":"shell","tool":"finish","args":{"message":"done"}}',
    '{"tool":"shell","args":{"command":"ls"}} {}',
    'prefix {"tool":"shell","args":{"command":"ls"}}',
    '{"tool":"shell","args":{"command":NaN}}',
])
def test_ambiguous_or_wrong_actions_never_execute(content):
    with pytest.raises(ParseError): parse_action(content)


def test_only_safe_format_repair():
    action, repaired = parse_action('```json\n{"tool":"shell","args":{"command":"echo ok"}}\n```')
    assert repaired and action["args"]["command"] == "echo ok"
    with pytest.raises(ParseError):
        parse_action('{"tool":"shell","args":{"command":"echo ok",}}')


def test_context_budget_keeps_task_and_bounds_unicode(tmp_path):
    trace = Trace(tmp_path / "trace.jsonl")
    original = [{"role":"system","content":"system"},{"role":"user","content":"important task"}]
    history = original + [{"role":"user","content":"é"*8000} for _ in range(8)]
    out = compact(history, trace)
    assert out[:2] == original
    assert sum(len(m["content"].encode())+32 for m in out) <= 6000
    assert trace.events[-1]["event"] == "context_compacted"
    assert len(truncate("😀"*10000).encode()) <= 2400


def test_format_errors_consume_steps_and_do_not_execute(tmp_path):
    import time
    class Fake:
        deadline = time.monotonic() + 10
        calls = 0
        def query(self, messages):
            self.calls += 1
            return {"choices":[{"message":{"content":"not json"}}]}
    class NeverExecute:
        def run(self, **kwargs): raise AssertionError("must not execute")
    fake = Fake()
    assert run_v0("test", fake, NeverExecute(), Trace(tmp_path/'t.jsonl'), 2) == "step_budget"
    assert fake.calls == 2


def test_retry_can_recover_then_submit(tmp_path):
    import time
    class Fake:
        deadline = time.monotonic() + 10
        outputs = iter(['{bad', '{"tool":"finish","args":{"message":"done"}}'])
        def query(self, messages):
            return {"choices":[{"message":{"content":next(self.outputs)}}]}
    trace = Trace(tmp_path/'t.jsonl')
    assert run_v0("test",Fake(),None,trace,3)=="submitted"
    assert len([e for e in trace.events if e["event"]=="parse_error"])==1
