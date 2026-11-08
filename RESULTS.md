# Measured local results

These are local mini-suite measurements, **not Terminal-Bench scores**. Docker was unavailable for these runs, so the local mini-suite was used. No hosted model was used. No claim of harness improvement is implied by implementing v0.

All performance numbers below are recomputed from saved run artifacts. Every complete mini10 run is included; development smoke runs and synthetic endpoint probes are excluded. No failed run is dropped and token accounting is not estimated. The combination is selected after the single-change ablations; this is development-set selection, not held-out validation.

## Ablation table

| Agent / variant | Enabled changes | Passed / tasks | Pass rate | Task wall (s) | Input tokens | Output tokens | Calls |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | upstream reference | 5 / 10 | 50.0% | 1728.90 | 403,614 | 34,099 | 139 |
| v0 | original v0 | 0 / 10 | 0.0% | 235.91 | 35,324 | 4,490 | 49 |
| v0-constrained | constrained | 2 / 10 | 20.0% | 412.69 | 82,172 | 7,601 | 79 |
| v0-repair | repair | 1 / 10 | 10.0% | 206.45 | 42,539 | 4,144 | 53 |
| v0-aligned | aligned | 0 / 10 | 0.0% | 241.95 | 35,401 | 5,376 | 46 |
| v0-requirements | requirements | 0 / 10 | 0.0% | 213.64 | 42,930 | 3,911 | 52 |
| v0-versions | versions | 0 / 10 | 0.0% | 296.43 | 45,320 | 5,251 | 56 |
| combo-constrained-aligned-versions | aligned, constrained, versions | 3 / 10 | 30.0% | 753.73 | 83,883 | 8,876 | 79 |
| combo-constrained-aligned-versions-requirements | aligned, constrained, requirements, versions | 2 / 10 | 20.0% | 1040.05 | 184,595 | 17,596 | 155 |
| combo-constrained-aligned-versions-requirements-repair | aligned, constrained, repair, requirements, versions | 4 / 10 | 40.0% | 1030.19 | 189,478 | 14,227 | 156 |

Measured model(s): `qwen3.5:4b-q4_K_M`.

Task wall is the sum of monotonic per-task elapsed times, including agent startup, inference, tools, submission copying and grading. Downloads and the separately logged model warm-up are excluded. Input tokens include repeated/cached prompt tokens as reported by the endpoint. Failed format attempts are included. Unknown usage stays unknown. Electricity, amortized hardware cost and dollar cost were not measured.

## Reproduction and evidence

Run directories (traces, per-task submissions, frozen source and the HTML trace viewer) are large and stay out of git. Every number here is recomputed from them by `make report`. The exact invocations were:

```sh
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=baseline SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=v0 SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=v0-constrained SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=v0-repair SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=v0-aligned SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=v0-requirements SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=v0-versions SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=combo-constrained-aligned-versions SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=combo-constrained-aligned-versions-requirements SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
make bench MODEL=qwen3.5:4b-q4_K_M AGENT=combo-constrained-aligned-versions-requirements-repair SUBSET=mini10 STEPS=16 TASK_TIMEOUT=600 MAX_TOKENS=1024
```

Comparability fields recorded in every run include model digest, suite hash, source hash, sampling settings and budgets. This is a single-machine development sample with one attempt per task per run, not a statistical estimate of general coding performance. The fixtures were authored for this project; the model was not trained or fine-tuned. The suite is intentionally much smaller and easier to set up than Terminal-Bench.

The compared runs share the same model digest, suite and inference/step/time budgets.

Phase 2 was preregistered in the experiment manifest. Each single variant enables only its named feature; combinations declare every enabled feature. The original reference/v0 source snapshots differ from the Phase 2 implementation. No hidden verifier or oracle content was used to develop these changes. The prior Phase 1 diagnosis was already known.

Phase 2 runs share one frozen implementation hash.

## Phase 2 findings

**Isolated changes:** constrained actions passed 2/10, targeted repair 1/10, alignment 0/10, requirement checks 0/10 and file-version repetition 0/10. None of these single changes beat the frozen baseline. Each was scored on the same task order, suite hash, model digest and budgets.

**Structured decoding repaired the protocol bottleneck.** The constrained run had 1 parse error and 0 format-budget exits. Its sole malformed action was a response cut off at the unchanged token limit, recorded in toposort. It still had 6 incorrect submissions and 4 loop/step exits. Valid action syntax was not enough for correct programs.

**Targeted feedback recovered some actions.** The repair run recorded 27 parse errors and 6 format-budget exits. intervals recovered from malformed calls and passed. merge-config shows the corrective instruction changing on repeated invalid replies without achieving a pass. This is a whole-run comparison, not proof that one individual message caused the pass.

**Alignment made a concrete edit safer.** The JSONL CLI trace records a Python syntax rejection for rebinding a comprehension iteration variable, before file mutation. The same run also completed raw-code patch dispatches. It still ended 8 tasks on format budgets. Mechanical edit safety and task correctness are different outcomes.

**The requirement workflow remained mostly unreachable in isolation.** All 10 tasks ultimately ended on format budgets. Its 1 finish-gate attempt was blocked by a missing requirements artifact in sql-revenue; 0 gates passed. This does not establish that executable self-tests are ineffective: the agent did not successfully reach that workflow.

**Version tracking removed a premature stop, but did not solve the task.** In config-parser, rereads after edits continued through the fixed step budget rather than stopping at the original identical-read guard. The hidden verdict was still a failure. More allowed work is not automatically useful work. No hidden verifier content was inspected to diagnose or change the implementation.

**The declared combinations scored 3/10, 2/10 and 4/10.** The strongest observed configuration was combo-constrained-aligned-versions-requirements-repair, at 40%, 1030.19 seconds, 189,478 input tokens and 14,227 output tokens. It improved on the original v0's observed result but did not beat the baseline's five passes. This is a development-suite result from the declared sequence, not a held-out or statistical win.

**Passing self-tests did not establish correctness.** In merge-config with requirement checks, an initial gate was blocked by the missing requirements file. A later gate passed, but the independent verdict was failure. That run recorded 1 passed and 6 blocked gates; missing artifacts and assertion failures must not be conflated. It also reached loop/step exits on 9 tasks, showing the workflow's cost under the fixed budget.

**The final repair switch did not explain the score difference.** The final configuration emitted 0 repair-feedback events because it had 0 parse errors. It scored differently from the preceding configuration even though the added branch was never used. The replay audit found identical first requests/responses on csv-totals, followed by changed tool observations (wall time and output). These single attempts cannot identify a causal repair benefit. No extra attempts were sampled to obtain a desired score.

**Combination selection:** All five single changes were completed first. The declared combination sequence starts with constrained actions, alignment and file versions, then adds requirement checks, then targeted repair. Each later candidate adds one feature. The final choice uses pass count, then parse-error count, actual total tokens and task wall time; every candidate is reported. See the combination plan. The observed selection under that rule is `combo-constrained-aligned-versions-requirements-repair`. The desired pass-rate win over the reference was not achieved.

## Failure and recovery taxonomy per run

Parse/tool/syntax/compaction/truncation counts are events. Format, loop/step and failed-submit counts are tasks. Requirement gates count successful or blocked finish attempts, including missing artifacts before any test executes. Nonzero shell exits may be deliberate probes or failing self-tests. Categories overlap and can occur in passing tasks; syntax rejection is also a tool error. Baseline output elision is not instrumented by the v0 truncation event. Compaction does not establish that context overflow occurred.

| Variant | Parse | Output cutoffs | Tool | Syntax | Compact | Truncate | Format exits | Loop/step exits | Failed submits | Requirement gate pass/block | API errors |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 5 | 12 | 0 | 0 | 0 | 0 | 4 | 4 | 0/0 | 0 |
| v0 | 32 | 0 | 3 | 0 | 7 | 0 | 9 | 1 | 0 | 0/0 | 0 |
| v0-constrained | 1 | 1 | 14 | 0 | 15 | 0 | 0 | 4 | 6 | 0/0 | 0 |
| v0-repair | 27 | 0 | 3 | 0 | 6 | 0 | 6 | 1 | 2 | 0/0 | 0 |
| v0-aligned | 28 | 0 | 3 | 1 | 4 | 0 | 8 | 0 | 2 | 0/0 | 0 |
| v0-requirements | 34 | 0 | 0 | 0 | 2 | 0 | 10 | 0 | 0 | 0/1 | 0 |
| v0-versions | 32 | 0 | 5 | 0 | 10 | 0 | 9 | 1 | 0 | 0/0 | 0 |
| combo-constrained-aligned-versions | 0 | 0 | 17 | 1 | 14 | 2 | 0 | 3 | 4 | 0/0 | 0 |
| combo-constrained-aligned-versions-requirements | 0 | 0 | 21 | 0 | 59 | 4 | 0 | 9 | 1 | 1/6 | 0 |
| combo-constrained-aligned-versions-requirements-repair | 0 | 0 | 25 | 0 | 65 | 8 | 0 | 9 | 1 | 1/8 | 0 |

## Per-task measurements

| Agent | Task | Outcome | Exit | Wall (s) | Input tokens | Output tokens |
|---|---|---|---|---:|---:|---:|
| baseline | csv-totals | FAIL | Submitted | 120.23 | 41,590 | 2,205 |
| baseline | merge-config | FAIL | Submitted | 130.45 | 30,878 | 2,626 |
| baseline | intervals | FAIL | Submitted | 76.54 | 17,026 | 1,701 |
| baseline | toposort | PASS | LimitsExceeded | 412.15 | 66,940 | 7,430 |
| baseline | log-summary | PASS | LimitsExceeded | 87.69 | 36,101 | 1,761 |
| baseline | jsonl-cli | FAIL | LimitsExceeded | 168.50 | 52,375 | 3,481 |
| baseline | sql-revenue | PASS | Submitted | 157.74 | 37,476 | 3,335 |
| baseline | repair-package | PASS | LimitsExceeded | 146.90 | 36,813 | 3,095 |
| baseline | path-index | PASS | Submitted | 161.11 | 28,085 | 3,350 |
| baseline | config-parser | FAIL | Submitted | 267.61 | 56,330 | 5,115 |
| v0 | csv-totals | FAIL | format_budget | 5.71 | 2,481 | 74 |
| v0 | merge-config | FAIL | format_budget | 5.76 | 1,365 | 99 |
| v0 | intervals | FAIL | format_budget | 6.01 | 1,473 | 105 |
| v0 | toposort | FAIL | format_budget | 9.07 | 4,214 | 154 |
| v0 | log-summary | FAIL | format_budget | 6.39 | 2,556 | 80 |
| v0 | jsonl-cli | FAIL | format_budget | 95.84 | 7,285 | 2,117 |
| v0 | sql-revenue | FAIL | format_budget | 6.37 | 1,536 | 102 |
| v0 | repair-package | FAIL | format_budget | 7.76 | 3,831 | 100 |
| v0 | path-index | FAIL | format_budget | 5.51 | 1,359 | 63 |
| v0 | config-parser | FAIL | loop_budget | 87.49 | 9,224 | 1,596 |
| v0-constrained | csv-totals | FAIL | loop_budget | 61.64 | 14,417 | 1,089 |
| v0-constrained | merge-config | FAIL | submitted | 28.65 | 3,465 | 633 |
| v0-constrained | intervals | PASS | loop_budget | 46.95 | 8,659 | 808 |
| v0-constrained | toposort | FAIL | submitted | 84.42 | 9,077 | 1,712 |
| v0-constrained | log-summary | PASS | loop_budget | 42.31 | 11,869 | 566 |
| v0-constrained | jsonl-cli | FAIL | submitted | 39.53 | 7,082 | 848 |
| v0-constrained | sql-revenue | FAIL | submitted | 10.01 | 2,351 | 212 |
| v0-constrained | repair-package | FAIL | step_budget | 69.45 | 20,147 | 1,066 |
| v0-constrained | path-index | FAIL | submitted | 13.42 | 2,353 | 300 |
| v0-constrained | config-parser | FAIL | submitted | 16.31 | 2,752 | 367 |
| v0-repair | csv-totals | FAIL | format_budget | 5.36 | 2,577 | 74 |
| v0-repair | merge-config | FAIL | format_budget | 25.31 | 3,734 | 596 |
| v0-repair | intervals | PASS | submitted | 46.44 | 8,254 | 935 |
| v0-repair | toposort | FAIL | format_budget | 4.30 | 1,446 | 66 |
| v0-repair | log-summary | FAIL | format_budget | 5.81 | 2,661 | 80 |
| v0-repair | jsonl-cli | FAIL | loop_budget | 79.08 | 11,637 | 1,596 |
| v0-repair | sql-revenue | FAIL | submitted | 10.76 | 2,348 | 236 |
| v0-repair | repair-package | FAIL | format_budget | 7.34 | 3,941 | 107 |
| v0-repair | path-index | FAIL | format_budget | 4.33 | 1,444 | 67 |
| v0-repair | config-parser | FAIL | submitted | 17.73 | 4,497 | 387 |
| v0-aligned | csv-totals | FAIL | format_budget | 5.36 | 2,608 | 71 |
| v0-aligned | merge-config | FAIL | format_budget | 5.93 | 1,449 | 99 |
| v0-aligned | intervals | FAIL | format_budget | 61.09 | 2,448 | 1,545 |
| v0-aligned | toposort | FAIL | format_budget | 57.01 | 6,757 | 1,331 |
| v0-aligned | log-summary | FAIL | format_budget | 6.10 | 2,674 | 80 |
| v0-aligned | jsonl-cli | FAIL | submitted | 74.55 | 9,648 | 1,698 |
| v0-aligned | sql-revenue | FAIL | format_budget | 4.95 | 1,593 | 60 |
| v0-aligned | repair-package | FAIL | format_budget | 8.08 | 3,975 | 103 |
| v0-aligned | path-index | FAIL | format_budget | 4.20 | 1,443 | 63 |
| v0-aligned | config-parser | FAIL | submitted | 14.67 | 2,806 | 326 |
| v0-requirements | csv-totals | FAIL | format_budget | 6.22 | 3,072 | 74 |
| v0-requirements | merge-config | FAIL | format_budget | 19.87 | 2,905 | 464 |
| v0-requirements | intervals | FAIL | format_budget | 6.78 | 3,008 | 77 |
| v0-requirements | toposort | FAIL | format_budget | 9.56 | 5,243 | 154 |
| v0-requirements | log-summary | FAIL | format_budget | 6.60 | 3,147 | 80 |
| v0-requirements | jsonl-cli | FAIL | format_budget | 6.32 | 3,025 | 68 |
| v0-requirements | sql-revenue | FAIL | format_budget | 60.66 | 9,870 | 1,396 |
| v0-requirements | repair-package | FAIL | format_budget | 9.31 | 4,571 | 100 |
| v0-requirements | path-index | FAIL | format_budget | 40.63 | 3,116 | 680 |
| v0-requirements | config-parser | FAIL | format_budget | 47.70 | 4,973 | 818 |
| v0-versions | csv-totals | FAIL | format_budget | 7.73 | 2,484 | 74 |
| v0-versions | merge-config | FAIL | format_budget | 7.25 | 1,365 | 99 |
| v0-versions | intervals | FAIL | format_budget | 7.93 | 1,473 | 105 |
| v0-versions | toposort | FAIL | format_budget | 11.65 | 4,214 | 154 |
| v0-versions | log-summary | FAIL | format_budget | 7.95 | 2,562 | 80 |
| v0-versions | jsonl-cli | FAIL | format_budget | 110.92 | 7,285 | 2,117 |
| v0-versions | sql-revenue | FAIL | format_budget | 5.92 | 1,536 | 102 |
| v0-versions | repair-package | FAIL | format_budget | 8.23 | 3,839 | 100 |
| v0-versions | path-index | FAIL | format_budget | 4.93 | 1,359 | 63 |
| v0-versions | config-parser | FAIL | step_budget | 123.91 | 19,203 | 2,357 |
| combo-constrained-aligned-versions | csv-totals | FAIL | loop_budget | 23.27 | 8,409 | 351 |
| combo-constrained-aligned-versions | merge-config | FAIL | submitted | 27.75 | 3,605 | 651 |
| combo-constrained-aligned-versions | intervals | PASS | submitted | 77.86 | 8,642 | 768 |
| combo-constrained-aligned-versions | toposort | PASS | submitted | 53.47 | 5,419 | 608 |
| combo-constrained-aligned-versions | log-summary | FAIL | step_budget | 83.87 | 21,138 | 434 |
| combo-constrained-aligned-versions | jsonl-cli | FAIL | submitted | 154.62 | 8,142 | 1,675 |
| combo-constrained-aligned-versions | sql-revenue | FAIL | submitted | 21.22 | 2,587 | 203 |
| combo-constrained-aligned-versions | repair-package | FAIL | step_budget | 265.47 | 20,281 | 3,174 |
| combo-constrained-aligned-versions | path-index | PASS | submitted | 30.62 | 2,854 | 686 |
| combo-constrained-aligned-versions | config-parser | FAIL | submitted | 15.57 | 2,806 | 326 |
| combo-constrained-aligned-versions-requirements | csv-totals | FAIL | step_budget | 124.96 | 20,513 | 1,835 |
| combo-constrained-aligned-versions-requirements | merge-config | FAIL | submitted | 125.65 | 15,467 | 2,459 |
| combo-constrained-aligned-versions-requirements | intervals | PASS | step_budget | 138.64 | 20,111 | 2,543 |
| combo-constrained-aligned-versions-requirements | toposort | FAIL | step_budget | 140.80 | 18,113 | 2,681 |
| combo-constrained-aligned-versions-requirements | log-summary | FAIL | step_budget | 52.89 | 18,435 | 650 |
| combo-constrained-aligned-versions-requirements | jsonl-cli | FAIL | step_budget | 92.06 | 20,073 | 1,228 |
| combo-constrained-aligned-versions-requirements | sql-revenue | FAIL | loop_budget | 71.36 | 16,303 | 1,141 |
| combo-constrained-aligned-versions-requirements | repair-package | FAIL | step_budget | 52.89 | 20,236 | 623 |
| combo-constrained-aligned-versions-requirements | path-index | PASS | step_budget | 113.64 | 19,053 | 2,054 |
| combo-constrained-aligned-versions-requirements | config-parser | FAIL | loop_budget | 127.17 | 16,291 | 2,382 |
| combo-constrained-aligned-versions-requirements-repair | csv-totals | FAIL | step_budget | 72.10 | 21,153 | 750 |
| combo-constrained-aligned-versions-requirements-repair | merge-config | FAIL | submitted | 97.99 | 14,645 | 1,545 |
| combo-constrained-aligned-versions-requirements-repair | intervals | PASS | step_budget | 141.76 | 20,114 | 2,027 |
| combo-constrained-aligned-versions-requirements-repair | toposort | PASS | step_budget | 69.57 | 19,735 | 825 |
| combo-constrained-aligned-versions-requirements-repair | log-summary | PASS | step_budget | 77.34 | 19,005 | 949 |
| combo-constrained-aligned-versions-requirements-repair | jsonl-cli | FAIL | step_budget | 122.35 | 20,029 | 1,627 |
| combo-constrained-aligned-versions-requirements-repair | sql-revenue | FAIL | step_budget | 84.33 | 15,843 | 1,522 |
| combo-constrained-aligned-versions-requirements-repair | repair-package | FAIL | step_budget | 81.42 | 21,054 | 884 |
| combo-constrained-aligned-versions-requirements-repair | path-index | PASS | loop_budget | 82.87 | 20,064 | 716 |
| combo-constrained-aligned-versions-requirements-repair | config-parser | FAIL | step_budget | 200.46 | 17,836 | 3,382 |

## Original Phase 1 diagnosis

The following diagnosis and ranking preceded Phase 2; its v0 references mean the original unmodified agent.

**The measured v0 is worse than the reference on this suite.** Its shorter runtime and lower token use reflect early failures, not greater efficiency at completing tasks. The v0 task records show nine `format_budget` exits and one `loop_budget` exit. All failed the independent grader. The baseline solved five tasks; three of those still ended at the upstream step limit. Submission status and correctness are deliberately separate.

**Malformed actions dominate v0.** On merge-config, the model repeated a shell object followed by a finish object in the same response; all three attempts were rejected before execution. On csv-totals, it repeatedly omitted `args` and added an unmatched closing brace. On toposort, it kept requesting a zero-based start line despite positive-line validation. The baseline also emitted malformed actions, but its traces contain successful recovery and task completions.

**Some corrective retries work, but the edit interface adds another failure point.** In jsonl-cli, v0 changed an invalid read with a `command` argument into a valid read with `path`. It then copied the displayed line-number prefixes into both patch strings. Exact-match patching safely rejected that edit without changing the file. Later invalid JSON exhausted the format budget. This is an interface mismatch as well as a model error; widening the step budget alone would not establish a fix.

**A valid edit or confident finish is not a correct program.** The baseline CSV submission uses `int(float(amount_str) * 100)`; the actual graded output contains `Ada: 28`, while the grader requires `Ada: 29`. merge-config retains aliases into input data and fails the independence check. intervals can shrink an enclosing interval and mutate an input list. The JSONL CLI grader observes only `b\n` where `a\nb\n` is required because the submission excludes numeric strings. The config-parser grader catches conversion of non-ASCII digits that should remain text.

**The repetition guard is too coarse.** In v0 config-parser, a fourth identical `read(config.py)` stops the task even though patches occurred between reads. The trace also shows self-written tests that contradict the task's line-based format and integer requirements. The guard prevents unbounded work, but it does not distinguish necessary reinspection from a stalled loop.

**Compaction was exercised; context overflow was not observed.** v0 recorded seven compactions across jsonl-cli and config-parser. The extractive ledger becomes repetitive and can omit useful outcomes. These traces do not establish that compaction caused the failures. No v0 observation-truncation event occurred in the scored runs; its truncation behavior is covered by offline tests, and the baseline's upstream observation elision is not counted by that event. No transport failure or missing token usage occurred in either scored run.

### Original improvement ranking

Ranked qualitatively from Phase 1 traces. Phase 2 measures these hypotheses above; this ranking is not a numerical gain estimate.

1. **Constrain the action shape at generation time** — Try native tool calling or an endpoint-supported JSON schema for exactly one action, with complete argument schemas and minimal optional fields. This addresses the nine format-budget exits in the v0 task records. Keep strict validation; compare this change alone before adding more machinery.
2. **Make corrective feedback specific to the failed tool** — Return a single valid example for the exact invalid field or envelope, and avoid generic shell-plus-finish examples that could encourage multiple actions. Detect identical invalid replies and change the repair instruction within a fixed repair budget. jsonl-cli shows a successful argument repair; merge-config shows the same invalid response surviving every retry.
3. **Align reading and patching** — Provide raw code separately from line-number metadata, explicitly mark which text is patchable, and add a bounded syntax check before committing Python edits. The copied prefixes in the failed patch are a concrete preventable failure. Preserve exact-match/no-mutation behavior on ambiguous patches; do not silently guess a replacement.
4. **Turn requirements into checks before submission** — Have the agent extract behavioral constraints and write small tests for them before declaring completion. Prioritize copy independence, decimal arithmetic, accepted input types and mutation requirements demonstrated by the baseline failures. Evaluate against unchanged hidden graders; do not feed their answers into the scored attempt. Check that self-written tests agree with the original task.
5. **Track progress and preserve useful memory** — Key repetition decisions to file versions and observation changes so rereading a modified file is allowed. Replace recursively clipped prose with a compact ledger of edits, test outcomes and unresolved constraints. Run separate ablations for the detector and memory policy: config-parser supplies evidence for both, but the current comparison cannot identify their individual effects.

Regenerate this document with `make report`. The generator verifies token sums, task counts, grader outcomes and source snapshots against the underlying JSONL before writing this file.
