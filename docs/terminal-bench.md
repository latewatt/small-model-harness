# Benchmark and model research

Checked on 7 November 2026. This document collects **published external results and the route to a real Terminal-Bench run**. This project's own measurements are in [RESULTS.md](../RESULTS.md). Primary sources are linked inline.

## What “current Terminal-Bench” means

The official homepage now defaults to **Terminal-Bench 4.0**. Its official run guide uses **Harbor**, not the old `tb` CLI, and says the tasks include GPU requirements. Its example uses Modal. Docker on an Apple Silicon Mac does not provide the required GPU environment for the entire current suite. The published run recipe uses repeated attempts. [Official homepage](https://www.tbench.ai/), [current run guide](https://www.tbench.ai/run).

Many model cards still report **Terminal-Bench 2.0**. That is a different benchmark: the original paper describes a collection of 89 terminal tasks. A 2.0 score cannot be relabeled 4.0, and a subset cannot be called a full-set score. The current 2.0 run page requires five attempts per task for official results. [Terminal-Bench paper](https://arxiv.org/abs/2601.11868), [2.0 run guide](https://www.tbench.ai/run?version=2.0).

Harbor is both the orchestration framework and the container/environment interface. A job contains trials; a trial runs an agent on a task and then invokes its verifier. Tasks package instructions, environment definition, configuration and grading. Harbor has a local results viewer and exports machine-readable artifacts. Docker is its ordinary local sandbox; cloud sandbox integrations are alternatives. [Harbor quick start](https://docs.harborframework.com/getting-started/quick-start), [run a job](https://docs.harborframework.com/jobs/run-a-job), [task overview](https://docs.harborframework.com/tasks/overview).

## Verified runner and pinned subset

We installed **Harbor 0.25.0** in `.venv-harbor`, separately from the agent environment. A `--print-config` dry run succeeds with the pinned version. The relevant current flags are `-d` dataset, `-a` agent, `-m` model, `-e` environment, `-i` include task name, `-n` concurrency and `-k` attempts. Repeated exact task filters prevent an accidental extra match such as `break-filter-js-from-html` when selecting `filter-js-from-html`. [Pinned Harbor source](https://github.com/harbor-framework/harbor/tree/v0.25.0), [job CLI source](https://github.com/harbor-framework/harbor/blob/v0.25.0/src/harbor/cli/jobs.py).

The historical public package is `terminal-bench/terminal-bench-2`, revision `1`, resolved through Harbor's public registry to:

```text
sha256:c6fc2e2382c1dbae99b2d5ecd2f4f4a60c3c01e0d84642d69b4afd92e99d078b
```

The resolved metadata lists 89 tasks. We validated that every chosen ID exists and saved all task content identities in `research/tb2-dataset-metadata.json`. [Public package](https://hub.harborframework.com/datasets/terminal-bench/terminal-bench-2/latest?tab=tasks).

`subsets/tb2-fast15.json` freezes these iteration candidates:

| Area | Tasks |
|---|---|
| Logs / text | `log-summary-date-ranges`, `regex-log`, `large-scale-text-editing` |
| Git / recovery | `git-leak-recovery`, `fix-git`, `git-multibranch`, `sanitize-git-repo`, `db-wal-recovery` |
| Data / repair | `multi-source-data-merger`, `cancel-async-tasks`, `extract-elf`, `fix-code-vulnerability` |
| Configuration / parsing | `openssl-selfsigned-cert`, `nginx-request-logging`, `filter-js-from-html` |

These were selected by workload type before any Terminal-Bench run, avoiding obvious training, video and simulation workloads. Public registry configuration was then checked: all selected tasks declare zero GPUs and 2048 MB task memory. **“Fast” is an iteration intention, not a timing result.** Docker was unavailable, so image build time, architecture compatibility and actual runtime are unmeasured. Do a cold-build/oracle preflight once Docker is available, then freeze a revised subset if necessary; do not silently replace failed tasks in a scored run.

## How to run later

Start Docker yourself and confirm `docker info` succeeds; nothing in this project installs or starts it. On a 16 GB laptop keep task concurrency at one, and account for Docker VM memory in addition to the model server.

```sh
make setup-terminal
make serve
make terminal-plan MODEL=qwen3.5:4b-q4_K_M SUBSET=tb2-fast15
```

Run the printed command when ready. It uses the official **Terminus 2** reference, host-side local inference, Docker task environments, the immutable dataset identity, exact task filters and one iteration attempt. It registers the local model's real configured context/output limits so LiteLLM does not fall back to an inappropriate context size. Its zero price entries disable local price lookup; they are not measured electricity or hardware costs. The iteration command also caps turns.

For the entire pinned 2.0 dataset:

```sh
make terminal-plan MODEL=qwen3.5:4b-q4_K_M SUBSET=tb2-full
```

That prints the full-dataset command with the task filter removed, five attempts per task and no iteration turn cap. Preserve every task, error, timeout, model configuration, dataset identity and trial artifact. Inspect with `.venv-harbor/bin/python scripts/harbor_local.py view runs/harbor`. Follow the official submission rules before calling anything an official score. The planner and metadata resolution were tested; **Docker execution was not**.

For current 4.0, the official example is:

```sh
harbor run -d terminal-bench/terminal-bench@4.0.0 \
  -e modal -a claude-code -m anthropic/claude-sonnet-5 -k 5
```

This requires the corresponding sandbox installation, GPU access and your own credentials/budget; it was not launched. Substitute a supported agent/model configuration deliberately and record it. Avoid comparing changed agents or budgets as though only the model changed. [Official current recipe](https://www.tbench.ai/run), [supported agents](https://docs.harborframework.com/agents/pre-integrated-agents).

The working `make bench` backend is the local **mini10** suite for baseline and v0. A Harbor adapter for v0 is a future extension, not an untested integration being presented as finished. Its interface is described in [design.md](design.md).

## Which models are worth considering

| Model / configuration | Primary evidence | Fit and decision |
|---|---|---|
| Qwen3.5 4B | Model card reports LiveCodeBench v6 **55.8** and BFCL-V4 **50.3**; these are not Terminal-Bench scores. [Model card](https://huggingface.co/Qwen/Qwen3.5-4B) | Selected candidate. The explicit Ollama `4b-q4_K_M` tag is much smaller than the default full/MLX variants. The actual local download and residency are in NOTES.md. |
| Qwen3.5 9B + little-coder | Official 2.0 board displays **9.2% ± 2.4**. [Leaderboard](https://www.tbench.ai/?version=2.0) | Its quantized weights and additional runtime would leave less comfortable headroom on this already-busy Mac. Not downloaded. |
| Qwen3.6 35B-A3B + little-coder | Official 2.0 board displays **24.6% ± 3.2**. [Leaderboard](https://www.tbench.ai/?version=2.0) | Small *active* parameter count is not a small weight footprint; outside tonight's memory policy. |
| Qwen3-Coder-Next | Vendor card reports Terminal-Bench 2 **36.2** and emphasizes agent training, long-horizon work and recovery. It has **80B total / 3B active** parameters. [Model card](https://huggingface.co/Qwen/Qwen3-Coder-Next), [technical report](https://arxiv.org/abs/2603.00729) | Useful future hosted/open-weight comparison. Its full weights do not fit comfortably here. Do not mistake active compute for resident memory. |
| Qwen2.5-Coder 1.5B / 3B | Official code-model family with small variants; Ollama lists roughly **986 MB / 1.9 GB** downloads. [Technical report](https://arxiv.org/abs/2409.12186), [Ollama library](https://ollama.com/library/qwen2.5-coder) | Good low-memory ablation candidates, but code-generation ability alone is not evidence of reliable agent loops. Not part of tonight's scored comparison. |

There is no verified tiny-model Terminal-Bench result here that establishes the chosen 4B model as universally best. It is a reasoned fit candidate: public coding/tool-use evidence, compatible local serving, explicit quantization and enough memory headroom. Its actual behavior is what this rig measures. Ollama tags can change; runs record the downloaded digest. [Qwen3.5 tags and sizes](https://ollama.com/library/qwen3.5/tags), [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility).

## What successful harnesses suggest

The official leaderboard evaluates **agent–model configurations**. For example, its 2.0 table lists MiniMax M2.1 with Crux at **36.6% ± 2.9**, versus Terminus 2 at **29.2% ± 2.9**. Different budgets and implementations can contribute, so this is evidence to investigate the harness, not a controlled causal estimate. [Official 2.0 table](https://www.tbench.ai/?version=2.0).

**Terminus 2** is the benchmark's neutral reference: structured terminal actions, validated parsing and context management rather than an IDE-heavy product. Its current source exposes JSON/XML parsers, turn limits and proactive summarization controls. **mini-SWE-agent** provides a compact, understandable baseline with a real upstream implementation; the project reports strong SWE-bench performance, which must not be substituted for a Terminal-Bench number. This project uses its supported text-based mode with pinned prompts. [Terminus source](https://github.com/harbor-framework/harbor/blob/v0.25.0/src/harbor/agents/terminus_2/terminus_2.py), [mini overview](https://mini-swe-agent.com/latest/), [local model configuration](https://mini-swe-agent.com/latest/models/local_models/).

SWE-agent's earlier ACI work motivates narrow file views, concise search and syntax-checked edits. A recent harness ablation study finds that context policies matter more under tight budgets and that predefined tools help weaker bash users; bash-proficient models can prefer a simpler interface. Another study finds model/task-dependent effects and even regressions from context compression in some repository-generation settings. Treat those as experiment hypotheses, not guaranteed gains for this model. [SWE-agent ACI](https://swe-agent.com/latest/background/aci/), [harness ablation study](https://arxiv.org/abs/2609.20804), [harness effects study](https://arxiv.org/abs/2609.32459).

## Failure modes to instrument

| Failure mode | Why it matters | What v0 records / does |
|---|---|---|
| Malformed actions | Wrong envelopes, duplicate fields, invalid escaping and output truncation can execute the wrong thing or stall a loop | Reject before execution; safe fence repair; bounded corrective retries; preserve raw replies |
| Repeated actions | Re-reading unchanged files and repeating failed edits spend a limited step budget | Count identical actions, warn, then stop; preserve status independently of grader pass |
| Context overflow / forgetting | Growing logs displace task constraints; summaries can discard the evidence needed for a fix | Bound observations and history; retain task; record extractive compaction events |
| Bad edits | Quoting errors, nonunique replacements and whole-file overwrites cause syntax/semantic regressions | Exact-match atomic patching; failures do not mutate files; future syntax validation should be measured |
| False completion | A model can pass its own weak tests or claim a patch succeeded when it did not | Grade independently after the loop; preserve failed and passing submissions |
| Infrastructure failure | Network errors, stalled commands and missing environments otherwise look like model reasoning failures | Separate API/tool/timeout events, observed vs unknown usage, per-task verifier logs |

The first development smoke runs already show malformed finish envelopes and shallow-copy solutions incorrectly judged complete by the model. The final comparative taxonomy in [RESULTS.md](../RESULTS.md) uses actual scored traces. General long-horizon guidance also emphasizes durable progress artifacts and explicit verification to prevent premature completion. [Long-running agent engineering](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents).

## Measurement discipline

Freeze the subset before optimizing, preserve failed attempts, use fresh environments, keep quantization/context/sampling identical, and compare pass rate together with wall time and actual provider-reported tokens. A short local suite can identify mechanical problems; it cannot establish benchmark generalization. After improvements, reserve held-out tasks and obtain the official full-set measurement. No training, benchmark contamination or fabricated score is needed to make the harness useful.
