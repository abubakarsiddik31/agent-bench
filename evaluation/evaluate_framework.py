import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.evaluation_utils import (
    call_google_ai_studio_json,
    count_non_comment_lines,
    env_or_none,
    list_framework_source_files,
    load_json,
    read_text,
    read_yaml_scalar,
    score_loc_required,
    weighted_average,
)


FRAMEWORK_WEIGHTS = {
    "tool_calling": 20,
    "orchestration": 20,
    "human_review_quality": 10,
    "ease_of_implementation": 10,
    "lines_of_code_required": 10,
    "readability": 10,
    "extensibility": 10,
    "observability": 10,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--fixture-dir", required=True)
    parser.add_argument("--framework-dir", required=True)
    parser.add_argument("--skip-judge", action="store_true")
    return parser.parse_args()


def count_setup_steps() -> int:
    return 1


def analyze_trace(trace_path: Path) -> dict:
    if not trace_path.exists():
        return {"tool_messages": 0, "assistant_messages": 0}

    tool_messages = 0
    assistant_messages = 0
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("type") == "assistant":
            assistant_messages += 1
            for block in payload.get("content", []):
                if block.get("kind") == "tool":
                    tool_messages += 1
    return {
        "tool_messages": tool_messages,
        "assistant_messages": assistant_messages,
    }


def heuristic_scores(
    lines_of_code: int,
    files_touched: int,
    setup_steps: int,
    trace_stats: dict,
    task_summary: dict,
    code_text: str,
) -> tuple[dict[str, float], dict[str, str]]:
    loc_score = score_loc_required(lines_of_code)
    tool_messages = trace_stats.get("tool_messages", 0)
    execution_success = task_summary.get("execution_success", False)
    contract_pass = task_summary.get("contract_pass", False)
    criterion_scores = task_summary.get("criterion_scores", {})

    if execution_success and tool_messages >= 2:
        tool_calling = 4.5
    elif execution_success and tool_messages >= 1:
        tool_calling = 4.0
    elif execution_success:
        tool_calling = 3.0
    else:
        tool_calling = 0.0

    if execution_success and contract_pass:
        orchestration = 4.5
    elif execution_success:
        orchestration = 3.0
    else:
        orchestration = 0.0

    if criterion_scores.get("explanation_quality", 0) >= 4 and criterion_scores.get("actionability", 0) >= 4:
        human_review_quality = 4.5
    elif execution_success:
        human_review_quality = 3.5
    else:
        human_review_quality = 1.0

    setup_score = 5.0 if setup_steps <= 1 else 4.0 if setup_steps == 2 else 3.0
    file_score = 5.0 if files_touched <= 1 else 4.0 if files_touched <= 2 else 3.0
    ease_of_implementation = round((loc_score + setup_score + file_score) / 3, 3)

    average_loc_per_file = lines_of_code / max(files_touched, 1)
    readability = 4.5 if average_loc_per_file <= 140 else 3.5 if average_loc_per_file <= 220 else 2.5

    extensibility = 4.5 if "infer_prompt_pack_path" in code_text and "common." in code_text else 3.5

    observability = 5.0 if execution_success and trace_stats.get("assistant_messages", 0) > 0 else 2.0

    scores = {
        "tool_calling": tool_calling,
        "orchestration": orchestration,
        "human_review_quality": human_review_quality,
        "ease_of_implementation": ease_of_implementation,
        "lines_of_code_required": loc_score,
        "readability": readability,
        "extensibility": extensibility,
        "observability": observability,
    }
    notes = {
        "tool_calling": "Heuristic based on successful execution and tool-message presence in the trace.",
        "orchestration": "Heuristic based on successful end-to-end execution and contract completion.",
        "human_review_quality": "Heuristic based on structured outputs plus explanation/actionability task scores.",
        "ease_of_implementation": "Heuristic based on setup steps, files touched, and framework-specific LOC.",
        "lines_of_code_required": "Deterministic score from framework-specific LOC thresholds.",
        "readability": "Heuristic based on LOC concentration in framework-specific files.",
        "extensibility": "Heuristic based on shared utility usage and dataset inference wiring.",
        "observability": "Heuristic based on trace and artifact availability.",
    }
    return scores, notes


def build_judge_prompt(
    framework_name: str,
    framework_dir: Path,
    implementation_metrics: dict,
    task_summary: dict,
    trace_stats: dict,
    code_files: list[Path],
) -> str:
    code_blocks = []
    for path in code_files:
        relative = path.relative_to(framework_dir.parent.parent)
        code_blocks.append(f"FILE: {relative}\n```python\n{read_text(path)}\n```")

    return f"""
You are evaluating an agent framework implementation, not the underlying model.

Framework: {framework_name}
Task: intake_triage

Implementation metrics:
{json.dumps(implementation_metrics, indent=2)}

Task evaluation summary:
{json.dumps(task_summary, indent=2)}

Trace summary:
{json.dumps(trace_stats, indent=2)}

Framework-specific code:
{chr(10).join(code_blocks)}

Score these criteria from 0.0 to 5.0:
- tool_calling
- orchestration
- human_review_quality
- ease_of_implementation
- readability
- extensibility
- observability

Return JSON only in this shape:
{{
  "tool_calling": {{"score": 0, "reason": "string"}},
  "orchestration": {{"score": 0, "reason": "string"}},
  "human_review_quality": {{"score": 0, "reason": "string"}},
  "ease_of_implementation": {{"score": 0, "reason": "string"}},
  "readability": {{"score": 0, "reason": "string"}},
  "extensibility": {{"score": 0, "reason": "string"}},
  "observability": {{"score": 0, "reason": "string"}},
  "overall_summary": "string"
}}

Important constraints:
- Do not score lines_of_code_required; that is computed separately.
- Focus on framework-specific agent construction code, not shared benchmark utilities.
- Treat task success as evidence, but do not let task success override poor developer ergonomics or weak observability.
""".strip()


def judge_scores_with_gemini(
    framework_name: str,
    framework_dir: Path,
    implementation_metrics: dict,
    task_summary: dict,
    trace_stats: dict,
    code_files: list[Path],
) -> tuple[dict[str, float], dict[str, str], str]:
    api_key = env_or_none("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    model_id = read_yaml_scalar(Path("evaluation/judge-model.yml"), "model_id")
    response = call_google_ai_studio_json(
        model_id=model_id,
        prompt=build_judge_prompt(
            framework_name=framework_name,
            framework_dir=framework_dir,
            implementation_metrics=implementation_metrics,
            task_summary=task_summary,
            trace_stats=trace_stats,
            code_files=code_files,
        ),
        api_key=api_key,
    )

    scores = {}
    notes = {}
    for criterion in [
        "tool_calling",
        "orchestration",
        "human_review_quality",
        "ease_of_implementation",
        "readability",
        "extensibility",
        "observability",
    ]:
        payload = response.get(criterion, {})
        scores[criterion] = round(float(payload.get("score", 0)), 3)
        notes[criterion] = str(payload.get("reason", "")).strip()
    return scores, notes, str(response.get("overall_summary", "")).strip()


def evaluate_framework(run_dir: Path, fixture_dir: Path, framework_dir: Path, skip_judge: bool = False) -> dict:
    task_summary = load_json(run_dir / "evaluation_summary.json")
    framework_name = framework_dir.parent.name
    code_files = list_framework_source_files(framework_dir)
    code_text = "\n\n".join(read_text(path) for path in code_files)
    lines_of_code = sum(count_non_comment_lines(path) for path in code_files)
    files_touched = len(code_files)
    setup_steps = count_setup_steps()
    trace_stats = analyze_trace(run_dir / "agent-trace.jsonl")

    implementation_metrics = {
        "lines_of_code": lines_of_code,
        "files_touched": files_touched,
        "setup_steps": setup_steps,
        "counted_files": [str(path) for path in code_files],
        "excluded_shared_paths": ["common/"],
    }

    heuristic_score_breakdown, heuristic_notes = heuristic_scores(
        lines_of_code=lines_of_code,
        files_touched=files_touched,
        setup_steps=setup_steps,
        trace_stats=trace_stats,
        task_summary=task_summary,
        code_text=code_text,
    )

    judge_mode = "heuristic"
    overall_summary = "Framework score derived from deterministic metrics and heuristics."
    if not skip_judge:
        try:
            judged_scores, judged_notes, overall_summary = judge_scores_with_gemini(
                framework_name=framework_name,
                framework_dir=framework_dir,
                implementation_metrics=implementation_metrics,
                task_summary=task_summary,
                trace_stats=trace_stats,
                code_files=code_files,
            )
            heuristic_score_breakdown.update(judged_scores)
            heuristic_notes.update(judged_notes)
            judge_mode = "gemini"
        except Exception as exc:
            heuristic_notes["judge_fallback"] = str(exc)
            judge_mode = "heuristic_fallback"

    heuristic_score_breakdown["lines_of_code_required"] = score_loc_required(lines_of_code)
    final_score = weighted_average(heuristic_score_breakdown, FRAMEWORK_WEIGHTS)

    summary = {
        "framework": framework_name,
        "task_id": "intake_triage",
        "run_dir": str(run_dir),
        "fixture_dir": str(fixture_dir),
        "judge_mode": judge_mode,
        "implementation_metrics": implementation_metrics,
        "score_breakdown": heuristic_score_breakdown,
        "criterion_notes": heuristic_notes,
        "final_score": final_score,
        "overall_summary": overall_summary,
    }

    output_path = run_dir / "framework_evaluation.json"
    output_path.write_text(f"{json.dumps(summary, indent=2)}\n", encoding="utf-8")

    framework_snapshot = {
        "framework": framework_name,
        "task_id": "intake_triage",
        "reviewer": "gemini_judge" if judge_mode == "gemini" else "heuristic_pipeline",
        "human_rating": final_score,
        "implementation_metrics": {
            "lines_of_code": lines_of_code,
            "files_touched": files_touched,
            "setup_steps": setup_steps,
        },
        "score_breakdown": heuristic_score_breakdown,
        "notes": {
            "fixture_id": fixture_dir.name,
            "judge_mode": judge_mode,
            "framework_evaluation_path": str(output_path),
            "summary": overall_summary,
        },
    }
    (run_dir / "framework_snapshot.json").write_text(
        f"{json.dumps(framework_snapshot, indent=2)}\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    args = parse_args()
    summary = evaluate_framework(
        run_dir=Path(args.run_dir).resolve(),
        fixture_dir=Path(args.fixture_dir).resolve(),
        framework_dir=Path(args.framework_dir).resolve(),
        skip_judge=args.skip_judge,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
