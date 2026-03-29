# PRD: Agent Framework Benchmarking Program

## Summary

This project will benchmark agent frameworks to choose the best-fit framework for this repository's future work. The benchmark will start with a researched longlist of eight frameworks, narrow that set to three finalists through desk research, and then evaluate the finalists across three task categories: coding, tool use, and research.

This PRD defines the benchmark program, decision criteria, scoring model, and output contract. It does not define the full benchmark harness implementation or the concrete prompts for each task category.

## Problem

The agent ecosystem is moving quickly, and framework selection based on popularity alone is unlikely to produce the best long-term fit. This repo needs a structured way to compare frameworks on real work, implementation tradeoffs, and reproducible outcomes before committing to one.

## Goal

Choose the most suitable general-purpose agent framework for this repo by benchmarking a shortlist of three frameworks on practical tasks with transparent, repeatable evaluation.

## Non-Goals

- Building the benchmark harness in this document
- Choosing the final three frameworks before longlist review is completed
- Defining final benchmark prompts in this version of the PRD
- Optimizing for a narrow single-use case such as voice-only agents or chatbot-only flows

## Users and Decision Audience

- Primary user: the repo maintainer running and reviewing benchmarks
- Secondary audience: collaborators who need to understand why a framework was chosen
- Decision owner: the repo maintainer, informed by benchmark results and implementation effort

## Benchmark Decision

The benchmark will answer one decision:

Which agent framework is the best overall fit for this repo's general-purpose agent use cases when balancing output quality, reliability, developer experience, observability, speed, and cost?

## Candidate Longlist

The benchmark will begin with the following eight frameworks and official resources, using these as the v1 longlist as of March 29, 2026:

| Framework | Official resource | Notes for evaluation |
| --- | --- | --- |
| Claude Agent SDK | [docs.anthropic.com/en/docs/claude-code/sdk](https://docs.anthropic.com/en/docs/claude-code/sdk) | Strong fit to coding and tool-using workflows; evaluate SDK maturity and observability. |
| OpenAI Agents SDK | [platform.openai.com/docs/guides/agents-sdk/](https://platform.openai.com/docs/guides/agents-sdk/) | Strong default baseline for hosted-agent workflows and structured tooling. |
| Google ADK | [google.github.io/adk-docs/](https://google.github.io/adk-docs/) | Evaluate orchestration model, tooling ergonomics, and ecosystem fit. |
| LangGraph | [docs.langchain.com/oss/python/langgraph/overview](https://docs.langchain.com/oss/python/langgraph/overview) | Evaluate graph-based orchestration, control, and production readiness. |
| CrewAI | [docs.crewai.com/en/introduction](https://docs.crewai.com/en/introduction) | Evaluate multi-agent ergonomics and developer setup complexity. |
| AutoGen | [microsoft.github.io/autogen/stable/user-guide/core-user-guide/index.html](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/index.html) | Evaluate event-driven multi-agent primitives and practical overhead. |
| Mastra | [mastra.ai](https://mastra.ai/) | Evaluate modern TypeScript agent workflow primitives and observability. |
| Pydantic AI | [github.com/pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | Evaluate typed outputs, tool ergonomics, and simplicity for benchmark tasks. |

## Shortlist Funnel

The framework selection process will happen in two stages.

### Stage 1: Desk Research

Each of the eight frameworks will be scored before any hands-on benchmark work begins. Stage 1 is intended to reduce the longlist to the three best candidates for deeper evaluation.

Each framework will be scored on:

- Maturity
- Documentation quality
- Observability and tracing support
- Tool support
- Orchestration support
- Ecosystem fit for this repo

Stage 1 output:

- A comparison table covering all eight frameworks
- A short rationale for each score
- A top-three shortlist for hands-on benchmarking

### Stage 2: Hands-On Benchmarking

Only the top three frameworks from Stage 1 will move forward.

Rules for Stage 2:

- Each framework should be used in its strongest first-party language/runtime rather than forcing all finalists into one language.
- The comparison must be normalized through shared task definitions, success criteria, budgets, and result formats.
- The same model family/provider should be used where feasible across finalists.
- If a framework cannot support the shared benchmark conditions cleanly, the limitation must be documented as part of the evaluation.

## Benchmark Scope

The benchmark will evaluate three task categories. This PRD intentionally defines categories rather than concrete prompts.

### 1. Coding

A repo-scoped implementation or debugging task that requires file edits and some form of validation.

The task should test:

- Ability to understand repo context
- Ability to make correct code changes
- Ability to use tools or checks during implementation
- Ability to produce a complete, reviewable outcome

### 2. Tool Use

A multi-step workflow that requires tool invocation, environment interaction, and structured completion.

The task should test:

- Tool invocation reliability
- State handling across multiple steps
- Correct sequencing of operations
- Clear final reporting

### 3. Research

A grounded synthesis task that requires collecting evidence and producing sourced conclusions.

The task should test:

- Source quality and grounding
- Accuracy of synthesis
- Clarity of final output
- Ability to stay within task constraints

## Benchmark Methodology

All finalist frameworks will be evaluated under the same benchmark rules unless a documented framework limitation prevents exact parity.

### Shared Rules

- Use the same model family/provider across finalists where feasible
- Use the same task category definitions and success criteria
- Use the same budget envelope per task category
- Use the same allowed tool envelope per task category
- Run each task category three times per framework to reduce one-off variance
- Capture both human-readable and machine-readable outputs for every run

### Normalization Principles

- Normalize evaluation on outcomes, not internal framework architecture
- Avoid introducing framework-specific helper logic that gives one framework an unfair advantage
- Allow each framework to use its native orchestration style if the benchmark contract is preserved
- Record exceptions explicitly whenever parity is imperfect

### Run Matrix

For three shortlisted frameworks, three task categories, and three repeated runs per category, the v1 benchmark will include:

- 27 total benchmark runs

## Output Contract

Every benchmark run must produce:

- One Markdown summary for human review
- One JSON result for aggregation and comparison

The minimum JSON result schema is:

```json
{
  "framework": "string",
  "task_category": "coding | tool_use | research",
  "run_id": "string",
  "outcome": "pass | partial | fail",
  "score_breakdown": {
    "output_quality_and_task_success": 0,
    "reliability_and_repeatability": 0,
    "developer_experience_and_implementation_effort": 0,
    "tooling_tracing_and_observability": 0,
    "runtime_speed": 0,
    "cost_efficiency": 0
  },
  "duration": {
    "unit": "seconds",
    "value": 0
  },
  "cost": {
    "currency": "USD",
    "value": 0
  },
  "notes": "string"
}
```

The Markdown summary for each run should include:

- Framework name
- Task category
- Run identifier
- Short execution summary
- Outcome
- Major strengths and failures
- Cost and duration
- Notes on benchmark fairness or framework-specific constraints

## Scoring Model

The benchmark will use a balanced scorecard with fixed weights:

| Criterion | Weight |
| --- | --- |
| Output quality and task success | 35% |
| Reliability and repeatability | 20% |
| Developer experience and implementation effort | 15% |
| Tooling, tracing, and observability | 10% |
| Runtime speed | 10% |
| Cost efficiency | 10% |

Scoring guidance:

- Use a consistent numerical scale for all criteria across all frameworks
- Apply the same rubric to every repeated run
- Aggregate scores at both run level and framework level
- Preserve raw notes alongside numerical results to support final interpretation

## Success Criteria

This PRD is successful when it enables the next implementation pass to proceed without needing new documentation decisions.

The benchmark program is successful when it produces:

- A ranked comparison of three shortlisted frameworks
- Repeatable results across coding, tool use, and research tasks
- Transparent Markdown and JSON artifacts for every run
- A final recommendation that clearly explains why the winning framework is the best fit

## Deliverables

The benchmark effort should eventually produce:

- A longlist research comparison
- A shortlisted set of three frameworks
- Benchmark task specifications for the three categories
- Per-run Markdown summaries
- Per-run JSON result files
- An aggregate comparison report with final recommendation

## Constraints and Defaults

- This benchmark is for general-purpose agent framework selection
- The README should remain lightweight until the benchmark harness exists
- The benchmark should prefer fairness and reproducibility over framework-specific optimization
- Missing parity between frameworks should be documented rather than hidden

## Open TBD Items

These items are intentionally deferred to later planning or implementation:

- Final shortlist after Stage 1 scoring
- Concrete benchmark prompts for each task category
- Exact task budgets and timeout numbers
- Final directory layout for benchmark harness code and result storage
- Final recommendation once benchmark results exist
