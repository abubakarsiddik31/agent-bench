# Agent Bench

Benchmarking agent frameworks with transparent, reproducible results to help choose the best-fit framework.

## Background

This repository exists to compare agent frameworks in a structured way instead of choosing one based on hype, familiarity, or isolated demos. The initial focus is a small, practical benchmark that can grow over time.

## Goals

- Research a longlist of candidate agent frameworks
- Shortlist three frameworks for hands-on evaluation
- Benchmark those finalists across five end-to-end agent tasks
- Produce Markdown and JSON outputs that make results easy to review and reproduce

## Benchmark Approach

The benchmark will begin with desk research across a longlist of frameworks and then narrow to three finalists. Those finalists will be compared on the same benchmark tasks, with shared success criteria and repeat runs where feasible.

The benchmark is intended to evaluate frameworks, not models. Task results are only one part of the decision; the benchmark will also compare tool calling, orchestration, human review quality, ease of use, implementation effort, readability, extensibility, and observability.
The framework scorecard uses these explicit dimensions: tool-calling reliability and ergonomics, orchestration primitives and control, human review quality, ease of implementation, lines of code required, readability, extensibility, and observability.
Tool-calling evaluation includes both how easy it is to add a new tool and how confident we are that the model will call that tool correctly in practice.

Framework-specific agent code is the primary unit of comparison. Shared helpers should live in a common area and should not dominate framework-level scoring.

The implementation flow is framework-by-framework and task-by-task: implement one task, evaluate it immediately, record framework implementation notes, and then continue to the next task.

The first concrete benchmark package is `intake-triage`, and `stress_v1` is the default comparison split.

The first framework implementations have started under `frameworks/anthropic-agent-sdk/intake-triage/`, `frameworks/openai-agents-sdk/intake-triage/`, and `frameworks/google-adk/intake-triage/`.

The detailed benchmark plan lives in [.plans/agent-framework-benchmark-prd.md](.plans/agent-framework-benchmark-prd.md).

## Planned Repository Structure

This repo is still early, but the intended structure is:

```text
.
├── .plans/
│   └── agent-framework-benchmark-prd.md
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── benchmarks/
│   ├── README.md
│   └── intake-triage/
│       ├── prompt-pack.yml
│       ├── fixtures/
│       └── stress_v1/
├── common/
│   ├── benchmark_utils.py
│   └── evaluation_utils.py
├── frameworks/
│   ├── anthropic-agent-sdk/
│   │   └── intake-triage/
│   │       └── agent.py
│   ├── google-adk/
│   │   └── intake-triage/
│   │       └── agent.py
│   └── openai-agents-sdk/
│       └── intake-triage/
│           └── agent.py
├── tasks/
│   ├── archive-review.yml
│   ├── intake-triage.yml
│   ├── packet-drafting.yml
│   ├── portfolio-investigation.yml
│   └── verification-sweep.yml
├── rubrics/
│   ├── shared-evaluation.yml
│   ├── framework-evaluation.yml
│   ├── archive-review.yml
│   ├── intake-triage.yml
│   ├── packet-drafting.yml
│   ├── portfolio-investigation.yml
│   └── verification-sweep.yml
├── evaluation/
│   ├── benchmark-execution.yml
│   ├── evaluate_intake_run.py
│   ├── evaluate_framework.py
│   ├── judge-model.yml
│   ├── metric-counting-policy.yml
│   ├── review-form.yml
│   └── run_intake_benchmark.py
├── results/
│   └── README.md
```

## Status

Project initialized. The benchmark design docs are in place, and the first concrete benchmark package now exists for `intake-triage`. Framework implementations and actual run artifacts are the next step.

## Install

```bash
uv sync
cp .env.example .env
```

The root `.env` should contain:

- `ANTHROPIC_API_KEY` for Anthropic framework runs
- `OPENAI_API_KEY` for OpenAI framework runs and GPT-5.4 evaluation judging
- `GOOGLE_API_KEY` for Google ADK framework runs with Gemini

## Usage

Run the full Anthropic benchmark from the repo root:

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/anthropic-agent-sdk/intake-triage/stress_v1/run-001
```

Run the OpenAI Agents SDK benchmark for the same task:

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/openai-agents-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/openai-agents-sdk/intake-triage/stress_v1/run-001
```

Run the Google ADK benchmark for the same task:

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/google-adk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/google-adk/intake-triage/stress_v1/run-001
```

The Google ADK runner defaults to `gemini-3.1-pro-preview` unless `GOOGLE_ADK_MODEL` or `GEMINI_MODEL` is set.

Re-score an existing run without calling the agent again:

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --skip-agent
```

Run the same pipeline without GPT-5.4 judging:

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --skip-agent \
  --skip-judge
```

Evaluate only the task contract from the repo root:

```bash
uv run python evaluation/evaluate_intake_run.py \
  --run-dir results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --fixture-dir benchmarks/intake-triage/stress_v1/fixtures/case-101
```

Evaluate only the framework score from the repo root:

```bash
uv run python evaluation/evaluate_framework.py \
  --run-dir results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --fixture-dir benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --framework-dir frameworks/anthropic-agent-sdk/intake-triage
```

## Evaluation Flow

Evaluation happens in two layers:

1. Task evaluation
   - The agent runs against a fixed prompt pack and fixture set.
   - We inspect the produced artifacts against the task contract and rubric.
   - Hard gates check whether required files, formats, and core outputs are present.
   - If the contract is violated, the run can fail even if the agent produced something useful.

2. Framework evaluation
   - After task execution, we record implementation and operator experience.
   - This includes tool-calling reliability and ergonomics, ease of adding new tools, confidence in correct tool invocation, orchestration primitives and control, human review quality, ease of implementation, lines of code required, readability, extensibility, and observability.
   - Final framework ranking uses both the task-performance score and the framework-quality score.

Evaluation model:

- Locked judge target: `GPT-5.4`
- Provider: `OpenAI`
- Model ID: `gpt-5.4`
- Config file: `evaluation/judge-model.yml`

Current scoring implementation:

- `evaluation/run_intake_benchmark.py` runs the full pipeline end to end
- `evaluation/evaluate_intake_run.py` handles deterministic task scoring
- `evaluation/evaluate_framework.py` handles framework-quality scoring
- GPT-5.4-based judging is used for qualitative framework scoring when `OPENAI_API_KEY` is present
- Deterministic task evaluation remains the hard-gate source of truth
- When the framework runtime exposes it, per-run cost and duration are captured in the saved run artifacts

Current evaluation status:

- Full end-to-end benchmark execution is now implemented for `intake-triage`
- `stress_v1` is the default comparison split
- Framework-quality scoring uses deterministic metrics plus GPT-5.4-assisted judging when configured
- A heuristic fallback is available when GPT-5.4 judging is skipped or unavailable

## Scoreboard

This table is the high-level benchmark view. It should reflect both task success and framework quality.

| Framework | Task | Run | Task Score | Tool Calling | Orchestration | Human Review | Ease of Impl | LOC Required | Readability | Extensibility | Observability | Cost | Duration | Final Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Anthropic Agent SDK | `intake-triage` | `stress_v1/run-001` | `4.75 / 5.0` | `4.875` | `4.5` | `3.5` | `5.0` | `5.0` | `4.5` | `4.5` | `5.0` | `$0.4601` | `283.857s` | `4.688 / 5.0` |
| OpenAI Agents SDK | `intake-triage` | `stress_v1/run-003` | `4.75 / 5.0` | `4.893` | `4.5` | `3.5` | `4.333` | `3.0` | `2.5` | `4.5` | `5.0` | `$0.11` | `72.222s` | `4.456 / 5.0` |
| Google ADK | `intake-triage` | `stress_v1/run-001` | `3.5 / 5.0` | `4.2` | `4.0` | `4.1` | `4.6` | `3.0` | `4.5` | `4.1` | `4.4` | `Not recorded` | `117.643s` | `3.805 / 5.0` |

## Next Steps

- Complete Stage 1 longlist research and scoring
- Select the final three frameworks for hands-on benchmarking
- Lock the exact provider and model ID in `evaluation/benchmark-execution.yml`
- Install dependencies from the repo root with `uv sync`
- Decide whether to keep normalized contract matching or force canonical output filenames in the runner
- Run the new `intake-triage` `stress_v1` fixtures
- Tune the deterministic evaluator against the harder split
- Improve framework judging prompts and reviewer overrides
- Lock the execution contract and evaluation policies in `evaluation/`
- Add final framework rollups across multiple tasks and runs

## License

Not yet specified.
