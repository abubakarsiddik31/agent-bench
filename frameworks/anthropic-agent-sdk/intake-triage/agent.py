import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, query


REQUIRED_OUTPUTS = [
    "triage_decision.json",
    "candidate_match_table.json",
    "gap_analysis.md",
    "next_actions.md",
]


def parse_args(argv: list[str]) -> tuple[Path, Path]:
    if "--fixture" not in argv or "--out" not in argv:
        raise ValueError("Usage: python agent.py --fixture <path> --out <path>")

    fixture = argv[argv.index("--fixture") + 1]
    out_dir = argv[argv.index("--out") + 1]
    return Path(fixture).resolve(), Path(out_dir).resolve()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def read_prompt_pack(prompt_pack_path: Path) -> dict[str, str]:
    text = prompt_pack_path.read_text(encoding="utf-8")
    return {
        "id": read_yaml_scalar(text, "id"),
        "task_id": read_yaml_scalar(text, "task_id"),
        "dataset_split": read_yaml_scalar(text, "dataset_split"),
        "objective": read_yaml_block(text, "objective"),
        "system_prompt": read_yaml_block(text, "system_prompt"),
        "user_prompt_template": read_yaml_block(text, "user_prompt_template"),
    }


def read_yaml_scalar(text: str, key: str) -> str:
    prefix = f"{key}:"
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    raise ValueError(f"Missing scalar key '{key}' in prompt pack")


def read_yaml_block(text: str, key: str) -> str:
    start_literal = f"{key}: |"
    start_folded = f"{key}: >"
    lines = text.splitlines()

    for index, line in enumerate(lines):
        if line == start_literal:
            return extract_indented_block(lines[index + 1 :], folded=False)
        if line == start_folded:
            return extract_indented_block(lines[index + 1 :], folded=True)

    raise ValueError(f"Missing block key '{key}' in prompt pack")


def extract_indented_block(lines: list[str], *, folded: bool) -> str:
    block: list[str] = []
    for line in lines:
        if not line.startswith("  "):
            break
        block.append(line[2:].rstrip())
    if folded:
        return " ".join(part.strip() for part in block).strip()
    return "\n".join(block).strip()


def prepare_workspace(repo_root_path: Path, fixture_dir: Path, workspace_dir: Path) -> None:
    shared_dir = repo_root_path / "benchmarks" / "intake-triage" / "fixtures" / "shared"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    for item in fixture_dir.iterdir():
        destination = workspace_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)

    shutil.copytree(shared_dir, workspace_dir / "shared", dirs_exist_ok=True)


def build_prompt(prompt_pack: dict[str, str]) -> str:
    return (
        f"{prompt_pack['objective']}\n\n"
        f"{prompt_pack['user_prompt_template']}\n\n"
        "Use the files in the current directory and the ./shared directory. "
        "Write the required outputs into the current directory."
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


def collect_output_presence(workspace_dir: Path) -> dict[str, bool]:
    return {file_name: (workspace_dir / file_name).exists() for file_name in REQUIRED_OUTPUTS}


def write_run_result(
    out_dir: Path,
    fixture_dir: Path,
    prompt_pack: dict[str, str],
    output_presence: dict[str, bool],
    trace_path: Path,
) -> None:
    fixture_id = fixture_dir.name
    payload = {
        "framework": "anthropic-agent-sdk",
        "task_id": prompt_pack["task_id"],
        "task_type": "intake_decisioning",
        "run_id": f"{prompt_pack['dataset_split']}-{fixture_id}",
        "outcome": "partial" if all(output_presence.values()) else "fail",
        "score_breakdown": {
            "output_quality_and_task_success": 0,
            "reliability_and_repeatability": 0,
            "human_review_quality": 0,
            "tooling_tracing_and_observability": 0,
            "runtime_speed": 0,
            "cost_efficiency": 0,
        },
        "duration": {"unit": "seconds", "value": 0},
        "cost": {"currency": "USD", "value": 0},
        "notes": {
            "prompt_pack_id": prompt_pack["id"],
            "fixture_id": fixture_id,
            "trace_path": str(trace_path),
            "output_presence": output_presence,
            "status": "Scoring is pending evaluator implementation.",
        },
    }
    (out_dir / "run_result.json").write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def write_framework_snapshot(out_dir: Path, fixture_dir: Path) -> None:
    payload = {
        "framework": "anthropic-agent-sdk",
        "task_id": "intake_triage",
        "reviewer": "TBD",
        "human_rating": 0,
        "implementation_metrics": {
            "lines_of_code": 0,
            "files_touched": 0,
            "setup_steps": 0,
        },
        "score_breakdown": {
            "tool_calling": 0,
            "orchestration": 0,
            "ease_of_use": 0,
            "readability": 0,
            "extensibility": 0,
            "observability": 0,
        },
        "notes": {
            "fixture_id": fixture_dir.name,
            "status": "Human framework review is pending.",
        },
    }
    (out_dir / "framework_snapshot.json").write_text(
        f"{json.dumps(payload, indent=2)}\n",
        encoding="utf-8",
    )


async def main() -> None:
    load_dotenv(repo_root() / ".env")

    fixture_dir, out_dir = parse_args(sys.argv[1:])
    repo_root_path = repo_root()
    prompt_pack = read_prompt_pack(repo_root_path / "benchmarks" / "intake-triage" / "prompt-pack.yml")
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
