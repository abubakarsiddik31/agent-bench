import json
import os
import sys
import time
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import autogen
from autogen import AssistantAgent, UserProxyAgent

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

def estimate_cost_from_usage(usage_dict: dict, model_name: str) -> float | None:
    if not usage_dict:
        return None
    input_cost = os.getenv("OPENAI_INPUT_COST_PER_1M")
    output_cost = os.getenv("OPENAI_OUTPUT_COST_PER_1M")
    if not input_cost or not output_cost:
        return None
    try:
        input_rate = float(input_cost)
        output_rate = float(output_cost)
    except ValueError:
        return None
        
    input_tokens = usage_dict.get("prompt_tokens", 0)
    output_tokens = usage_dict.get("completion_tokens", 0)
    
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

    model_name = os.getenv("AUTOGEN_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.4"

    llm_config = {
        "config_list": [{"model": model_name}],
        "cache_seed": None, # disable caching for benchmarks
    }
    
    if model_name.startswith("gemini"):
        llm_config["config_list"][0]["api_type"] = "google"
        llm_config["config_list"][0]["api_key"] = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    else:
        llm_config["config_list"][0]["api_key"] = os.getenv("OPENAI_API_KEY")

    trace_lines: list[str] = []

    # Define tools
    def list_workspace_files() -> Annotated[str, "List files available in the current workspace."]:
        append_tool_trace(trace_lines, "list_workspace_files", {})
        files = []
        for path in sorted(workspace_dir.rglob("*")):
            if path.is_file():
                files.append(str(path.relative_to(workspace_dir)))
        return "\n".join(files)

    def read_workspace_file(path: Annotated[str, "The relative path to the file"]) -> Annotated[str, "Read a file from the workspace."]:
        append_tool_trace(trace_lines, "read_workspace_file", {"path": path})
        return safe_path(workspace_dir, path).read_text(encoding="utf-8")

    def search_workspace(query: Annotated[str, "The text query to search for"]) -> Annotated[str, "Search the workspace for a text query and return matching lines."]:
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

    def write_workspace_file(path: Annotated[str, "The relative path"], content: Annotated[str, "The complete content to write"]) -> Annotated[str, "Write a file in the workspace."]:
        append_tool_trace(
            trace_lines,
            "write_workspace_file",
            {"path": path, "content_preview": content[:200]},
        )
        target = safe_path(workspace_dir, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {target.relative_to(workspace_dir)}"

    system_prompt = "\n\n".join(
        [
            prompt_pack["system_prompt"],
            "Use the provided tools to inspect the workspace, search for evidence, and write the required output files.",
            "Do not stop until all required outputs have been written to the workspace root.",
            "If any required output file is missing, call the write tool until all files exist.",
            f"Required files: {', '.join(REQUIRED_OUTPUTS)}.",
            "Reply 'TERMINATE' to end the conversation when you verify all files are written.",
        ]
    )

    assistant = AssistantAgent(
        name="assistant",
        system_message=system_prompt,
        llm_config=llm_config,
    )
    
    user_proxy = UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        is_termination_msg=lambda x: x.get("content", "") and "TERMINATE" in x.get("content", ""),
        code_execution_config=False,
    )

    # Register tools
    autogen.agentchat.register_function(
        list_workspace_files,
        caller=assistant,
        executor=user_proxy,
        name="list_workspace_files",
        description="List files available in the current workspace.",
    )
    autogen.agentchat.register_function(
        read_workspace_file,
        caller=assistant,
        executor=user_proxy,
        name="read_workspace_file",
        description="Read a file from the workspace using a relative path.",
    )
    autogen.agentchat.register_function(
        search_workspace,
        caller=assistant,
        executor=user_proxy,
        name="search_workspace",
        description="Search the workspace for a text query and return matching lines with file references.",
    )
    autogen.agentchat.register_function(
        write_workspace_file,
        caller=assistant,
        executor=user_proxy,
        name="write_workspace_file",
        description="Write a file in the workspace using a relative path.",
    )

    start_time = time.perf_counter()

    for attempt in range(3):
        if attempt == 0:
            prompt = build_prompt(prompt_pack)
            user_proxy.initiate_chat(assistant, message=prompt)
        else:
            missing_outputs = missing_required_outputs(workspace_dir)
            if not missing_outputs:
                break
            prompt = "\n".join(
                [
                    "The benchmark run is incomplete.",
                    f"Missing required output files: {', '.join(missing_outputs)}.",
                    "Continue from the current workspace state.",
                    "Use the available tools and write every missing required output file now.",
                    "Do not summarize a plan. Finish by creating the missing files.",
                ]
            )
            user_proxy.send(recipient=assistant, message=prompt)

        # Extract tracing manually from chat history for observability
        chat_history = user_proxy.chat_messages[assistant]
        
        # Only log the last message as final output in the trace if we hit our condition
        missing_outputs = missing_required_outputs(workspace_dir)
        if not missing_outputs:
            break

    # Get aggregated usage
    client = assistant.client
    usage_summary = client.actual_usage_summary if hasattr(client, 'actual_usage_summary') else {}
    
    # We fetch total cost if available
    cost = estimate_cost_from_usage(usage_summary, model_name)
    
    accumulated_usage = {
        "input_tokens": usage_summary.get('prompt_tokens', 0),
        "output_tokens": usage_summary.get('completion_tokens', 0),
        "total_tokens": usage_summary.get('total_tokens', 0),
    }

    final_text = ""
    if user_proxy.chat_messages and assistant in user_proxy.chat_messages:
        last_message = user_proxy.chat_messages[assistant][-1]
        final_text = last_message.get("content", "")

    trace_lines.append(
        json.dumps(
            {
                "type": "final_output",
                "value": final_text,
                "usage": to_json_safe(accumulated_usage),
                "model": model_name,
            }
        )
    )

    duration_seconds = round(time.perf_counter() - start_time, 3)
    trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    output_presence = collect_output_presence(workspace_dir)
    runtime_metadata = {
        "total_cost_usd": cost,
        "duration_seconds": duration_seconds,
        "usage": {
            "provider": "autogen",
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
        framework_name="autogen",
    )
    write_framework_snapshot(out_dir, fixture_dir, framework_name="autogen")


if __name__ == "__main__":
    main()
