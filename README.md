# Agent Bench

Agent Bench is an open-source benchmark project for comparing agent frameworks with transparent, reproducible results.

## What This Repo Is For

This repository helps answer one question: which agent framework is the best fit for real end-to-end agent workflows when you consider both task performance and developer experience.

The benchmark is framework-first, not model-first. Results are intended to help teams compare:

- tool-calling reliability and ergonomics
- orchestration primitives and control
- human review quality
- ease of implementation
- lines of code required
- readability
- extensibility
- observability, tracing, and debugging support

## Scoreboard

This is the main comparison view for the current public benchmark runs.

| Framework | Runtime Model Used | Provider-Agnostic? | Task | Run | Task Score | Framework Score | Final Score | Duration | Outcome
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Anthropic Agent SDK | `sonnet-4.6` | `No` | `intake-triage` | `stress_v1/run-001` | `4.75 / 5.0` | `4.625 / 5.0` | `4.688 / 5.0` | `283.857s` | `Pass` |
| OpenAI Agents SDK | `gpt-5.4` | `Yes` | `intake-triage` | `stress_v1/run-003` | `4.75 / 5.0` | `4.162 / 5.0` | `4.456 / 5.0` | `72.222s` | `Pass` |
| LangGraph | `gpt-5.4` | `Yes` | `intake-triage` | `stress_v1/run-001` | `2.475 / 5.0` | `4.2 / 5.0` | `3.338 / 5.0` | `46.232s` | `Partial` |
| LangGraph | `gemini-3.1-pro-preview` | `Yes` | `intake-triage` | `stress_v1/run-002` | `4.25 / 5.0` | `3.85 / 5.0` | `4.05 / 5.0` | `73.916s` | `Pass` |
| CrewAI | `gpt-5.4` | `Yes` | `intake-triage` | `stress_v1/run-001` | `2.475 / 5.0` | `3.8 / 5.0` | `3.138 / 5.0` | `121.142s` | `Partial` |
| AutoGen | `gpt-5.4` | `Yes` | `intake-triage` | `stress_v1/run-001` | `2.475 / 5.0` | `3.8 / 5.0` | `3.138 / 5.0` | `35.261s` | `Partial` |
| Pydantic AI | `gemini-3.1-pro-preview` | `Yes` | `intake-triage` | `stress_v1/run-001` | `2.475 / 5.0` | `4.2 / 5.0` | `3.338 / 5.0` | `172.726s` | `Partial` |
| Pydantic AI | `gpt-5.4` | `Yes` | `intake-triage` | `stress_v1/run-002` | `3.5 / 5.0` | `4.43 / 5.0` | `3.965 / 5.0` | `63.056s` | `Partial` |
| Google ADK | `gemini-3.1-pro-preview` | `Yes` | `intake-triage` | `stress_v1/run-001` | `3.5 / 5.0` | `4.11 / 5.0` | `3.805 / 5.0` | `117.643s` | `Partial` |

Notes:
- `Provider-Agnostic?` here means whether the framework is designed to work as a general multi-provider runtime.
- Anthropic Agent SDK can authenticate through multiple hosting paths for Claude, but it is still Claude-specific rather than provider-agnostic.
- The current recorded runtime models are `sonnet-4.6`, `gpt-5.4`, and `gemini-3.1-pro-preview`.

## Tool Metrics

This table tracks the detailed tool-calling behavior that sits behind the framework score.

| Framework | Run | Tool Pass | Total Calls | Passed Calls | Failed Calls | Unique Tools | Write Calls | Artifacts Produced | Success Rate | Write Completion | Output Coverage | Custom Tool Efficiency |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Anthropic Agent SDK | `stress_v1/run-001` | `Pass` | `39` | `39` | `0` | `4` | `4` | `3 / 4` | `1.0` | `0.75` | `0.75` | `0.875` |
| OpenAI Agents SDK | `stress_v1/run-003` | `Pass` | `44` | `44` | `0` | `4` | `7` | `4 / 4` | `1.0` | `0.571` | `1.0` | `0.893` |
| LangGraph | `stress_v1/run-001` | `Pass` | `16` | `16` | `0` | `3` | `4` | `4 / 4` | `1.0` | `1.0` | `1.0` | `1.0` |
| LangGraph | `stress_v1/run-002` | `Pass` | `16` | `16` | `0` | `3` | `4` | `4 / 4` | `1.0` | `1.0` | `1.0` | `1.0` |
| CrewAI | `stress_v1/run-001` | `Pass` | `16` | `16` | `0` | `3` | `4` | `4 / 4` | `1.0` | `1.0` | `1.0` | `1.0` |
| AutoGen | `stress_v1/run-001` | `Pass` | `21` | `21` | `0` | `4` | `4` | `4 / 4` | `1.0` | `1.0` | `1.0` | `1.0` |
| Pydantic AI | `stress_v1/run-001` | `Pass` | `37` | `37` | `0` | `4` | `8` | `4 / 4` | `1.0` | `0.5` | `1.0` | `0.875` |
| Pydantic AI | `stress_v1/run-002` | `Pass` | `26` | `26` | `0` | `4` | `5` | `4 / 4` | `1.0` | `0.8` | `1.0` | `0.95` |
| Google ADK | `stress_v1/run-001` | `Pass` | `25` | `25` | `0` | `4` | `8` | `4 / 4` | `1.0` | `0.5` | `1.0` | `0.875` |

## Framework Evaluation Notes

This section provides qualitative insights into the developer experience and framework design based on the benchmark runs.

- **Anthropic Agent SDK (`run-001`)**: Framework score derived from deterministic metrics and heuristics.
- **OpenAI Agents SDK (`run-003`)**: Framework score derived from deterministic metrics and heuristics.
- **LangGraph (`run-001`)**: LangGraph provides a robust and highly extensible foundation for agent development. The use of `StateGraph` and prebuilt components like `ToolNode` makes constructing a standard ReAct loop relatively clean, though it requires adopting a graph-based mental model. The implementation is readable and handles tool calling exceptionally well, but relies on manual tracing and an external retry loop rather than fully utilizing the framework's native capabilities for observability and complex cyclic routing.
- **LangGraph (`run-002`)**: The LangGraph implementation showcases a robust, highly extensible graph-based architecture for agent orchestration. While tool calling is seamless, the implementation's reliance on manual tracing and external retry logic adds boilerplate and reduces readability. Overall, it offers excellent control for complex workflows at the cost of a slightly steeper learning curve.
- **CrewAI (`run-001`)**: CrewAI provides a highly readable and easy-to-implement declarative framework for building agents. Its tool calling is reliable, and the abstractions for agents and tasks are intuitive. However, the framework lacks built-in output validation (requiring custom retry loops) and required manual instrumentation for detailed observability. Despite successfully generating all required outputs, the agent struggled with the complex reasoning required for the task, resulting in a partial success.
- **AutoGen (`run-001`)**: Autogen provides a robust, multi-agent paradigm that handles tool execution effectively through its UserProxyAgent. While tool definition is elegantly Pythonic, the dual-agent setup can feel slightly over-engineered for a single-agent task. The framework's biggest drawback in this implementation is the lack of accessible, built-in tracing, which forces developers to manually instrument tool functions to capture observability data.
- **Pydantic AI (`run-001`, `run-002`)**: Pydantic AI offers a highly ergonomic, type-safe, and Pythonic approach to building agents. Its tool-calling and dependency injection mechanisms (`RunContext`) are standout features that make the code clean and maintainable. However, the need for manual tracing inside each tool highlights a gap in out-of-the-box observability hooks for custom logging. When running `gpt-5.4` (`run-002`), the framework executed much faster and with fewer, more efficient tool calls (26 vs 37), but both models still struggled to perfectly match the gold-standard qualitative rubrics for the complex triage reasoning, resulting in partial successes.
- **Google ADK (`run-001`)**: This google-adk implementation is a strong, pragmatic single-agent setup: simple to build, readable, and equipped with enough orchestration and tracing to complete the task reliably. Its biggest strengths are low implementation overhead and good observability for a compact script. Its main limitations are shallow orchestration and low-level tool design, which likely left some quality on the table despite successful artifact generation.

## Current Scope

The current public benchmark focuses on:

- a shared task suite
- reproducible evaluation scripts
- side-by-side framework implementations
- saved result artifacts and score tables

### Supported Frameworks

Currently implemented:
- [Anthropic Agent SDK](https://docs.anthropic.com/en/docs/claude-code/sdk)
- [Google ADK](https://google.github.io/adk-docs/)
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)
- [OpenAI Agents SDK](https://platform.openai.com/docs/guides/agents-sdk/)

Planned:
- [CrewAI](https://docs.crewai.com/en/introduction)
- [AutoGen](https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/index.html)
- [Mastra](https://mastra.ai/)
- [Pydantic AI](https://github.com/pydantic/pydantic-ai)

The first implemented benchmark task is `intake-triage`, and `stress_v1` is the default comparison split.

## Repository Structure

The repository is organized like this:

```text
.
├── .env.example
├── .gitignore
├── CONTRIBUTING.md
├── LICENSE
├── OPEN_SOURCE_CHECKLIST.md
├── pyproject.toml
├── README.md
├── SECURITY.md
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
│   ├── langgraph/
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

## Install

```bash
uv sync
cp .env.example .env
```

The root `.env` should contain:

- `ANTHROPIC_API_KEY` for Anthropic framework runs
- `OPENAI_API_KEY` for OpenAI framework runs
- `GOOGLE_API_KEY` for Google ADK framework runs with Gemini
- `GEMINI_API_KEY` for Gemini-based framework evaluation judging

## Usage

Run commands are grouped by framework below.

<details>
<summary>Anthropic Agent SDK</summary>

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/anthropic-agent-sdk/intake-triage/stress_v1/run-001
```

</details>

<details>
<summary>OpenAI Agents SDK</summary>

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/openai-agents-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/openai-agents-sdk/intake-triage/stress_v1/run-003
```

</details>

<details>
<summary>Google ADK</summary>

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/google-adk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/google-adk/intake-triage/stress_v1/run-001
```

The Google ADK runner defaults to `gemini-3.1-pro-preview` unless `GOOGLE_ADK_MODEL` or `GEMINI_MODEL` is set.

</details>

<details>
<summary>LangGraph</summary>

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/langgraph/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/langgraph/intake-triage/stress_v1/run-001
```

The LangGraph runner defaults to `gpt-5.4` unless `LANGGRAPH_MODEL` or `OPENAI_MODEL` is set.

</details>

<details>
<summary>Re-score Existing Run</summary>

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --skip-agent
```

</details>

<details>
<summary>Skip Judge</summary>

```bash
uv run python evaluation/run_intake_benchmark.py \
  --agent-script frameworks/anthropic-agent-sdk/intake-triage/agent.py \
  --fixture benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --out results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --skip-agent \
  --skip-judge
```

</details>

<details>
<summary>Task-Only Evaluation</summary>

```bash
uv run python evaluation/evaluate_intake_run.py \
  --run-dir results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --fixture-dir benchmarks/intake-triage/stress_v1/fixtures/case-101
```

</details>

<details>
<summary>Framework-Only Evaluation</summary>

```bash
uv run python evaluation/evaluate_framework.py \
  --run-dir results/anthropic-agent-sdk/intake-triage/stress_v1/run-001 \
  --fixture-dir benchmarks/intake-triage/stress_v1/fixtures/case-101 \
  --framework-dir frameworks/anthropic-agent-sdk/intake-triage
```

</details>

## How Evaluation Works

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

- Locked judge target: `Gemini 3.1 Pro Preview`
- Provider: `Google AI Studio`
- Model ID: `gemini-3.1-pro-preview`
- Config file: `evaluation/judge-model.yml`

Current scoring implementation:

- `evaluation/run_intake_benchmark.py` runs the full pipeline end to end
- `evaluation/evaluate_intake_run.py` handles deterministic task scoring
- `evaluation/evaluate_framework.py` handles framework-quality scoring
- Gemini-based judging is used for qualitative framework scoring when `GEMINI_API_KEY` is present
- Deterministic task evaluation remains the hard-gate source of truth
- When the framework runtime exposes it, per-run cost and duration are captured in the saved run artifacts

Current evaluation status:

- Full end-to-end benchmark execution is now implemented for `intake-triage`
- `stress_v1` is the default comparison split
- Framework-quality scoring uses deterministic metrics plus Gemini-assisted judging when configured
- A heuristic fallback is available when Gemini judging is skipped or unavailable


## Public Release Notes

- Internal planning files are not part of the public project surface.
- Result rows should be backed by saved evaluation artifacts in `results/`.
- Shared logic belongs in `common/` and `evaluation/`.
- Framework-specific code belongs in `frameworks/<framework>/<task>/`.

## Community Files

- Contribution guide: [CONTRIBUTING.md](/Users/abubakarsiddik/Desktop/OSS/agent-bench/CONTRIBUTING.md)
- Code of conduct: [CODE_OF_CONDUCT.md](/Users/abubakarsiddik/Desktop/OSS/agent-bench/CODE_OF_CONDUCT.md)
- Security policy: [SECURITY.md](/Users/abubakarsiddik/Desktop/OSS/agent-bench/SECURITY.md)
- Release checklist: [OPEN_SOURCE_CHECKLIST.md](/Users/abubakarsiddik/Desktop/OSS/agent-bench/OPEN_SOURCE_CHECKLIST.md)

## License

This project is released under the [MIT License](/Users/abubakarsiddik/Desktop/OSS/agent-bench/LICENSE).
