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

The detailed benchmark plan lives in [.plans/agent-framework-benchmark-prd.md](.plans/agent-framework-benchmark-prd.md).

## Planned Repository Structure

This repo is still early, but the intended structure is:

```text
.
├── .plans/
│   └── agent-framework-benchmark-prd.md
├── README.md
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
├── benchmarks/   # TBD
└── results/      # TBD
```

## Status

Project initialized. The first PRD for benchmark design is now in place. Benchmark tasks, harness code, and result storage are still to be defined.

## Install

`TBD`

## Usage

`TBD`

## Next Steps

- Complete Stage 1 longlist research and scoring
- Select the final three frameworks for hands-on benchmarking
- Define the concrete prompt packs and datasets for the five task specs in `tasks/`
- Implement evaluators that apply the rubric definitions in `rubrics/`
- Lock the execution contract and evaluation policies in `evaluation/`
- Capture framework-level implementation metrics and human ratings alongside task scores
- Add the benchmark harness and result collection structure

## License

Not yet specified.
