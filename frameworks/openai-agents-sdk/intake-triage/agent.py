import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents import Agent, ModelSettings, Runner, function_tool
from common.benchmark_utils import (
    build_prompt,
    collect_output_presence,
    infer_prompt_pack_path,
    parse_args,
    prepare_workspace,
    read_prompt_pack,
    repo_root,
    to_json_safe,
    REQUIRED_OUTPUTS,
    write_framework_snapshot,
    write_run_result,
)


def safe_path(workspace_dir: Path, relative_path: str) -> Path:
    path = (workspace_dir / relative_path).resolve()
    if workspace_dir.resolve() not in path.parents and path != workspace_dir.resolve():
        raise ValueError(f"Path must stay inside workspace: {relative_path}")
    return path


def build_tools(workspace_dir: Path) -> list:
    @function_tool
    def list_workspace_files() -> str:
        """List files available in the current workspace."""
        files = []
        for path in sorted(workspace_dir.rglob("*")):
            if path.is_file():
                files.append(str(path.relative_to(workspace_dir)))
        return "\n".join(files)

    @function_tool
    def read_workspace_file(path: str) -> str:
        """Read a file from the workspace using a relative path."""
        return safe_path(workspace_dir, path).read_text(encoding="utf-8")

    @function_tool
    def search_workspace(query: str) -> str:
        """Search the workspace for a text query and return matching lines with file references."""
        matches: list[str] = []
        lowered_query = query.lower()
        for path in sorted(workspace_dir.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for index, line in enumerate(text.splitlines(), start=1):
                if lowered_query in line.lower():
                    matches.append(f"{path.relative_to(workspace_dir)}:{index}: {line}")
        return "\n".join(matches[:200]) if matches else "No matches found."

    @function_tool
    def write_workspace_file(path: str, content: str) -> str:
        """Write a file in the workspace using a relative path."""
        target = safe_path(workspace_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {target.relative_to(workspace_dir)}"

    return [
        list_workspace_files,
        read_workspace_file,
        search_workspace,
        write_workspace_file,
    ]


def serialize_trace_item(item: object) -> dict[str, object]:
    item_type = item.__class__.__name__
    data = {"type": item_type}
    raw_item = getattr(item, "raw_item", None)
    if raw_item is not None:
        data["raw_item"] = to_json_safe(raw_item)
    agent = getattr(item, "agent", None)
    if agent is not None and hasattr(agent, "name"):
        data["agent"] = agent.name
    return data


def serialize_usage(usage: object) -> object:
    return to_json_safe(usage)


def estimate_cost_from_usage(usage: object) -> float | None:
    if usage is None:
        return None

    input_cost = os.getenv("OPENAI_INPUT_COST_PER_1M")
    output_cost = os.getenv("OPENAI_OUTPUT_COST_PER_1M")
    if not input_cost or not output_cost:
        return None

    try:
        input_rate = float(input_cost)
        output_rate = float(output_cost)
        input_tokens = float(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = float(getattr(usage, "output_tokens", 0) or 0)
    except ValueError:
        return None

    total = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
    return round(total, 8)


def usage_totals(usage: object) -> dict[str, float]:
    return {
        "requests": float(getattr(usage, "requests", 0) or 0),
        "input_tokens": float(getattr(usage, "input_tokens", 0) or 0),
        "output_tokens": float(getattr(usage, "output_tokens", 0) or 0),
        "total_tokens": float(getattr(usage, "total_tokens", 0) or 0),
    }


def accumulate_usage(total: dict[str, float], usage: object) -> dict[str, float]:
    usage_values = usage_totals(usage)
    return {
        key: total.get(key, 0.0) + usage_values.get(key, 0.0)
        for key in {"requests", "input_tokens", "output_tokens", "total_tokens"}
    }


def estimate_cost_from_totals(totals: dict[str, float]) -> float | None:
    input_cost = os.getenv("OPENAI_INPUT_COST_PER_1M")
    output_cost = os.getenv("OPENAI_OUTPUT_COST_PER_1M")
    if not input_cost or not output_cost:
        return None
    try:
        input_rate = float(input_cost)
        output_rate = float(output_cost)
    except ValueError:
        return None
    total = (totals.get("input_tokens", 0.0) / 1_000_000 * input_rate) + (
        totals.get("output_tokens", 0.0) / 1_000_000 * output_rate
    )
    return round(total, 8)


def missing_required_outputs(workspace_dir: Path) -> list[str]:
    presence = collect_output_presence(workspace_dir)
    return [file_name for file_name, exists in presence.items() if not exists]


def run_once(agent: Agent, prompt: str, trace_lines: list[str]) -> object:
    result = Runner.run_sync(agent, prompt, max_turns=25)
    usage = getattr(result.context_wrapper, "usage", None)
    trace_lines.append(
        json.dumps(
            {
                "type": "final_output",
                "value": to_json_safe(result.final_output),
                "last_agent": getattr(result.last_agent, "name", None),
                "usage": serialize_usage(usage),
            }
        )
    )
    for item in getattr(result, "new_items", []):
        trace_lines.append(json.dumps(serialize_trace_item(item), default=repr))
    return result


def main() -> None:
    load_dotenv(repo_root(__file__) / ".env")

    fixture_dir, out_dir = parse_args(sys.argv[1:])
    repo_root_path = repo_root(__file__)
    prompt_pack = read_prompt_pack(infer_prompt_pack_path(fixture_dir))
    workspace_dir = out_dir / "workspace"
    trace_path = out_dir / "agent-trace.jsonl"

    out_dir.mkdir(parents=True, exist_ok=True)
    prepare_workspace(repo_root_path, fixture_dir, workspace_dir)

    model_name = os.getenv("OPENAI_AGENT_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4.1-mini"
    tools = build_tools(workspace_dir)
    instructions = "\n\n".join(
        [
            prompt_pack["system_prompt"],
            "Use the provided tools to inspect the workspace, search for evidence, and write the required output files.",
            "Do not stop until all required outputs have been written to the workspace root.",
            "If any required output file is missing, continue working and call the write tool until all files exist.",
        ]
    )

    agent = Agent(
        name="Intake Triage Agent",
        instructions=instructions,
        model=model_name,
        tools=tools,
        model_settings=ModelSettings(
            tool_choice="required",
            include_usage=True,
        ),
    )

    trace_lines: list[str] = []
    start_time = time.perf_counter()
    aggregated_usage = {
        "requests": 0.0,
        "input_tokens": 0.0,
        "output_tokens": 0.0,
        "total_tokens": 0.0,
    }

    result = run_once(agent, build_prompt(prompt_pack), trace_lines)
    usage = getattr(result.context_wrapper, "usage", None)
    aggregated_usage = accumulate_usage(aggregated_usage, usage)

    for attempt in range(2):
        missing_outputs = missing_required_outputs(workspace_dir)
        if not missing_outputs:
            break
        followup_prompt = "\n".join(
            [
                "The previous pass stopped before the benchmark was complete.",
                f"Missing required output files: {', '.join(missing_outputs)}.",
                "Continue from the current workspace state.",
                "Use the available tools and write every missing required output file now.",
                f"Required files: {', '.join(REQUIRED_OUTPUTS)}.",
                "Do not summarize a plan. Finish by creating the missing files.",
            ]
        )
        result = run_once(agent, followup_prompt, trace_lines)
        usage = getattr(result.context_wrapper, "usage", None)
        aggregated_usage = accumulate_usage(aggregated_usage, usage)

    duration_seconds = round(time.perf_counter() - start_time, 3)
    runtime_metadata = {
        "total_cost_usd": estimate_cost_from_totals(aggregated_usage) or estimate_cost_from_usage(usage),
        "duration_seconds": duration_seconds,
        "usage": {
            "aggregated": to_json_safe(aggregated_usage),
            "last_run": serialize_usage(usage),
        },
    }
    trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    output_presence = collect_output_presence(workspace_dir)
    write_run_result(
        out_dir,
        fixture_dir,
        prompt_pack,
        output_presence,
        trace_path,
        runtime_metadata,
        framework_name="openai-agents-sdk",
    )
    write_framework_snapshot(out_dir, fixture_dir, framework_name="openai-agents-sdk")


if __name__ == "__main__":
    main()
