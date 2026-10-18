import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.evaluation_utils import (
    call_openai_responses_json,
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
        return {
            "tool_messages": 0,
            "assistant_messages": 0,
            "tool_calls_by_name": {},
            "unique_tools": [],
            "failed_tool_calls_detected": 0,
            "passed_tool_calls_detected": 0,
            "write_calls": 0,
            "read_like_calls": 0,
        }

    tool_messages = 0
    assistant_messages = 0
    tool_calls_by_name: dict[str, int] = {}
    failed_tool_calls_detected = 0
    write_calls = 0
    read_like_calls = 0

    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload_type = payload.get("type")
        if payload_type == "assistant":
            assistant_messages += 1
            for block in payload.get("content", []):
                if block.get("kind") == "tool":
                    tool_messages += 1
                    tool_name = str(block.get("value", "unknown"))
                    tool_calls_by_name[tool_name] = tool_calls_by_name.get(tool_name, 0) + 1
                    lowered = tool_name.lower()
                    if "write" in lowered or lowered == "edit":
                        write_calls += 1
                    if any(name in lowered for name in ["read", "grep", "glob", "search", "list", "bash"]):
                        read_like_calls += 1
        elif payload_type == "ToolCallItem":
            tool_messages += 1
            raw_item = payload.get("raw_item", {})
            tool_name = str(raw_item.get("name", "unknown"))
            tool_calls_by_name[tool_name] = tool_calls_by_name.get(tool_name, 0) + 1
            lowered = tool_name.lower()
            if "write" in lowered or lowered == "edit":
                write_calls += 1
            if any(name in lowered for name in ["read", "grep", "glob", "search", "list", "bash"]):
                read_like_calls += 1
            if str(raw_item.get("status", "")).lower() in {"failed", "error"}:
                failed_tool_calls_detected += 1
        elif payload_type == "MessageOutputItem":
            assistant_messages += 1
        elif payload_type in {"tool_error", "error"}:
            failed_tool_calls_detected += 1

    failed_tool_calls_detected = min(failed_tool_calls_detected, tool_messages)
    passed_tool_calls_detected = max(tool_messages - failed_tool_calls_detected, 0)
    return {
        "tool_messages": tool_messages,
        "assistant_messages": assistant_messages,
        "tool_calls_by_name": tool_calls_by_name,
        "unique_tools": sorted(tool_calls_by_name.keys()),
        "failed_tool_calls_detected": failed_tool_calls_detected,
        "passed_tool_calls_detected": passed_tool_calls_detected,
        "write_calls": write_calls,
        "read_like_calls": read_like_calls,
    }


def compute_tool_call_metrics(trace_stats: dict, task_summary: dict) -> dict:
    total_calls = int(trace_stats.get("tool_messages", 0))
    failed_calls = int(trace_stats.get("failed_tool_calls_detected", 0))
    passed_calls = int(trace_stats.get("passed_tool_calls_detected", 0))
    write_calls = int(trace_stats.get("write_calls", 0))
    normalized_outputs = task_summary.get("normalized_output_presence", {})
    produced_outputs = sum(1 for value in normalized_outputs.values() if value)
    expected_outputs = len(normalized_outputs) if normalized_outputs else 0

    tool_call_success_rate = round(passed_calls / total_calls, 3) if total_calls else 0.0
    write_completion_rate = round(produced_outputs / write_calls, 3) if write_calls else 0.0
    output_coverage_rate = round(produced_outputs / expected_outputs, 3) if expected_outputs else 0.0
    custom_tool_efficiency = round(
        ((tool_call_success_rate * 0.5) + (write_completion_rate * 0.25) + (output_coverage_rate * 0.25)),
        3,
    )

    return {
        "total_tool_calls": total_calls,
        "passed_tool_calls_detected": passed_calls,
        "failed_tool_calls_detected": failed_calls,
        "tool_calls_by_name": trace_stats.get("tool_calls_by_name", {}),
        "unique_tools_used": trace_stats.get("unique_tools", []),
        "write_calls": write_calls,
        "read_like_calls": int(trace_stats.get("read_like_calls", 0)),
        "required_artifacts_expected": expected_outputs,
        "required_artifacts_produced": produced_outputs,
        "tool_call_success_rate": tool_call_success_rate,
        "write_completion_rate": write_completion_rate,
        "output_coverage_rate": output_coverage_rate,
        "custom_tool_efficiency": custom_tool_efficiency,
        "tool_call_passed": failed_calls == 0 and total_calls > 0,
    }


def heuristic_scores(
    lines_of_code: int,
    files_touched: int,
    setup_steps: int,
    trace_stats: dict,
    task_summary: dict,
    code_text: str,
    tool_metrics: dict,
) -> tuple[dict[str, float], dict[str, str]]:
    loc_score = score_loc_required(lines_of_code)
    execution_success = task_summary.get("execution_success", False)
    contract_pass = task_summary.get("contract_pass", False)
    criterion_scores = task_summary.get("criterion_scores", {})

    success_rate = float(tool_metrics.get("tool_call_success_rate", 0))
    efficiency = float(tool_metrics.get("custom_tool_efficiency", 0))
    total_calls = int(tool_metrics.get("total_tool_calls", 0))
    if execution_success and total_calls > 0:
        tool_calling = round(
            min(
                5.0,
                2.5 + (success_rate * 1.5) + (efficiency * 1.0),
            ),
            3,
        )
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
        "tool_calling": (
            "Heuristic based on detected tool-call counts, pass/fail detection, output coverage, "
            f"and custom tool efficiency ({tool_metrics.get('custom_tool_efficiency')})."
        ),
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


def judge_scores_with_openai(
    framework_name: str,
    framework_dir: Path,
    implementation_metrics: dict,
    task_summary: dict,
    trace_stats: dict,
    code_files: list[Path],
) -> tuple[dict[str, float], dict[str, str], str]:
    api_key = env_or_none("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    model_id = read_yaml_scalar(Path("evaluation/judge-model.yml"), "model_id")
    response = call_openai_responses_json(
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
        schema_name="framework_judge_scores",
        schema={
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "tool_calling": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                },
                "orchestration": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                },
                "human_review_quality": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                },
                "ease_of_implementation": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                },
                "readability": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                },
                "extensibility": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                },
                "observability": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "score": {"type": "number"},
                        "reason": {"type": "string"},
                    },
                    "required": ["score", "reason"],
                },
                "overall_summary": {"type": "string"},
            },
            "required": [
                "tool_calling",
                "orchestration",
                "human_review_quality",
                "ease_of_implementation",
                "readability",
                "extensibility",
                "observability",
                "overall_summary",
            ],
        },
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
    load_dotenv(REPO_ROOT / ".env")

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
    tool_metrics = compute_tool_call_metrics(trace_stats, task_summary)

    heuristic_score_breakdown, heuristic_notes = heuristic_scores(
        lines_of_code=lines_of_code,
        files_touched=files_touched,
        setup_steps=setup_steps,
        trace_stats=trace_stats,
        task_summary=task_summary,
        code_text=code_text,
        tool_metrics=tool_metrics,
    )

    judge_mode = "heuristic"
    overall_summary = "Framework score derived from deterministic metrics and heuristics."
    if not skip_judge:
        try:
            judge_provider = read_yaml_scalar(Path("evaluation/judge-model.yml"), "provider")
            if judge_provider == "openai":
                judged_scores, judged_notes, overall_summary = judge_scores_with_openai(
                    framework_name=framework_name,
                    framework_dir=framework_dir,
                    implementation_metrics=implementation_metrics,
                    task_summary=task_summary,
                    trace_stats=trace_stats,
                    code_files=code_files,
                )
                judge_mode = "openai"
            elif judge_provider == "google_ai_studio":
                judged_scores, judged_notes, overall_summary = judge_scores_with_gemini(
                    framework_name=framework_name,
                    framework_dir=framework_dir,
                    implementation_metrics=implementation_metrics,
                    task_summary=task_summary,
                    trace_stats=trace_stats,
                    code_files=code_files,
                )
                judge_mode = "gemini"
            else:
                raise RuntimeError(f"Unsupported judge provider: {judge_provider}")
            heuristic_score_breakdown.update(judged_scores)
            heuristic_notes.update(judged_notes)
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
        "tool_call_metrics": tool_metrics,
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
        "reviewer": "openai_judge" if judge_mode == "openai" else "gemini_judge" if judge_mode == "gemini" else "heuristic_pipeline",
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
