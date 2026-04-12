import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from crewai import Agent, Crew, Process, Task
from crewai.tools import tool

from common.benchmark_utils import (
    REQUIRED_OUTPUTS,
    build_prompt,
    collect_output_presence,
    infer_prompt_pack_path,
    parse_args,
    prepare_workspace,
    read_prompt_pack,
    repo_root,
    to_json_safe,
    write_framework_snapshot,
    write_run_result,
)


def safe_path(workspace_dir: Path, relative_path: str) -> Path:
    path = (workspace_dir / relative_path).resolve()
    if workspace_dir.resolve() not in path.parents and path != workspace_dir.resolve():
        raise ValueError(f"Path must stay inside workspace: {relative_path}")
    return path


def missing_required_outputs(workspace_dir: Path) -> list[str]:
    presence = collect_output_presence(workspace_dir)
    return [file_name for file_name, exists in presence.items() if not exists]


def append_tool_trace(trace_lines: list[str], tool_name: str, payload: object) -> None:
    trace_lines.append(
        json.dumps(
            {
                "type": "assistant",
                "content": [{"kind": "tool", "value": tool_name}],
                "payload": to_json_safe(payload),
            }
        )
    )


def build_tools(workspace_dir: Path, trace_lines: list[str]) -> list:
    @tool("list_workspace_files")
    def list_workspace_files() -> str:
        """List files available in the current workspace."""
        append_tool_trace(trace_lines, "list_workspace_files", {})
        files = []
        for path in sorted(workspace_dir.rglob("*")):
            if path.is_file():
                files.append(str(path.relative_to(workspace_dir)))
        return "\n".join(files)

    @tool("read_workspace_file")
    def read_workspace_file(path: str) -> str:
        """Read a file from the workspace using a relative path."""
        append_tool_trace(trace_lines, "read_workspace_file", {"path": path})
        return safe_path(workspace_dir, path).read_text(encoding="utf-8")

    @tool("search_workspace")
    def search_workspace(query: str) -> str:
        """Search the workspace for a text query and return matching lines with file references."""
        append_tool_trace(trace_lines, "search_workspace", {"query": query})
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

    @tool("write_workspace_file")
    def write_workspace_file(path: str, content: str) -> str:
        """Write a file in the workspace using a relative path."""
        append_tool_trace(
            trace_lines,
            "write_workspace_file",
            {"path": path, "content_preview": content[:200]},
        )
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


def estimate_cost_from_usage(totals: dict[str, float]) -> float | None:
    input_cost = os.getenv("OPENAI_INPUT_COST_PER_1M")
    output_cost = os.getenv("OPENAI_OUTPUT_COST_PER_1M")
    if not input_cost or not output_cost:
        return None
    try:
        input_rate = float(input_cost)
        output_rate = float(output_cost)
    except ValueError:
        return None
    total = (totals["input_tokens"] / 1_000_000 * input_rate) + (
        totals["output_tokens"] / 1_000_000 * output_rate
    )
    return round(total, 8)


def main() -> None:
    load_dotenv(repo_root(__file__) / ".env")

    fixture_dir, out_dir = parse_args(sys.argv[1:])
    repo_root_path = repo_root(__file__)
    prompt_pack = read_prompt_pack(infer_prompt_pack_path(fixture_dir))
    workspace_dir = out_dir / "workspace"
    trace_path = out_dir / "agent-trace.jsonl"

    out_dir.mkdir(parents=True, exist_ok=True)
    prepare_workspace(repo_root_path, fixture_dir, workspace_dir)

    raw_model_name = os.getenv("CREWAI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.4"
    
    # litellm expects provider prefixes
    if raw_model_name.startswith("gemini"):
        model_string = f"gemini/{raw_model_name}"
    else:
        model_string = raw_model_name # defaults to openai

    trace_lines: list[str] = []
    tools = build_tools(workspace_dir, trace_lines)

    system_prompt_instruction = prompt_pack["system_prompt"]
    
    triage_agent = Agent(
        role='Intake Triage Specialist',
        goal='Evaluate incoming vendor proposals against policies and make accurate triage decisions.',
        backstory=system_prompt_instruction,
        verbose=False,
        allow_delegation=False,
        tools=tools,
        llm=model_string
    )

    accumulated_usage = {"input_tokens": 0.0, "output_tokens": 0.0, "total_tokens": 0.0}
    start_time = time.perf_counter()
    
    final_text = ""

    for attempt in range(3):
        if attempt == 0:
            task_description = "\n\n".join(
                [
                    build_prompt(prompt_pack),
                    "Use the provided tools to inspect the workspace, search for evidence, and write the required output files.",
                    "Do not stop until all required outputs have been written to the workspace root.",
                    f"Required files: {', '.join(REQUIRED_OUTPUTS)}.",
                ]
            )
        else:
            missing_outputs = missing_required_outputs(workspace_dir)
            task_description = "\n".join(
                [
                    "The benchmark run is incomplete.",
                    f"Missing required output files: {', '.join(missing_outputs)}.",
                    "Continue from the current workspace state.",
                    "Use the available tools and write every missing required output file now.",
                    "Do not summarize a plan. Finish by creating the missing files.",
                ]
            )

        triage_task = Task(
            description=task_description,
            expected_output="All required output files successfully written to the workspace.",
            agent=triage_agent
        )

        crew = Crew(
            agents=[triage_agent],
            tasks=[triage_task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()
        
        # CrewAI token usage (litellm standardizes this mostly, but we fetch from crew.usage_metrics)
        if hasattr(crew, 'usage_metrics') and crew.usage_metrics:
            metrics = crew.usage_metrics
            if hasattr(metrics, 'prompt_tokens'):
                accumulated_usage["input_tokens"] += metrics.prompt_tokens or 0
                accumulated_usage["output_tokens"] += metrics.completion_tokens or 0
                accumulated_usage["total_tokens"] += metrics.total_tokens or 0
            elif isinstance(metrics, dict):
                accumulated_usage["input_tokens"] += metrics.get('prompt_tokens', 0)
                accumulated_usage["output_tokens"] += metrics.get('completion_tokens', 0)
                accumulated_usage["total_tokens"] += metrics.get('total_tokens', 0)

        final_text = str(result)
        trace_lines.append(json.dumps({"type": "message", "role": "assistant", "content": final_text}, default=repr))

        if not missing_required_outputs(workspace_dir):
            break

    trace_lines.append(
        json.dumps(
            {
                "type": "final_output",
                "value": final_text,
                "usage": to_json_safe(accumulated_usage),
                "model": raw_model_name,
            }
        )
    )

    duration_seconds = round(time.perf_counter() - start_time, 3)
    trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    output_presence = collect_output_presence(workspace_dir)
    runtime_metadata = {
        "total_cost_usd": estimate_cost_from_usage(accumulated_usage),
        "duration_seconds": duration_seconds,
        "usage": {
            "provider": "crewai",
            "model": raw_model_name,
            "usage_metadata": accumulated_usage,
        },
    }
    
    write_run_result(
        out_dir,
        fixture_dir,
        prompt_pack,
        output_presence,
        trace_path,
        runtime_metadata,
        framework_name="crewai",
    )
    write_framework_snapshot(out_dir, fixture_dir, framework_name="crewai")


if __name__ == "__main__":
    main()
