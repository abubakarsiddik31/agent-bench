# PRD: Agent Framework Benchmarking Program

## Summary

This project will benchmark agent frameworks to choose the best-fit framework for this repository's future work. The benchmark will start with a researched longlist of eight frameworks, narrow that set to three finalists through desk research, and then evaluate the finalists across five benchmark tasks.

This PRD defines the benchmark program, decision criteria, task suite, scoring model, and output contract. It does not define the full benchmark harness implementation or the final prompt packs for each task.

## Problem

The agent ecosystem is moving quickly, and framework selection based on popularity alone is unlikely to produce the best long-term fit. This repo needs a structured way to compare frameworks on real work, implementation tradeoffs, and reproducible outcomes before committing to one.

## Goal

Choose the most suitable general-purpose agent framework for this repo by benchmarking a shortlist of three frameworks on practical, end-to-end agent workflows with transparent, repeatable evaluation.

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

## Task Design Principles

The benchmark task suite should reflect realistic end-to-end operational workflows and remain reusable across frameworks.

Rules for task design:

- Use domain-neutral operational scenarios that generalize well across frameworks
- Preserve the same reasoning shape, tool demands, review gates, and end-to-end flow across repeated runs
- Keep evaluation difficulty anchored to realistic workflow complexity, not simplified toy tasks
- Ensure every benchmark task is fully agentic, meaning the agent must plan, use tools, transform data, make intermediate decisions, and produce a reviewable final artifact

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

The benchmark will evaluate five fully agentic benchmark tasks.

### Task Types Covered

The five-task suite intentionally expands beyond the original coding, tool use, and research framing. The benchmark should now cover:

- Document intelligence
- Draft generation and QA
- Intake decisioning
- Natural-language analytics
- Workflow orchestration and exception handling

### Task 1: Archive Review and Structured Findings

**Task type:** document intelligence

The agent receives a large, messy document bundle plus a small reference record. It must ingest the bundle, extract structured facts, reconcile them against the reference data, identify discrepancies, assign confidence, and produce a review packet with source citations.

End-to-end flow:

1. Read the inbound bundle and reference record
2. Extract text or structured content from mixed-quality source files
3. Segment the content into meaningful sections
4. Extract key entities and relationships into a normalized schema
5. Cross-check extracted facts against the reference record
6. Classify findings as clear, needs review, or exception
7. Produce a final structured report and reviewer summary with citations

What it tests:

- Multi-step document understanding
- Evidence-grounded extraction
- Entity resolution across noisy inputs
- Confidence scoring and human-review packaging

### Task 2: Policy-Aware Packet Drafting and Preflight Review

**Task type:** draft generation and QA

The agent receives structured case data, policy rules, and a template/style guide. It must assemble a near-final output document, verify it against rule requirements, flag uncertain sections, and produce both the draft and a preflight QA summary.

End-to-end flow:

1. Gather required structured inputs and rule constraints
2. Select the correct output format and style variant
3. Generate a complete draft, not a partial template fill
4. Run a self-check for completeness, consistency, and rule coverage
5. Highlight uncertain or missing sections
6. Produce a final draft plus QA findings for human approval

What it tests:

- Controlled generation under constraints
- Use of templates, policies, and structured inputs
- Secondary review reasoning before handoff
- Ability to separate mechanical checks from human judgment

### Task 3: Intake Triage, Matching, and Gap Analysis

**Task type:** intake decisioning

The agent receives an inbound intake packet and access to an existing portfolio of records. It must decide whether the packet represents a new record, an update to an existing record, or a likely duplicate; explain why; identify missing data; and recommend the next operational action.

End-to-end flow:

1. Parse the inbound packet into structured fields
2. Search existing records using multiple matching signals
3. Rank candidate matches and decide the most likely disposition
4. Explain the rationale for the disposition
5. Identify missing required and non-blocking fields
6. Produce a triage recommendation, confidence score, and action list

What it tests:

- Multi-signal matching and reasoning
- Decision support with explainability
- Gap detection and prioritization
- Operational handoff quality

### Task 4: Natural-Language Portfolio Investigation

**Task type:** natural-language analytics

The agent receives a user question about a portfolio or dataset and must translate that request into structured retrieval steps, execute the investigation, validate the interpretation, and return an actionable result set with explanation.

End-to-end flow:

1. Interpret the user's natural-language question
2. Translate it into structured filters, aggregations, or retrieval steps
3. Execute the search or analysis over the provided dataset
4. Show the interpreted query in human-readable form
5. Return the matching results or ranked answers
6. Summarize what was found, including limits or ambiguities

What it tests:

- Query interpretation fidelity
- Structured retrieval from natural-language requests
- Result explanation and correction friendliness
- Manager-style analytical assistance

### Task 5: Triggered Verification Sweep and Exception Routing

**Task type:** workflow orchestration and exception handling

The agent receives a queue of records plus trigger conditions and access to one or more external mock systems or tools. It must run the required checks, handle retries or failures, record outcomes, escalate only the exceptions, and update workflow state with a clean audit trail.

End-to-end flow:

1. Read the queue and determine which records require checks
2. Execute the required external lookups or tool-driven verifications
3. Handle rate limits, transient failures, and retries within policy
4. Record routine negative or normal results automatically
5. Escalate positive hits or uncertain outcomes for review
6. Update workflow state and produce an audit summary

What it tests:

- Tool reliability under operational constraints
- Stateful orchestration over multiple records
- Retry logic and exception handling
- Accurate escalation and auditability

## Benchmark Methodology

All finalist frameworks will be evaluated under the same benchmark rules unless a documented framework limitation prevents exact parity.

### Shared Rules

- Use the same model family/provider across finalists where feasible
- Use the same task definitions and success criteria
- Use the same budget envelope per task
- Use the same allowed tool envelope per task
- Run each task three times per framework to reduce one-off variance
- Capture both human-readable and machine-readable outputs for every run

### Normalization Principles

- Normalize evaluation on outcomes, not internal framework architecture
- Avoid introducing framework-specific helper logic that gives one framework an unfair advantage
- Allow each framework to use its native orchestration style if the benchmark contract is preserved
- Record exceptions explicitly whenever parity is imperfect

### Run Matrix

For three shortlisted frameworks, five benchmark tasks, and three repeated runs per task, the v1 benchmark will include:

- 45 total benchmark runs

## Output Contract

Every benchmark run must produce:

- One Markdown summary for human review
- One JSON result for aggregation and comparison

The minimum JSON result schema is:

```json
{
  "framework": "string",
  "task_id": "archive_review | packet_drafting | intake_triage | portfolio_investigation | verification_sweep",
  "task_type": "document_intelligence | draft_generation_and_qa | intake_decisioning | natural_language_analytics | workflow_orchestration",
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
- Task identifier and task type
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
- Repeatable results across all five end-to-end benchmark tasks
- Transparent Markdown and JSON artifacts for every run
- A final recommendation that clearly explains why the winning framework is the best fit

## Deliverables

The benchmark effort should eventually produce:

- A longlist research comparison
- A shortlisted set of three frameworks
- Benchmark task specifications for the five tasks
- YAML task definitions in the `tasks/` directory
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
- Concrete prompt packs and datasets for each task
- Exact task budgets and timeout numbers
- Final directory layout for benchmark harness code and result storage
- Final recommendation once benchmark results exist
