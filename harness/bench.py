"""Shared measurement rig. Success is solely the hidden verifier's result."""
import csv
import hashlib
import json
import os
import platform
import shlex
import shutil
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from . import ROOT
from .client import Client, ModelConfig, HarnessError
from .sandbox import Sandbox
from .trace import Trace

CORE_FILES = ("__init__.py", "baseline.py", "bench.py", "client.py", "protocol.py", "sandbox.py", "trace.py", "v0.py", "variants.py", "experiment.py")


def digest_tree(path: Path):
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            h.update(str(f.relative_to(path)).encode() + b"\0" + f.read_bytes())
    return h.hexdigest()


def load_tasks(subset: str):
    if not subset or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in subset):
        raise ValueError("subset must name a file in subsets/ (e.g. mini10)")
    selection = json.loads((ROOT / "subsets" / f"{subset}.json").read_text())
    suite = ROOT / "suites" / selection["suite"]
    manifest = json.loads((suite / "manifest.json").read_text())
    by_id = {t["id"]: t for t in manifest["tasks"]}
    if len(selection["tasks"]) != len(set(selection["tasks"])):
        raise ValueError("duplicate task IDs in subset")
    return suite, [by_id[k] for k in selection["tasks"]]


def grade(work: Path, task_path: Path, trace=None):
    verifier = task_path / "verify.py"
    sandbox = Sandbox(work, readable=[verifier])
    command = f"{shlex.quote(str(ROOT / '.venv/bin/python'))} -I {shlex.quote(str(verifier))} {shlex.quote(str(work))}"
    output = sandbox.run(command, timeout=15)
    passed = output["returncode"] == 0 and output["output"].rstrip().endswith("VERIFIED")
    result = {"passed": passed, **output}
    if trace:
        trace.emit("grade", **result)
    return result


def model_identity(config):
    base = config.base_url.rstrip("/")
    if base.startswith("http://127.0.0.1:11435"):
        with urllib.request.urlopen(base.removesuffix("/v1") + "/api/tags", timeout=5) as r:
            models = json.load(r)["models"]
        for model in models:
            if model["name"] == config.model:
                return model
        raise ValueError(f"local model {config.model!r} is not installed; use make pull MODEL=...")
    # No inference call or third-party key discovery for external providers.
    return {"name": config.model, "identity_unverified": True}


def classify(result, events):
    tags = []
    if any(e["event"] == "parse_error" for e in events): tags.append("malformed_action")
    if any(e["event"] == "api_error" for e in events): tags.append("provider_error")
    if any(e["event"] == "context_compacted" for e in events): tags.append("context_compaction")
    if any(e["event"] == "observation_truncated" for e in events): tags.append("large_observation")
    if any(e["event"] == "tool_error" or (e["event"] == "tool" and e.get("returncode") != 0) for e in events): tags.append("tool_error")
    if result["exit_status"] in ("step_budget", "LimitsExceeded", "loop_budget", "time_budget", "BudgetExceeded"):
        tags.append("budget_or_loop")
    if not result["passed"]:
        tags.append("verifier_failure")
    return tags


def run_bench(**kwargs):
    import fcntl
    (ROOT / ".runtime").mkdir(exist_ok=True)
    with (ROOT / ".runtime/bench.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("another benchmark owns the model; run sequentially")
        return _run_bench(**kwargs)


def _run_bench(model: str, agent: str, subset: str, base_url: str, steps=16, task_timeout=240, max_tokens=1024):
    parsed_url = urlsplit(base_url)
    if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc or parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment:
        raise ValueError("BASE_URL must be an http(s) endpoint without credentials, query or fragment; use HARNESS_API_KEY")
    from .variants import features_for
    features = frozenset() if agent == "baseline" else features_for(agent)
    if steps < 1 or task_timeout <= 0 or max_tokens < 1:
        raise ValueError("budgets must be positive")
    suite, tasks = load_tasks(subset)
    config = ModelConfig(model=model, base_url=base_url, max_tokens=max_tokens)
    identity = model_identity(config)
    experiment = None
    if features:
        from .experiment import validate_experiment
        experiment = validate_experiment(config, identity, suite, subset, steps, task_timeout, features)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = "".join(c if c.isalnum() else "-" for c in model)
    out = ROOT / "runs" / f"{stamp}-{agent}-{slug}-{subset}-{uuid.uuid4().hex[:6]}"
    out.mkdir(parents=True)
    source = out / "source"
    source.mkdir()
    for name in CORE_FILES:
        shutil.copy2(ROOT / "harness" / name, source / name)
    meta = {"run_id": out.name, "started_at": datetime.now(timezone.utc).isoformat(),
            "agent": agent, "model": model, "model_identity": identity, "subset": subset,
            "suite": suite.name, "suite_sha256": digest_tree(suite),
            "code_sha256": digest_tree(source), "steps": steps,
            "task_timeout_s": task_timeout, "max_tokens": max_tokens,
            "temperature": config.temperature, "seed": config.seed, "base_url": base_url,
            "platform": platform.platform(), "python": platform.python_version(),
            "concurrency": 1, "complete": False,
            "measurement": "local-mini-suite; not Terminal-Bench; tokens are provider usage, wall times use monotonic clock"}
    if experiment:
        meta.update(phase=2, features=sorted(features), experiment=experiment)
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    print(f"Run: {out.relative_to(ROOT)}", flush=True)
    started = time.monotonic()
    # Explicit, separately logged warm-up prevents accidental cold-load bias.
    warm_trace = Trace(out / "warmup.jsonl")
    warm = Client(config, warm_trace, time.monotonic() + 180)
    warm.query([{"role": "user", "content": "Reply with READY."}])
    meta["warmup"] = warm.stats()
    rows = []
    for index, task in enumerate(tasks, 1):
        task_path = ROOT / task["path"]
        trial = out / task["id"]
        work = trial / "work"
        shutil.copytree(task_path / "initial", work)
        trace = Trace(trial / "trace.jsonl")
        begin = time.monotonic()
        client = Client(config, trace, begin + task_timeout)
        if "aligned" in features:
            from .variants import AlignedSandbox
            sandbox = AlignedSandbox(work, trace=trace, deadline=client.deadline)
        else:
            sandbox = Sandbox(work, trace=trace, deadline=client.deadline)
        prompt = (task_path / "instruction.md").read_text()
        trace.emit("task_start", task_id=task["id"], instruction=prompt, agent=agent, model=model)
        error = None
        try:
            if agent == "baseline":
                from .baseline import run_baseline
                status = run_baseline(prompt, client, sandbox, trace, steps, trial)
            elif features:
                from .variants import run_variant
                status = run_variant(prompt, client, sandbox, trace, steps, features)
            else:
                from .v0 import run_v0
                status = run_v0(prompt, client, sandbox, trace, steps)
        except Exception as exc:
            status = type(exc).__name__
            error = str(exc) if isinstance(exc, HarnessError) else type(exc).__name__
            trace.emit("agent_error", error=error, error_type=status)
        agent_s = time.monotonic() - begin
        # Preserve the submitted tree before grader-generated inputs appear.
        shutil.copytree(work, trial / "submission", symlinks=True, ignore=shutil.ignore_patterns(".tmp", "__pycache__"))
        verdict = grade(work, task_path, trace)
        (trial / "verifier.log").write_text(verdict["output"] + verdict["exception_info"])
        result = {"task": task["id"], "category": task["category"], "agent": agent, "model": model,
                  "passed": verdict["passed"], "exit_status": status, "error": error,
                  "agent_s": agent_s, "grader_s": verdict["wall_s"], "wall_s": time.monotonic() - begin,
                  **client.stats()}
        result["tags"] = classify(result, trace.events)
        result["event_counts"] = {kind: sum(e["event"] == kind for e in trace.events) for kind in sorted({e["event"] for e in trace.events})}
        trace.emit("task_result", **result)
        (trial / "result.json").write_text(json.dumps(result, indent=2))
        with (out / "tasks.jsonl").open("a") as stream:
            stream.write(json.dumps(result) + "\n")
        rows.append(result)
        print(f"[{index}/{len(tasks)}] {task['id']:<18} {'PASS' if result['passed'] else 'FAIL'}  {result['wall_s']:.2f}s  in={result['prompt_tokens']} out={result['completion_tokens']}  {status}", flush=True)
    complete_usage = all(row["usage_complete"] for row in rows)
    summary = {"tasks": len(rows), "passed": sum(row["passed"] for row in rows),
               "pass_rate": sum(row["passed"] for row in rows) / len(rows),
               "task_wall_s": sum(row["wall_s"] for row in rows),
               "job_wall_s": time.monotonic() - started,
               "prompt_tokens": sum(row["prompt_tokens"] for row in rows) if complete_usage else None,
               "completion_tokens": sum(row["completion_tokens"] for row in rows) if complete_usage else None,
               "calls": sum(row["calls"] for row in rows), "usage_complete": complete_usage}
    meta.update(complete=True, finished_at=datetime.now(timezone.utc).isoformat(), summary=summary)
    (out / "run.json").write_text(json.dumps(meta, indent=2))
    with (out / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["task","passed","exit_status","wall_s","prompt_tokens","completion_tokens","calls"], extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)
    from .viewer import build_viewer
    build_viewer(out)
    print(f"\n| Agent | Model | Passed | Pass rate | Task wall (s) | Input tokens | Output tokens |")
    print("|---|---|---:|---:|---:|---:|---:|")
    print(f"| {agent} | {model} | {summary['passed']}/{summary['tasks']} | {summary['pass_rate']:.1%} | {summary['task_wall_s']:.2f} | {summary['prompt_tokens']} | {summary['completion_tokens']} |")
    print(f"Trace viewer: {out / 'viewer.html'}", flush=True)
    return out
