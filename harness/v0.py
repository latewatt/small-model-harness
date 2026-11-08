"""A small, deliberately inspectable agent loop."""
import json
import time
from collections import Counter

from .client import HarnessError
from .protocol import ParseError, parse_action

SYSTEM = '''You are a coding agent working inside a task workspace on macOS.
Solve the user's task by inspecting files, making changes, and testing them.
Every reply must be exactly ONE JSON object, with no prose or Markdown:
{"tool":"shell","args":{"command":"ls -la"}}
Available tools:
shell: {"command":string} -- bash command, 12 second timeout, fresh shell in workspace.
read: {"path":string,"start":integer optional,"lines":integer optional} -- numbered lines.
patch: {"path":string,"old":string,"new":string} -- replace exactly one occurrence. Read first. For a NEW file only, use old="".
search: {"query":string,"path":string optional} -- literal recursive text search.
finish: {"message":string} -- submit files for grading and stop.
The args wrapper is REQUIRED for EVERY tool, including finish:
{"tool":"finish","args":{"message":"Implemented and tested the changes."}}
Paths must be relative to the workspace. Python 3 and standard library are installed.
Network access is disabled. Only workspace writes are allowed. Hidden tests are unavailable.
Escape quotes and newlines in JSON strings. Do not put multiple actions in one reply.
Run a focused check before finish. Do not merely describe a solution: edit the files.
'''


def cut_bytes(text: str, limit: int) -> str:
    return text.encode()[:limit].decode("utf-8", "ignore")


def truncate(text: str, limit: int = 2400) -> str:
    raw = text.encode()
    if len(raw) <= limit:
        return text
    marker = f"\n[observation truncated: {len(raw)} bytes; use selective read/search]\n"
    half = (limit - len(marker.encode())) // 2
    return raw[:half].decode("utf-8", "ignore") + marker + raw[-half:].decode("utf-8", "ignore")


def compact(messages: list[dict], trace, limit: int = 6000):
    """Deterministic extractive memory; no second LLM or hidden token usage.

    UTF-8 byte count is a conservative input-size guard, not a token metric.
    Always retains the system prompt and task; evicted actions/observations are
    represented in a bounded ledger. Recent messages stay chronological.
    """
    size = lambda ms: sum(len((m.get("content") or "").encode()) + 32 for m in ms)
    if size(messages) <= limit:
        return messages
    original_size = size(messages)
    fixed, history = messages[:2], messages[2:]
    memory = []
    while history and size(fixed + history) > limit - 1000:
        item = history.pop(0)
        memory.append(f"{item['role']}: {cut_bytes(item.get('content') or '', 180)}")
    summary = "Earlier activity (extractive, may omit details):\n" + cut_bytes("\n".join(memory[-5:]), 900)
    result = fixed + [{"role": "user", "content": summary}] + history
    while history and size(result) > limit:
        history.pop(0)
        result = fixed + [{"role": "user", "content": summary}] + history
    if size(result) > limit:
        raise HarnessError("system/task exceeds context byte budget")
    trace.emit("context_compacted", before_bytes=original_size, after_bytes=size(result), summary=summary)
    return result


def run_v0(task: str, client, sandbox, trace, steps: int):
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task}]
    repeated = Counter()
    format_streak = 0
    exit_status = "step_budget"
    for step in range(1, steps + 1):
        if time.monotonic() >= client.deadline:
            return "time_budget"
        messages = compact(messages, trace)
        response = client.query(messages)
        content = response["choices"][0]["message"].get("content") or ""
        messages.append({"role": "assistant", "content": content})
        try:
            action, repaired = parse_action(content)
            if response["choices"][0].get("finish_reason") == "length":
                raise ParseError("output token limit reached; shorten the action")
        except ParseError as exc:
            format_streak += 1
            trace.emit("parse_error", step=step, error=str(exc), response=content)
            messages.append({"role": "user", "content": f'FORMAT ERROR: {exc}. Nothing was executed. Every tool needs an args object. Example shell: {{"tool":"shell","args":{{"command":"ls"}}}}. Example finish: {{"tool":"finish","args":{{"message":"done"}}}}. Correct your previous action and retry.'})
            if format_streak >= 3:
                return "format_budget"
            continue
        format_streak = 0
        trace.emit("action", step=step, action=action, repaired=repaired)
        if action["tool"] == "finish":
            return "submitted"
        signature = json.dumps(action, sort_keys=True)
        repeated[signature] += 1
        if repeated[signature] >= 4:
            trace.emit("loop_detected", step=step, action=action)
            return "loop_budget"
        if repeated[signature] == 3:
            messages.append({"role": "user", "content": "This identical action has repeated. Change your approach; one more identical action will end the task."})
        try:
            tool, args = action["tool"], action["args"]
            if tool == "shell":
                result = sandbox.run(**args)
            elif tool == "search":
                result = sandbox.search(**args)
            else:
                output = getattr(sandbox, tool)(**args)
                result = {"output": output, "returncode": 0, "exception_info": ""}
                trace.emit("tool", tool=tool, arguments=args, **result)
        except (OSError, ValueError, UnicodeError) as exc:
            result = {"output": "", "returncode": -1, "exception_info": f"{type(exc).__name__}: {exc}"}
            trace.emit("tool_error", tool=action["tool"], arguments=action["args"], **result)
        observation = json.dumps(result, ensure_ascii=False)
        bounded = truncate(observation)
        if bounded != observation:
            trace.emit("observation_truncated", input_bytes=len(observation.encode()), output_bytes=len(bounded.encode()))
        messages.append({"role": "user", "content": bounded})
    return exit_status
