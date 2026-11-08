"""Independent, predeclared Phase 2 changes around the original v0 loop.

No task IDs, grader content, oracle code, or task-specific solution hints belong
in this module. An empty feature set delegates to the unchanged v0 function.
"""
import ast
import hashlib
import json
import re
import time
from collections import Counter

from .protocol import SCHEMA, ParseError, parse_action
from .sandbox import Sandbox
from .v0 import SYSTEM, compact, truncate, run_v0

FEATURES = ("constrained", "repair", "aligned", "requirements", "versions")
VARIANTS = {"v0-" + name: frozenset([name]) for name in FEATURES}


def features_for(agent):
    if agent == "v0":
        return frozenset()
    if agent in VARIANTS:
        return VARIANTS[agent]
    if agent.startswith("combo-"):
        names = agent.removeprefix("combo-").split("-")
        if len(names) >= 2 and len(set(names)) == len(names) and set(names) <= set(FEATURES):
            return frozenset(names)
    raise ValueError("unknown variant; use v0-" + ", v0-".join(FEATURES) + " or combo-FEATURE-FEATURE")


def action_schema():
    """Discriminated union: the chosen tool determines exactly its arguments."""
    branches = []
    for tool, (required, optional) in SCHEMA.items():
        properties = {}
        for key, kind in (required | optional).items():
            # This endpoint silently drops constraints for a NUL-excluding
            # regex. Use its verified schema subset; local parsing still
            # rejects NULs and token-limit cutoffs before any execution.
            rule = {"type": "string", "maxLength": 32768} if kind is str else {"type": "integer", "minimum": 1}
            if key == "lines":
                rule["maximum"] = 200
            properties[key] = rule
        branches.append({"type": "object", "additionalProperties": False,
                         "properties": {"tool": {"const": tool}, "args": {
                             "type": "object", "properties": properties,
                             "required": list(required), "additionalProperties": False}},
                         "required": ["tool", "args"]})
    return {"oneOf": branches}


ACTION_FORMAT = {"type": "json_schema", "json_schema": {
    "name": "single_agent_action", "strict": True, "schema": action_schema()}}


def repair_feedback(content, error, repetition):
    """Infer intent only for feedback. No recovered fragment is ever executed."""
    candidate = {}
    try:
        candidate, _ = json.JSONDecoder().raw_decode(content.lstrip())
    except (ValueError, TypeError):
        match = re.search(r'"tool"\s*:\s*"([a-z]+)"', content)
        if match:
            candidate = {"tool": match.group(1)}
    if not isinstance(candidate, dict):
        candidate = {}
    tool = candidate.get("tool")
    if not isinstance(tool, str) or tool not in SCHEMA:
        tool = "shell"
    args = candidate.get("args", candidate)
    if not isinstance(args, dict):
        args = {}
    defaults = {"shell": {"command": "ls -la"},
                "read": {"path": "module.py"},
                "patch": {"path": "module.py", "old": "old text", "new": "replacement text"},
                "search": {"query": "symbol", "path": "."},
                "finish": {"message": "Implemented and tested the changes."}}
    example_args = dict(defaults[tool])
    required, optional = SCHEMA[tool]
    for key, kind in (required | optional).items():
        value = args.get(key)
        if type(value) is kind:
            if kind is str and len(value) <= 1200 and "\x00" not in value:
                example_args[key] = value
            elif kind is int:
                example_args[key] = max(1, min(value, 200)) if key == "lines" else max(1, value)
    example = {"tool": tool, "args": example_args}
    # This assertion checks our example, not the invalid model output.
    parse_action(json.dumps(example))
    if repetition == 1:
        instruction = "Correct the indicated field. Keep your intended operation, using this tool's exact envelope."
    elif repetition == 2:
        instruction = "Your identical invalid reply repeated. Discard its formatting and rebuild one object using only the keys below."
    else:
        instruction = "The previous correction did not change the invalid reply. Start a new, shorter action; do not repeat the malformed text."
    return (f"FORMAT ERROR: {error}. Nothing was executed. Tool: {tool}; "
            f"required args: {list(required)}; optional args: {list(optional)}. "
            f"{instruction} Exactly one valid example (adapt its values):\n" + json.dumps(example)), example


class AlignedSandbox(Sandbox):
    def read(self, path: str, start: int = 1, lines: int = 100):
        target = self.path(path)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("file too large; use shell with a selective read")
        content = target.read_text().splitlines(keepends=True)
        selected = content[start - 1:start - 1 + lines]
        return {"path": path, "start_line": start, "end_line": start + len(selected) - 1,
                "total_lines": len(content), "code": "".join(selected)}

    def patch(self, path: str, old: str, new: str):
        target = self.path(path)
        if target.exists():
            before = target.read_text()
            if not old or before.count(old) != 1:
                raise ValueError("old text must match exactly once; copy only the raw code field")
            candidate = before.replace(old, new, 1)
        elif old:
            raise ValueError("new file requires empty old text")
        else:
            candidate = new
        if len(candidate.encode()) > 2 * 1024 * 1024:
            raise ValueError("patch exceeds file size limit")
        if target.suffix == ".py":
            try:
                compile(candidate, path, "exec", dont_inherit=True)
            except (SyntaxError, ValueError) as exc:
                detail = f"{getattr(exc, 'msg', str(exc))} at line {getattr(exc, 'lineno', '?')}"
                if self.trace:
                    self.trace.emit("syntax_rejected", path=path, error=detail)
                raise ValueError(f"Python syntax check rejected edit without mutation: {detail}") from exc
        return super().patch(path, old, new)


def workspace_version(sandbox, action):
    """Version metadata, not source contents; never traverses symlinks.

    Reads/patches track their target. Search and shell track workspace files.
    Atomic replacement and normal writes change inode/mtime/size. Temporary
    command directories and Python caches do not count as source progress.
    """
    tool, args = action["tool"], action["args"]
    try:
        scope = sandbox.path(args["path"]) if tool in ("read", "patch") else sandbox.work
    except ValueError:
        return "invalid-path"
    paths = [scope] if not scope.is_dir() else sorted(scope.rglob("*"))
    state = []
    for path in paths:
        if path.is_symlink() or any(p in (".tmp", "__pycache__") for p in path.relative_to(sandbox.work).parts):
            continue
        try:
            stat = path.stat()
        except FileNotFoundError:
            state.append((str(path.relative_to(sandbox.work)), "missing"))
            continue
        if path.is_file():
            state.append((str(path.relative_to(sandbox.work)), stat.st_ino, stat.st_mtime_ns, stat.st_size))
    return hashlib.sha256(json.dumps(state).encode()).hexdigest()


REQUIREMENTS_PROMPT = '''\nBefore implementation, extract the task's requirements into .agent-requirements.json:
[{"quote":"an exact phrase copied from the user task","check":"how a self-test will verify it"}].
Cover each distinct behavior stated in the task. Do not invent requirements.
Write .agent-selftest.py with small runnable Python assertions for those requirements.
Check that expected values agree with the task text, not merely with your implementation.
Use only public task instructions and workspace files. Test the requested entry point.
The finish action runs this self-test and refuses submission if it fails or the artifacts are missing.
All planning, editing, and tests must fit the existing step budget. Use shell to create these files.
'''


def requirement_check(task, sandbox, trace):
    """Observable submission gate; does not claim semantic proof of self-tests."""
    try:
        plan_path = sandbox.path(".agent-requirements.json")
        test_path = sandbox.path(".agent-selftest.py")
        if plan_path.stat().st_size > 32768 or test_path.stat().st_size > 65536:
            raise ValueError("requirement artifacts are too large")
        plan = json.loads(plan_path.read_text())
        if not isinstance(plan, list) or not plan:
            raise ValueError("requirements must be a nonempty JSON list")
        normalized_task = " ".join(task.split())
        for item in plan:
            if (not isinstance(item, dict) or set(item) != {"quote", "check"}
                    or not all(isinstance(item[k], str) and item[k].strip() for k in item)):
                raise ValueError("each requirement needs nonempty quote and check strings")
            if " ".join(item["quote"].split()) not in normalized_task:
                raise ValueError("a requirement quote is not present in the task; use its exact wording")
        tree = ast.parse(test_path.read_text())
        if not any(isinstance(node, ast.Assert) for node in ast.walk(tree)):
            raise ValueError("self-test must contain executable assert checks")
        result = sandbox.run("python3 .agent-selftest.py")
        passed = result["returncode"] == 0
    except (OSError, ValueError, SyntaxError) as exc:
        result = {"output": "", "returncode": -1, "exception_info": str(exc)}
        passed = False
    trace.emit("requirement_check", passed=passed, **result)
    return passed, result


def run_variant(task, client, sandbox, trace, steps, features):
    if not features:
        return run_v0(task, client, sandbox, trace, steps)
    system = SYSTEM
    if "aligned" in features:
        system = system.replace("-- numbered lines.", "-- raw code plus separate range metadata; copy only code when patching.")
        system += "\nPython patch actions are syntax-checked before committing; rejected edits leave the file unchanged.\n"
    if "requirements" in features:
        system += REQUIREMENTS_PROMPT
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task}]
    repeated, invalid_replies = Counter(), Counter()
    format_streak = 0
    trace.emit("variant", features=sorted(features))
    for step in range(1, steps + 1):
        if time.monotonic() >= client.deadline:
            return "time_budget"
        messages = compact(messages, trace)
        response = client.query(messages, response_format=ACTION_FORMAT) if "constrained" in features else client.query(messages)
        content = response["choices"][0]["message"].get("content") or ""
        messages.append({"role": "assistant", "content": content})
        try:
            action, repaired = parse_action(content)
            if response["choices"][0].get("finish_reason") == "length":
                raise ParseError("output token limit reached; shorten the action")
        except ParseError as exc:
            format_streak += 1
            trace.emit("parse_error", step=step, error=str(exc), response=content)
            if "repair" in features:
                invalid_replies[content] += 1
                feedback, example = repair_feedback(content, str(exc), invalid_replies[content])
                trace.emit("repair_feedback", step=step, repetition=invalid_replies[content], example=example, feedback=feedback)
            else:
                feedback = f'FORMAT ERROR: {exc}. Nothing was executed. Every tool needs an args object. Example shell: {{"tool":"shell","args":{{"command":"ls"}}}}. Example finish: {{"tool":"finish","args":{{"message":"done"}}}}. Correct your previous action and retry.'
            messages.append({"role": "user", "content": feedback})
            if format_streak >= 3:
                return "format_budget"
            continue
        format_streak = 0
        trace.emit("action", step=step, action=action, repaired=repaired)
        if action["tool"] == "finish":
            if "requirements" in features:
                passed, result = requirement_check(task, sandbox, trace)
                if not passed:
                    messages.append({"role": "user", "content": "SUBMISSION BLOCKED: requirements/self-test check failed. " + truncate(json.dumps(result))})
                    continue
            return "submitted"
        signature = json.dumps(action, sort_keys=True)
        if "versions" in features:
            version = workspace_version(sandbox, action)
            signature += ":" + version
            trace.emit("action_version", step=step, version=version)
        repeated[signature] += 1
        if repeated[signature] >= 4:
            trace.emit("loop_detected", step=step, action=action)
            return "loop_budget"
        if repeated[signature] == 3:
            warning = "This action repeated against the same file version. Change your approach; one more repetition without a file change ends the task." if "versions" in features else "This identical action has repeated. Change your approach; one more identical action will end the task."
            messages.append({"role": "user", "content": warning})
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
    return "step_budget"
