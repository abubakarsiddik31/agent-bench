import json
import os
import sys
import time
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

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


def build_tools(workspace_dir: Path, trace_lines: list[str]) -> list:
    @tool
    def list_workspace_files() -> str:
        """List files available in the current workspace."""
        return list_files_in_workspace(workspace_dir, trace_lines)

    @tool
    def read_workspace_file(path: str) -> str:
        """Read a file from the workspace using a relative path."""
        return read_file_in_workspace(workspace_dir, path, trace_lines)

    @tool
    def search_workspace(query: str) -> str:
        """Search the workspace for a text query and return matching lines with file references."""
        return search_text_in_workspace(workspace_dir, query, trace_lines)

    @tool
    def write_workspace_file(path: str, content: str) -> str:
        """Write a file in the workspace using a relative path."""
        return write_file_in_workspace(workspace_dir, path, content, trace_lines)

    return [
        list_workspace_files,
        read_workspace_file,
        search_workspace,
        write_workspace_file,
    ]


def serialize_message(message: AIMessage) -> dict[str, object]:
    payload: dict[str, object] = {
        "type": "assistant",
        "content": [{"kind": "text", "value": str(message.content)}],
        "usage": to_json_safe(getattr(message, "usage_metadata", None)),
        "response_metadata": to_json_safe(getattr(message, "response_metadata", None)),
    }
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        payload["tool_calls"] = to_json_safe(tool_calls)
    return payload


def sum_usage(messages: Iterable[object]) -> dict[str, float]:
    totals = {
        "input_tokens": 0.0,
        "output_tokens": 0.0,
        "total_tokens": 0.0,
    }
    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        totals["input_tokens"] += float(usage.get("input_tokens", 0) or 0)
        totals["output_tokens"] += float(usage.get("output_tokens", 0) or 0)
        totals["total_tokens"] += float(usage.get("total_tokens", 0) or 0)
    return totals


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


def build_graph(llm_with_tools, tools: list):
    tool_node = ToolNode(tools)

    def call_model(state: MessagesState):
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": [response]}

    def route_model_output(state: MessagesState):
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("assistant", call_model)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "assistant")
    graph.add_conditional_edges("assistant", route_model_output, {"tools": "tools", END: END})
    graph.add_edge("tools", "assistant")
    return graph.compile()


def invoke_graph(graph, messages: list[object]) -> dict:
    return graph.invoke(
        {"messages": messages},
        config={"recursion_limit": 50},
    )


def main() -> None:
    load_dotenv(repo_root(__file__) / ".env")

    fixture_dir, out_dir = parse_args(sys.argv[1:])
    repo_root_path = repo_root(__file__)
    prompt_pack = read_prompt_pack(infer_prompt_pack_path(fixture_dir))
    workspace_dir = out_dir / "workspace"
    trace_path = out_dir / "agent-trace.jsonl"

    out_dir.mkdir(parents=True, exist_ok=True)
    prepare_workspace(repo_root_path, fixture_dir, workspace_dir)

    model_name = os.getenv("LANGGRAPH_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.4"
    trace_lines: list[str] = []
    tools = build_tools(workspace_dir, trace_lines)
    instructions = "\n\n".join(
        [
            prompt_pack["system_prompt"],
            "Use the provided tools to inspect the workspace, search for evidence, and write the required output files.",
            "Do not stop until all required outputs have been written to the workspace root.",
            "If any required output file is missing, continue working and call the write tool until all files exist.",
            f"Required files: {', '.join(REQUIRED_OUTPUTS)}.",
        ]
    )

    if model_name.startswith("gemini"):
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            # stream_usage=True is not universally supported across all providers in the exact same way, but LangChain Google GenAI handles usage naturally
        )
    else:
        llm = ChatOpenAI(
            model=model_name,
            stream_usage=True,
        )
    llm_with_tools = llm.bind_tools(tools, strict=False)
    graph = build_graph(llm_with_tools, tools)

    start_time = time.perf_counter()
    messages: list[object] = [
        SystemMessage(content=instructions),
        HumanMessage(content=build_prompt(prompt_pack)),
    ]
    accumulated_usage = {"input_tokens": 0.0, "output_tokens": 0.0, "total_tokens": 0.0}

    for attempt in range(3):
        previous_count = len(messages)
        state = invoke_graph(graph, messages)
        messages = state["messages"]
        new_messages = messages[previous_count:]
        for message in new_messages:
            if isinstance(message, AIMessage):
                trace_lines.append(json.dumps(serialize_message(message), default=repr))
        new_usage = sum_usage(message for message in new_messages if isinstance(message, AIMessage))
        for key, value in new_usage.items():
            accumulated_usage[key] += value

        missing_outputs = missing_required_outputs(workspace_dir)
        if not missing_outputs:
            break
        if attempt == 2:
            break
        messages = messages + [
            HumanMessage(
                content="\n".join(
                    [
                        "The benchmark run is incomplete.",
                        f"Missing required output files: {', '.join(missing_outputs)}.",
                        "Continue from the current workspace state.",
                        "Use the available tools and write every missing required output file now.",
                        "Do not summarize a plan. Finish by creating the missing files.",
                    ]
                )
            )
        ]

    final_text = ""
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            if isinstance(message.content, str):
                final_text = message.content
            else:
                final_text = json.dumps(to_json_safe(message.content))
            break

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
        "total_cost_usd": estimate_cost_from_usage(accumulated_usage),
        "duration_seconds": duration_seconds,
        "usage": {
            "provider": "langgraph",
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
        framework_name="langgraph",
    )
    write_framework_snapshot(out_dir, fixture_dir, framework_name="langgraph")


if __name__ == "__main__":
    main()
