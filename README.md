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

Framework-specific agent code is the primary unit of comparison. Shared helpers should live in a common area and should not dominate framework-level scoring.

The implementation flow is framework-by-framework and task-by-task: implement one task, evaluate it immediately, record framework implementation notes, and then continue to the next task.

The first concrete benchmark package is `intake-triage`, with both a `starter_v1` split for harness validation and a harder `stress_v1` split for real framework comparison.

The first framework implementation has started under `frameworks/anthropic-agent-sdk/intake-triage/`.

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
│   └── benchmark_utils.py
├── frameworks/
│   └── anthropic-agent-sdk/
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
│   ├── judge-model.yml
│   ├── metric-counting-policy.yml
│   └── review-form.yml
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
- `GEMINI_API_KEY` for Google AI Studio evaluation/judging

## Usage

Run the Anthropic starter iteration from the repo root:

```bash
uv run \
  python frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/fixtures/case-001 \
  --out results/anthropic-agent-sdk/intake-triage/starter_v1/run-001
```

Run the harder stress split from the repo root:

```bash
uv run \
  python frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/anthropic-agent-sdk/intake-triage/stress_v1/run-001
```

Evaluate a completed run from the repo root:

```bash
uv run python evaluation/evaluate_intake_run.py \
  --run-dir results/anthropic-agent-sdk/intake-triage/starter_v1/run-003 \
  --fixture-dir benchmarks/intake-triage/fixtures/case-001
```

Evaluate a stress-split run from the repo root:

```bash
uv run python evaluation/evaluate_intake_run.py \
  --run-dir results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --fixture-dir benchmarks/intake-triage/stress_v1/fixtures/case-101
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
   - This includes tool-calling reliability and ergonomics, orchestration primitives and control, human review quality, ease of implementation, lines of code required, readability, extensibility, and observability.
   - Final framework ranking uses both the task-performance score and the framework-quality score.

Evaluation model:

- Locked judge target: `Gemini 3.1 Pro Preview`
- Provider: `Google AI Studio`
- Model ID: `gemini-3.1-pro-preview`
- Config file: `evaluation/judge-model.yml`

Current scoring implementation:

- Deterministic evaluator script handles hard gates, normalized artifact matching, and fixture checks today
- Gemini-based judge assistance is the next layer, not the current hard-gate source of truth

Current evaluation status:

- Execution and deterministic evaluation are working for Anthropic `run-003`
- Deterministic contract evaluation is available through `evaluation/evaluate_intake_run.py`
- Full rubric automation and Gemini-assisted judging are still pending
- `starter_v1` exists for harness validation; `stress_v1` now exists to better separate framework quality

## Scoreboard

This table is the high-level benchmark view. It should reflect both task success and framework quality.

| Framework | Task | Run | Task Score | Tool Calling | Orchestration | Human Review | Ease of Impl | LOC Required | Readability | Extensibility | Observability | Final Score |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Anthropic Agent SDK | `intake-triage` | `run-003` | `5.0 / 5.0` | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending |

## Next Steps

- Complete Stage 1 longlist research and scoring
- Select the final three frameworks for hands-on benchmarking
- Lock the exact provider and model ID in `evaluation/benchmark-execution.yml`
- Install dependencies from the repo root with `uv sync`
- Lock the exact provider and model ID in `evaluation/benchmark-execution.yml`
- Decide whether to keep normalized contract matching or force canonical output filenames in the runner
- Run the new `intake-triage` `stress_v1` fixtures
- Record outputs in `results/anthropic-agent-sdk/intake-triage/starter_v1/`
- Add scoring automation for the new harder split
- Extend the deterministic evaluator with Gemini-based rubric judging
- Lock the execution contract and evaluation policies in `evaluation/`
- Capture framework-level implementation metrics and human ratings alongside task scores
- Add the benchmark harness and result collection structure

## License

Not yet specified.
