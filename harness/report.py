"""Reproduce the results document from measured artifacts, never estimates."""
import json
from pathlib import Path
from collections import Counter
from . import ROOT
from .bench import digest_tree


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_run(run):
    meta = json.loads((run / "run.json").read_text())
    if not meta["complete"]:
        raise ValueError(f"incomplete run: {run.name}")
    rows = read_rows(run / "tasks.jsonl")
    if len(rows) != meta["summary"]["tasks"] or len({r["task"] for r in rows}) != len(rows):
        raise ValueError("missing or duplicate tasks")
    if digest_tree(run / "source") != meta["code_sha256"]:
        raise ValueError("source snapshot hash mismatch")
    for row in rows:
        events = read_rows(run / row["task"] / "trace.jsonl")
        responses = [e["response"] for e in events if e["event"] == "response"]
        grades = [e for e in events if e["event"] == "grade"]
        if len(grades) != 1 or grades[0]["passed"] != row["passed"]:
            raise ValueError("grade/summary mismatch")
        if row["usage_complete"]:
            for key in ("prompt_tokens", "completion_tokens"):
                if sum(r["usage"][key] for r in responses) != row[key]:
                    raise ValueError("response/summary token mismatch")
        if sum(e["event"] == "request" for e in events) != row["calls"]:
            raise ValueError("request count mismatch")
        if meta.get("phase") == 2:
            features = meta["features"]
            declarations = [e["features"] for e in events if e["event"] == "variant"]
            if declarations != [features]:
                raise ValueError("variant declaration mismatch")
            for event in events:
                if event["event"] == "request":
                    constrained = "response_format" in event["payload"]
                    if constrained != ("constrained" in features):
                        raise ValueError("structured-output feature mismatch")
            if meta["code_sha256"] != meta["experiment"]["frozen_core_sha256"]:
                raise ValueError("experiment/source hash mismatch")
    summary = meta["summary"]
    if summary["passed"] != sum(r["passed"] for r in rows):
        raise ValueError("pass count mismatch")
    if summary["pass_rate"] != summary["passed"] / len(rows):
        raise ValueError("pass rate mismatch")
    if summary["calls"] != sum(r["calls"] for r in rows):
        raise ValueError("aggregate call count mismatch")
    if abs(summary["task_wall_s"] - sum(r["wall_s"] for r in rows)) > 1e-6:
        raise ValueError("wall time mismatch")
    for key in ("prompt_tokens", "completion_tokens"):
        expected = sum(r[key] for r in rows) if all(r["usage_complete"] for r in rows) else None
        if summary[key] != expected:
            raise ValueError("aggregate token mismatch")
    return meta, rows


def metric(value):
    return "unknown" if value is None else f"{value:,}"


def taxonomy(run, rows):
    counts = Counter()
    for row in rows:
        events = read_rows(run / row['task'] / 'trace.jsonl')
        counts['parse'] += sum(e['event']=='parse_error' for e in events)
        counts['tool'] += sum(e['event']=='tool_error' or (e['event']=='tool' and e.get('returncode')!=0) for e in events)
        counts['syntax'] += sum(e['event']=='syntax_rejected' for e in events)
        counts['compact'] += sum(e['event']=='context_compacted' for e in events)
        counts['truncate'] += sum(e['event']=='observation_truncated' for e in events)
        counts['format_exit'] += row['exit_status']=='format_budget'
        counts['budget_exit'] += row['exit_status'] in ('loop_budget','step_budget','LimitsExceeded','time_budget','BudgetExceeded')
        counts['failed_submit'] += not row['passed'] and row['exit_status'] in ('Submitted','submitted')
        counts['checks_pass'] += sum(e['event']=='requirement_check' and e['passed'] for e in events)
        counts['checks_fail'] += sum(e['event']=='requirement_check' and not e['passed'] for e in events)
        counts['api_errors'] += sum(e['event']=='api_error' for e in events)
        counts['output_cutoffs'] += sum(e['event']=='response' and any(c.get('finish_reason')=='length' for c in e['response'].get('choices',[])) for e in events)
    return counts


def report(root=ROOT):
    runs = []
    for path in sorted((root / "runs").glob("*/run.json")):
        meta = json.loads(path.read_text())
        if meta.get("complete") and meta.get("subset") == "mini10":
            runs.append((path.parent, *verify_run(path.parent)))
    if not runs:
        raise ValueError("No complete mini10 runs. Smoke runs are not score runs.")
    lines = ["# Measured local results", "",
             "These are local mini-suite measurements, **not Terminal-Bench scores**. Docker's daemon was unavailable; the requested fallback was used. No hosted model was used. No claim of harness improvement is implied by implementing v0.", "",
             "All performance numbers below are recomputed from saved run artifacts. Every complete mini10 run is included; development smoke runs and synthetic endpoint probes are excluded. No failed run is dropped and token accounting is not estimated. The combination is selected after the single-change ablations; this is development-set selection, not held-out validation.", "",
             "## Ablation table", "",
             "| Agent / variant | Enabled changes | Passed / tasks | Pass rate | Task wall (s) | Input tokens | Output tokens | Calls |",
             "|---|---|---:|---:|---:|---:|---:|---:|"]
    for path, meta, rows in runs:
        s = meta["summary"]
        features = ', '.join(meta.get('features', [])) or ('upstream reference' if meta['agent']=='baseline' else 'original v0')
        lines.append(f"| [{meta['agent']}]({path.relative_to(root)}/run.json) | {features} | {s['passed']} / {s['tasks']} | {s['pass_rate']:.1%} | {s['task_wall_s']:.2f} | {metric(s['prompt_tokens'])} | {metric(s['completion_tokens'])} | {s['calls']} |")
    models = sorted({m['model'] for _,m,_ in runs})
    lines += ['', 'Measured model(s): ' + ', '.join(f'`{m}`' for m in models) + '.']
    lines += ["", "Task wall is the sum of monotonic per-task elapsed times, including agent startup, inference, tools, submission copying and grading. Downloads and the separately logged model warm-up are excluded. Input tokens include repeated/cached prompt tokens as reported by the endpoint. Failed format attempts are included. Unknown usage stays unknown. Electricity, amortized hardware cost and dollar cost were not measured.", "", "## Reproduction and evidence", ""]
    for path, meta, rows in runs:
        relative = path.relative_to(root)
        lines += [f"- **{meta['agent']}**: [run metadata]({relative}/run.json), [CSV]({relative}/results.csv), [trace viewer]({relative}/viewer.html), [frozen source]({relative}/source/).",
                  f"  Actual invocation: `make bench MODEL={meta['model']} AGENT={meta['agent']} SUBSET={meta['subset']} STEPS={meta['steps']} TASK_TIMEOUT={meta['task_timeout_s']:g} MAX_TOKENS={meta['max_tokens']}`.",
                  f"  Job wall including warm-up: {meta['summary']['job_wall_s']:.2f} s. Started: `{meta['started_at']}`."]
    lines += ["", "Comparability fields recorded in every run include model digest, suite hash, source hash, sampling settings and budgets. This is a single-machine development sample with one attempt per task per run, not a statistical estimate of general coding performance. The fixtures were authored for this project; the model was not trained or fine-tuned. The suite is intentionally much smaller and easier to set up than Terminal-Bench.", ""]
    identities = {(m['model_identity'].get('digest'), m['suite_sha256'], m['steps'], m['task_timeout_s'], m['max_tokens'], m['temperature'], m['seed']) for _,m,_ in runs}
    lines.append("The compared runs share the same model digest, suite and inference/step/time budgets." if len(identities)==1 else "Runs have differing model/suite/budget fields; inspect run metadata before attributing any difference to the agent.")
    phase2 = [(p,m,rows) for p,m,rows in runs if m.get('phase')==2]
    if phase2:
        lines += ['', 'Phase 2 was preregistered in [the experiment manifest](research/phase2-experiment.json). Each single variant enables only its named feature; combinations declare every enabled feature. The original reference/v0 source snapshots differ from the Phase 2 implementation. No hidden verifier or oracle content was used to develop these changes. The prior Phase 1 diagnosis was already known.']
        hashes = {m['code_sha256'] for _,m,_ in phase2}
        lines += ['', 'Phase 2 runs share one frozen implementation hash.' if len(hashes)==1 else 'Phase 2 contains multiple implementation hashes; compare the recorded revisions explicitly.']
        analysis_path = root / 'research/phase2-analysis.json'
        if analysis_path.exists():
            phase2_analysis = json.loads(analysis_path.read_text())
            lines += ['', '## Phase 2 findings', ''] + phase2_analysis['findings']
            lines += ['', '**Combination selection:** ' + phase2_analysis['selection']]
    lines += ['', '## Failure and recovery taxonomy per run', '',
              'Parse/tool/syntax/compaction/truncation counts are events. Format, loop/step and failed-submit counts are tasks. Requirement gates count successful or blocked finish attempts, including missing artifacts before any test executes. Nonzero shell exits may be deliberate probes or failing self-tests. Categories overlap and can occur in passing tasks; syntax rejection is also a tool error. Baseline output elision is not instrumented by the v0 truncation event. Compaction does not establish that context overflow occurred.', '',
              '| Variant | Parse | Output cutoffs | Tool | Syntax | Compact | Truncate | Format exits | Loop/step exits | Failed submits | Requirement gate pass/block | API errors |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for path, meta, rows in runs:
        c = taxonomy(path, rows)
        lines.append(f"| [{meta['agent']}]({path.relative_to(root)}/tasks.jsonl) | {c['parse']} | {c['output_cutoffs']} | {c['tool']} | {c['syntax']} | {c['compact']} | {c['truncate']} | {c['format_exit']} | {c['budget_exit']} | {c['failed_submit']} | {c['checks_pass']}/{c['checks_fail']} | {c['api_errors']} |")
    lines += ["", "## Per-task measurements", "", "| Agent | Task | Outcome | Exit | Wall (s) | Input tokens | Output tokens |", "|---|---|---|---|---:|---:|---:|"]
    for path, meta, rows in runs:
        for r in rows:
            rel = path.relative_to(root) / r["task"]
            lines.append(f"| {meta['agent']} | [{r['task']}]({rel}/trace.jsonl) | {'PASS' if r['passed'] else 'FAIL'} | {r['exit_status']} | {r['wall_s']:.2f} | {metric(r['prompt_tokens'])} | {metric(r['completion_tokens'])} |")
    commentary = root / "research/results-analysis.json"
    if commentary.exists():
        analysis=json.loads(commentary.read_text())
        lines += ["", "## Original Phase 1 diagnosis", "", "The following diagnosis and ranking preceded Phase 2; its v0 references mean the original unmodified agent.", ""] + analysis['findings']
        lines += ["", "### Original improvement ranking", "", "Ranked qualitatively from Phase 1 traces. Phase 2 measures these hypotheses above; this ranking is not a numerical gain estimate.", ""]
        for index, idea in enumerate(analysis['ideas'], 1):
            lines.append(f"{index}. **{idea['title']}** — {idea['reason']}")
    else:
        lines += ["", "Detailed failure analysis is pending inspection of the completed comparison traces."]
    lines += ["", "Regenerate this document with `make report`. The generator verifies token sums, task counts, grader outcomes and source snapshots against the underlying JSONL before writing this file.", ""]
    target=root/'RESULTS.md';target.write_text('\n'.join(lines))
    if phase2 and (root/'research/phase2-analysis.json').exists():
        from .writeup import writeup
        writeup(root, runs, json.loads((root/'research/phase2-analysis.json').read_text()))
    return target
