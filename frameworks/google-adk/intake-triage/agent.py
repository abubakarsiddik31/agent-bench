import inspect
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from google.adk.agents import LlmAgent  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from common.benchmark_utils import (  # noqa: E402
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
    def list_workspace_files() -> str:
        """List files available in the current workspace."""
        append_tool_trace(trace_lines, "list_workspace_files", {})
        files = []
        for path in sorted(workspace_dir.rglob("*")):
            if path.is_file():
                files.append(str(path.relative_to(workspace_dir)))
        return "\n".join(files)

    def read_workspace_file(path: str) -> str:
        """Read a file from the workspace using a relative path."""
        append_tool_trace(trace_lines, "read_workspace_file", {"path": path})
        return safe_path(workspace_dir, path).read_text(encoding="utf-8")

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


def ensure_session(session_service: InMemorySessionService, *, app_name: str, user_id: str, session_id: str) -> None:
    created = session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id,
    )
    if inspect.isawaitable(created):
        import asyncio

        asyncio.run(created)


def run_once(
    runner: Runner,
    *,
    user_id: str,
    session_id: str,
    prompt: str,
    trace_lines: list[str],
) -> str:
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    final_output = ""
    events = runner.run(user_id=user_id, session_id=session_id, new_message=content)

    for event in events:
        if not getattr(event, "content", None):
            continue
        parts = getattr(event.content, "parts", []) or []
        text_parts = [part.text for part in parts if getattr(part, "text", None)]
        is_final = False
        try:
            is_final = bool(event.is_final_response())
        except Exception:
            is_final = False
        if is_final and text_parts:
            final_output = "\n".join(text_parts).strip()

    trace_lines.append(
        json.dumps(
            {
                "type": "final_output",
                "value": final_output,
            }
        )
    )
    return final_output


def main() -> None:
    load_dotenv(repo_root(__file__) / ".env")
    if not os.getenv("GOOGLE_API_KEY") and os.getenv("GEMINI_API_KEY"):
        os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

    fixture_dir, out_dir = parse_args(sys.argv[1:])
    repo_root_path = repo_root(__file__)
    prompt_pack = read_prompt_pack(infer_prompt_pack_path(fixture_dir))
    workspace_dir = out_dir / "workspace"
    trace_path = out_dir / "agent-trace.jsonl"

    out_dir.mkdir(parents=True, exist_ok=True)
    prepare_workspace(repo_root_path, fixture_dir, workspace_dir)

    model_name = os.getenv("GOOGLE_ADK_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-3.1-pro-preview"
    trace_lines: list[str] = []
    tools = build_tools(workspace_dir, trace_lines)
    instructions = "\n\n".join(
        [
            prompt_pack["system_prompt"],
            "Use the provided tools to inspect the workspace, search for evidence, and write the required output files.",
            "Do not stop until all required outputs have been written to the workspace root.",
            "If any required output file is missing, continue working and call the write tool until all files exist.",
        ]
    )

    agent = LlmAgent(
        name="intake_triage_agent",
        model=model_name,
        instruction=instructions,
        tools=tools,
    )

    app_name = "agent_bench_google_adk"
    user_id = "benchmark_user"
    session_id = f"intake_triage_{fixture_dir.name}"
    session_service = InMemorySessionService()
    ensure_session(session_service, app_name=app_name, user_id=user_id, session_id=session_id)
    runner = Runner(agent=agent, app_name=app_name, session_service=session_service)

    start_time = time.perf_counter()
    run_once(
        runner,
        user_id=user_id,
        session_id=session_id,
        prompt=build_prompt(prompt_pack),
        trace_lines=trace_lines,
    )

    for _ in range(2):
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
        run_once(
            runner,
            user_id=user_id,
            session_id=session_id,
            prompt=followup_prompt,
            trace_lines=trace_lines,
        )

    duration_seconds = round(time.perf_counter() - start_time, 3)
    trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    output_presence = collect_output_presence(workspace_dir)
    runtime_metadata = {
        "total_cost_usd": None,
        "duration_seconds": duration_seconds,
        "usage": {
            "provider": "google_adk",
            "model": model_name,
        },
    }
    write_run_result(
        out_dir,
        fixture_dir,
        prompt_pack,
        output_presence,
        trace_path,
        runtime_metadata,
        framework_name="google-adk",
    )
    write_framework_snapshot(out_dir, fixture_dir, framework_name="google-adk")


if __name__ == "__main__":
    main()
