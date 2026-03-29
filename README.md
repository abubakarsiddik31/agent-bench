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

The implementation flow is framework-by-framework and task-by-task: implement one task, evaluate it immediately, record framework implementation notes, and then continue to the next task.

The first concrete benchmark package is `intake-triage`, with a starter prompt pack, shared policies, and gold fixtures under `benchmarks/intake-triage/`.

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
│       └── fixtures/
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

## Usage

Run the first Anthropic starter iteration from the repo root:

```bash
uv run \
  python frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/fixtures/case-001 \
  --out results/anthropic-agent-sdk/intake-triage/starter_v1/run-001
```

## Next Steps

- Complete Stage 1 longlist research and scoring
- Select the final three frameworks for hands-on benchmarking
- Lock the exact provider and model ID in `evaluation/benchmark-execution.yml`
- Install dependencies from the repo root with `uv sync`
- Lock the exact provider and model ID in `evaluation/benchmark-execution.yml`
- Run the Anthropic `intake-triage` implementation against the starter fixtures
- Record outputs in `results/anthropic-agent-sdk/intake-triage/starter_v1/`
- Implement evaluators that apply the rubric definitions in `rubrics/`
- Lock the execution contract and evaluation policies in `evaluation/`
- Capture framework-level implementation metrics and human ratings alongside task scores
- Add the benchmark harness and result collection structure

## License

Not yet specified.
