import json
import shutil
from pathlib import Path


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


def repo_root(from_file: str) -> Path:
    return Path(from_file).resolve().parents[3]


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
            "human_review_quality": 0,
            "ease_of_implementation": 0,
            "lines_of_code_required": 0,
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
