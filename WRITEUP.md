# Valid actions are only the start

We tested `qwen3.5:4b-q4_K_M` on a frozen local coding suite. The original v0 passed 0/10 tasks; the upstream mini-SWE-agent baseline passed 5/10. We then completed 5 single-change runs and 3 combination run(s), keeping the model digest, suite and budgets fixed.

The best measured Phase 2 configuration, **combo-constrained-aligned-versions-requirements-repair**, passed **4/10 (40%)** and did not beat the baseline. Its summed task wall time was **1030.19 seconds**, with **189,478 input tokens** and **14,227 output tokens**. This is an observed development-suite result, not a Terminal-Bench score or a statistical claim.

| Configuration | Passed | Wall (s) | Input / output tokens |
|---|---:|---:|---:|
| baseline | 5/10 | 1728.90 | 403,614 / 34,099 |
| v0 | 0/10 | 235.91 | 35,324 / 4,490 |
| v0-constrained | 2/10 | 412.69 | 82,172 / 7,601 |
| v0-repair | 1/10 | 206.45 | 42,539 / 4,144 |
| v0-aligned | 0/10 | 241.95 | 35,401 / 5,376 |
| v0-requirements | 0/10 | 213.64 | 42,930 / 3,911 |
| v0-versions | 0/10 | 296.43 | 45,320 / 5,251 |
| combo-constrained-aligned-versions | 3/10 | 753.73 | 83,883 / 8,876 |
| combo-constrained-aligned-versions-requirements | 2/10 | 1040.05 | 184,595 / 17,596 |
| combo-constrained-aligned-versions-requirements-repair | 4/10 | 1030.19 | 189,478 / 14,227 |

The changes addressed action decoding, corrective feedback, reading/editing contracts, requirement-based self-tests and repetition after edits. Each was measured alone before any combination. No task-specific solution hints or hidden-grader content were used in development.

Structured output changed a concrete failure mode: recorded malformed-action events went from 32 in the original v0 run to 1 in the constrained-only run. Format-budget exits changed from 9 to 0. Those counts describe protocol reliability; the pass table shows whether it translated into correct programs.

Raw code views and precommit syntax checking addressed a concrete edit problem, and the file-version guard stopped treating every reread after an edit as the same stalled action. These mechanical fixes did not guarantee correct programs. Adding the requirement workflow changed the observed score from 3/10 to 2/10 and consumed more tokens. A self-test gate passed while the independent grader failed the same submission: matching task quotes and successful assertions did not prove adequate coverage. The final configuration reached 4/10, but its added repair branch never ran. Tool timings and filesystem observations changed subsequent prompts despite a fixed seed. We cannot credit that score difference to repair, and the baseline's five passes were not exceeded.

**What this experiment can establish.** These are actual, sequential local runs with provider-reported tokens and independent grading. The combination was selected on the same small development suite; there is no held-out result. All completed attempts, regressions, source snapshots and trace evidence are retained. Faster early exits are not successful-task efficiency.

The next decision should come from a held-out evaluation and a real Terminal-Bench run once the required environment is available. The useful artifact here is an inspectable experiment: change one thing, preserve the failures, and measure correctness separately from valid tool syntax.

See [RESULTS.md](RESULTS.md) for the complete ablation table, per-task logs and failure taxonomy, and [docs/design.md](docs/design.md) for the implementation. Regenerate both the numbers here and RESULTS.md with `make report`.
