import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.benchmark_utils import (  # noqa: E402
    build_prompt,
    collect_output_presence,
    infer_prompt_pack_path,
    parse_args,
    prepare_workspace,
    read_prompt_pack,
    repo_root,
    write_framework_snapshot,
    write_run_result,
)


async def run_agent(prompt: str, workspace_dir: Path, system_prompt: str) -> list[str]:
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="acceptEdits",
        cwd=str(workspace_dir),
        system_prompt=system_prompt,
        max_turns=25,
    )

    trace_lines: list[str] = []
    async for message in query(prompt=prompt, options=options):
        trace_lines.append(format_message(message))
    return trace_lines


def format_message(message: object) -> str:
    if isinstance(message, AssistantMessage):
        return json.dumps(
            {
                "type": "assistant",
                "content": [serialize_block(block) for block in message.content],
            }
        )
    if isinstance(message, ResultMessage):
        return json.dumps(
            {
                "type": "result",
                "subtype": getattr(message, "subtype", "unknown"),
            }
        )
    return json.dumps({"type": message.__class__.__name__})


def serialize_block(block: object) -> dict[str, str]:
    if hasattr(block, "text"):
        return {"kind": "text", "value": getattr(block, "text")}
    if hasattr(block, "name"):
        return {"kind": "tool", "value": getattr(block, "name")}
    return {"kind": "unknown", "value": block.__class__.__name__}


async def main() -> None:
    load_dotenv(repo_root(__file__) / ".env")

    fixture_dir, out_dir = parse_args(sys.argv[1:])
    repo_root_path = repo_root(__file__)
    prompt_pack = read_prompt_pack(infer_prompt_pack_path(fixture_dir))
    workspace_dir = out_dir / "workspace"
    trace_path = out_dir / "agent-trace.jsonl"

    out_dir.mkdir(parents=True, exist_ok=True)
    prepare_workspace(repo_root_path, fixture_dir, workspace_dir)

    trace_lines = await run_agent(
        build_prompt(prompt_pack),
        workspace_dir,
        prompt_pack["system_prompt"],
    )
    trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")

    output_presence = collect_output_presence(workspace_dir)
    write_run_result(out_dir, fixture_dir, prompt_pack, output_presence, trace_path)
    write_framework_snapshot(out_dir, fixture_dir)


if __name__ == "__main__":
    asyncio.run(main())
