import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.messages import ModelRequest, ModelResponse

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.benchmark_utils import (
    REQUIRED_OUTPUTS,
    build_prompt,
    collect_output_presence,
    infer_prompt_pack_path,
    list_files_in_workspace,
    missing_required_outputs,
    parse_args,
    prepare_workspace,
    read_file_in_workspace,
    read_prompt_pack,
    repo_root,
    search_text_in_workspace,
    to_json_safe,
    write_file_in_workspace,
    write_framework_snapshot,
    write_run_result,
)


class AgentDeps:
    def __init__(self, workspace_dir: Path, trace_lines: list[str]):
        self.workspace_dir = workspace_dir
        self.trace_lines = trace_lines


# Initialize Agent
agent = Agent(
    'openai:gpt-4o',  # Default, will be overridden
    deps_type=AgentDeps,
)


@agent.tool
def list_workspace_files(ctx: RunContext[AgentDeps]) -> str:
    """List files available in the current workspace."""
    return list_files_in_workspace(ctx.deps.workspace_dir, ctx.deps.trace_lines)


@agent.tool
def read_workspace_file(ctx: RunContext[AgentDeps], path: str) -> str:
    """Read a file from the workspace using a relative path."""
    return read_file_in_workspace(ctx.deps.workspace_dir, path, ctx.deps.trace_lines)


@agent.tool
def search_workspace(ctx: RunContext[AgentDeps], query: str) -> str:
    """Search the workspace for a text query and return matching lines with file references."""
    return search_text_in_workspace(ctx.deps.workspace_dir, query, ctx.deps.trace_lines)


@agent.tool
def write_workspace_file(ctx: RunContext[AgentDeps], path: str, content: str) -> str:
    """Write a file in the workspace using a relative path."""
    return write_file_in_workspace(ctx.deps.workspace_dir, path, content, ctx.deps.trace_lines)


def estimate_cost_from_usage(totals: dict[str, int | float], model_name: str) -> Optional[float]:
    input_tokens = float(totals.get("input_tokens", 0) or 0)
    output_tokens = float(totals.get("output_tokens", 0) or 0)
    
    input_cost = os.getenv("OPENAI_INPUT_COST_PER_1M")
    output_cost = os.getenv("OPENAI_OUTPUT_COST_PER_1M")
    if not input_cost or not output_cost:
        return None
    try:
        input_rate = float(input_cost)
        output_rate = float(output_cost)
    except ValueError:
        return None
    total = (input_tokens / 1_000_000 * input_rate) + (
        output_tokens / 1_000_000 * output_rate
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

    model_name = os.getenv("PYDANTIC_AI_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.4"
    
    # Configure model
    if model_name.startswith("gemini"):
        model = GoogleModel(model_name)
    else:
        # Assume OpenAI compatible for anything else
        model = OpenAIModel(model_name)

    agent.model = model
    
    trace_lines: list[str] = []
    deps = AgentDeps(workspace_dir, trace_lines)
    
    instructions = "\n\n".join(
        [
            prompt_pack["system_prompt"],
            "Use the provided tools to inspect the workspace, search for evidence, and write the required output files.",
            "Do not stop until all required outputs have been written to the workspace root.",
            "If any required output file is missing, continue working and call the write tool until all files exist.",
            f"Required files: {', '.join(REQUIRED_OUTPUTS)}.",
        ]
    )
    
    agent.system_prompt = instructions

    start_time = time.perf_counter()
    
    accumulated_usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0
    }

    message_history = None
    
    for attempt in range(3):
        prompt = build_prompt(prompt_pack) if attempt == 0 else \
                 f"The benchmark run is incomplete. Missing required output files: {', '.join(missing_required_outputs(workspace_dir))}. Continue from the current workspace state. Use the available tools and write every missing required output file now. Do not summarize a plan. Finish by creating the missing files."
        
        result = agent.run_sync(prompt, deps=deps, message_history=message_history)
        message_history = result.all_messages()
        
        # Record trace
        for msg in result.new_messages():
            role = "unknown"
            if isinstance(msg, ModelRequest):
                role = "user"
            elif isinstance(msg, ModelResponse):
                role = "assistant"
            trace_lines.append(json.dumps({"type": "message", "role": role, "content": str(msg)}, default=repr))
            
        # Update usage
        usage = result.usage()
        accumulated_usage["input_tokens"] += (getattr(usage, 'input_tokens', 0) or 0)
        accumulated_usage["output_tokens"] += (getattr(usage, 'output_tokens', 0) or 0)
        accumulated_usage["total_tokens"] += (getattr(usage, 'total_tokens', 0) or 0)

        missing_outputs = missing_required_outputs(workspace_dir)
        if not missing_outputs:
            break

    final_text = result.output
    trace_lines.append(
        json.dumps(
            {
                "type": "final_output",
                "value": str(final_text),
                "usage": to_json_safe(accumulated_usage),
                "model": model_name,
            }
        )
    )

    duration_seconds = round(time.perf_counter() - start_time, 3)
    trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    output_presence = collect_output_presence(workspace_dir)
    runtime_metadata = {
        "total_cost_usd": estimate_cost_from_usage(accumulated_usage, model_name),
        "duration_seconds": duration_seconds,
        "usage": {
            "provider": "pydantic-ai",
            "model": model_name,
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
        framework_name="pydantic-ai",
    )
    write_framework_snapshot(out_dir, fixture_dir, framework_name="pydantic-ai")

if __name__ == "__main__":
    main()
