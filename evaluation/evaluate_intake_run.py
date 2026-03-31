import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.evaluation_utils import (
    load_json,
    parse_markdown_sections,
    read_text,
    try_load_json,
    weighted_average,
)


CANONICAL_OUTPUTS = {
    "triage_decision.json": [
        ("root", "triage_decision.json"),
        ("root", "triage-decision.json"),
        ("workspace", "triage_decision.json"),
        ("workspace", "triage-decision.json"),
        ("workspace", "decision.json"),
    ],
    "candidate_match_table.json": [
        ("root", "candidate_match_table.json"),
        ("root", "candidate-match-table.json"),
        ("workspace", "candidate_match_table.json"),
        ("workspace", "candidate-match-table.json"),
        ("workspace", "match-table.json"),
    ],
    "gap_analysis.md": [
        ("root", "gap_analysis.md"),
        ("root", "gap-analysis.md"),
        ("workspace", "gap_analysis.md"),
        ("workspace", "gap-analysis.md"),
        ("workspace", "gap-analysis.json"),
    ],
    "next_actions.md": [
        ("root", "next_actions.md"),
        ("root", "next-actions.md"),
        ("workspace", "next_actions.md"),
        ("workspace", "next-actions.md"),
        ("workspace", "action-plan.json"),
    ],
}

TASK_WEIGHTS = {
    "matching_accuracy": 25,
    "policy_application": 20,
    "explanation_quality": 20,
    "gap_prioritization": 15,
    "actionability": 10,
    "confidence_calibration": 10,
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "but",
    "by",
    "do",
    "exact",
    "for",
    "human",
    "if",
    "in",
    "is",
    "of",
    "on",
    "or",
    "same",
    "the",
    "to",
    "two",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--fixture-dir", required=True)
    return parser.parse_args()


def resolve_outputs(run_dir: Path, workspace_dir: Path) -> tuple[dict[str, bool], dict[str, str]]:
    presence: dict[str, bool] = {}
    resolved_paths: dict[str, str] = {}

    for canonical_name, candidates in CANONICAL_OUTPUTS.items():
        found_path: Path | None = None
        for scope, candidate_name in candidates:
            base_dir = run_dir if scope == "root" else workspace_dir
            candidate_path = base_dir / candidate_name
            if candidate_path.exists():
                found_path = candidate_path
                break
        presence[canonical_name] = found_path is not None
        if found_path is not None:
            resolved_paths[canonical_name] = str(found_path)

    return presence, resolved_paths


def load_triage_decision(resolved_paths: dict[str, str]) -> dict | None:
    triage_path = resolved_paths.get("triage_decision.json")
    if not triage_path:
        return None
    return load_json(Path(triage_path))


def load_match_table(resolved_paths: dict[str, str]) -> dict | None:
    match_path = resolved_paths.get("candidate_match_table.json")
    if not match_path:
        return None
    return load_json(Path(match_path))


def derive_ranked_candidates(match_table: dict) -> list[str]:
    if "ranked_candidates" in match_table:
        ranked = match_table["ranked_candidates"]
        normalized = []
        for item in ranked:
            if isinstance(item, dict):
                normalized.append(item.get("record_id"))
            else:
                normalized.append(item)
        return [item for item in normalized if item]

    if "candidates" in match_table:
        candidates = match_table["candidates"]
        sorted_candidates = sorted(
            candidates,
            key=lambda item: (item.get("rank", 9999), -(item.get("total_score", 0))),
        )
        return [item.get("record_id") for item in sorted_candidates if item.get("record_id")]

    return []


def normalize_rationale_text(triage: dict | None) -> str:
    if not triage:
        return ""
    parts: list[str] = []

    for key in ["rationale", "key_rationale", "confidence_rationale"]:
        value = triage.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))

    guardrails = triage.get("guardrails_applied", [])
    if isinstance(guardrails, list):
        for item in guardrails:
            if isinstance(item, dict):
                rule = item.get("rule", "")
                outcome = item.get("outcome", "")
                parts.append(f"{rule} {outcome}".strip())
            else:
                parts.append(str(item))

    supporting = triage.get("supporting_evidence", [])
    if isinstance(supporting, list):
        for item in supporting:
            if isinstance(item, dict):
                parts.append(
                    " ".join(
                        str(piece)
                        for piece in [item.get("source", ""), item.get("summary", "")]
                        if piece
                    )
                )

    return "\n".join(part for part in parts if part).strip()


def normalize_gap_analysis(resolved_paths: dict[str, str], triage: dict | None) -> dict[str, list[str]]:
    gap_path = resolved_paths.get("gap_analysis.md")
    if gap_path:
        path = Path(gap_path)
        payload = try_load_json(path)
        if payload and "missing_fields" in payload:
            missing = payload["missing_fields"]
            return {
                "must_have": list(missing.get("must_have", [])),
                "later_required": list(missing.get("later_required", [])),
                "optional": list(missing.get("optional", [])),
            }

        sections = parse_markdown_sections(read_text(path))
        return {
            "must_have": split_section_lines(sections.get("Must-Have Gaps", "")),
            "later_required": split_section_lines(sections.get("Later-Required Gaps", "")),
            "optional": split_section_lines(sections.get("Optional Gaps", "")),
        }

    if triage and isinstance(triage.get("missing_fields"), dict):
        missing = triage["missing_fields"]
        return {
            "must_have": list(missing.get("must_have", [])),
            "later_required": list(missing.get("later_required", [])),
            "optional": list(missing.get("optional", [])),
        }

    return {"must_have": [], "later_required": [], "optional": []}


def normalize_action_plan(resolved_paths: dict[str, str]) -> dict[str, list[str]]:
    action_path = resolved_paths.get("next_actions.md")
    if not action_path:
        return {"immediate_actions": [], "review_notes": []}

    path = Path(action_path)
    payload = try_load_json(path)
    if payload and "steps" in payload:
        immediate_actions = []
        review_notes = []
        for step in payload.get("steps", []):
            action = f"{step.get('action', '')}: {step.get('detail', '')}".strip(": ")
            if step.get("priority") == "immediate":
                immediate_actions.append(action)
            else:
                review_notes.append(action)
        return {
            "immediate_actions": [item for item in immediate_actions if item],
            "review_notes": [item for item in review_notes if item],
        }

    sections = parse_markdown_sections(read_text(path))
    return {
        "immediate_actions": split_section_lines(sections.get("Immediate Actions", "")),
        "review_notes": split_section_lines(sections.get("Review Notes", "")),
    }


def infer_action_plan_from_triage(triage: dict | None, gap_analysis: dict[str, list[str]]) -> dict[str, list[str]]:
    if not triage:
        return {"immediate_actions": [], "review_notes": []}

    immediate_actions: list[str] = []
    review_notes: list[str] = []

    disposition = triage.get("disposition")
    best_match = triage.get("best_match_record_id")
    if disposition == "update" and best_match:
        immediate_actions.append(f"Link the intake to existing record {best_match} as an update.")
    elif disposition == "transfer" and best_match:
        immediate_actions.append(f"Transfer operational ownership for record {best_match}.")
    elif disposition == "new_record":
        immediate_actions.append("Create a new record because no existing record remains credible.")
    elif disposition == "duplicate_review":
        immediate_actions.append("Route to human review because multiple plausible records remain.")

    corrections = triage.get("data_corrections_required", [])
    if isinstance(corrections, list):
        for item in corrections[:3]:
            if isinstance(item, dict):
                field = item.get("field", "field")
                action = item.get("action", "review")
                review_notes.append(f"{action} {field}")

    for field in gap_analysis.get("must_have", []):
        review_notes.append(f"Collect missing must-have field: {field}")
    for field in gap_analysis.get("later_required", []):
        review_notes.append(f"Collect later-required field: {field}")

    return {
        "immediate_actions": immediate_actions,
        "review_notes": review_notes,
    }


def split_section_lines(text: str) -> list[str]:
    items = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        stripped = stripped.removeprefix("-").strip()
        items.append(stripped)
    return items


def score_matching_accuracy(semantic_checks: dict[str, bool]) -> float:
    passed = sum(1 for value in semantic_checks.values() if value)
    if passed == 3:
        return 5.0
    if passed == 2:
        return 3.5
    if passed == 1:
        return 1.5
    return 0.0


def score_policy_application(
    rationale_text: str,
    triage: dict | None,
    gold: dict,
) -> float:
    required_phrases = [phrase.lower() for phrase in gold.get("rationale_must_include", [])]
    rationale_lower = rationale_text.lower()
    matched = sum(1 for phrase in required_phrases if phrase_matches(phrase, rationale_lower))
    coverage = matched / len(required_phrases) if required_phrases else 1.0

    contradictory = triage.get("contradictory_signals") if triage else None
    contradiction_explicit = False
    if isinstance(contradictory, list) and contradictory:
        contradiction_explicit = True
    elif any(word in rationale_lower for word in ["stale", "reused", "ambiguous", "conflict", "two plausible", "not final"]):
        contradiction_explicit = True

    if coverage >= 0.85 and contradiction_explicit:
        return 5.0
    if coverage >= 0.6:
        return 3.5
    if coverage >= 0.3:
        return 2.0
    return 0.5


def score_explanation_quality(rationale_text: str, gold: dict) -> float:
    rationale_lower = rationale_text.lower()
    required_phrases = [phrase.lower() for phrase in gold.get("rationale_must_include", [])]
    matched = sum(1 for phrase in required_phrases if phrase_matches(phrase, rationale_lower))
    coverage = matched / len(required_phrases) if required_phrases else 1.0
    line_count = len([line for line in rationale_text.splitlines() if line.strip()])

    if coverage >= 0.85 and line_count >= 3:
        return 5.0
    if coverage >= 0.6 and line_count >= 2:
        return 4.0
    if coverage >= 0.4:
        return 2.5
    if rationale_text.strip():
        return 1.5
    return 0.0


def score_gap_prioritization(observed: dict[str, list[str]], expected: dict[str, list[str]]) -> float:
    must_observed = set(observed.get("must_have", []))
    must_expected = set(expected.get("must_have", []))
    later_observed = set(observed.get("later_required", []))
    later_expected = set(expected.get("later_required", []))
    optional_observed = set(observed.get("optional", []))
    optional_expected = set(expected.get("optional", []))

    if must_observed == must_expected and later_observed == later_expected:
        if optional_observed == optional_expected or optional_expected.issubset(optional_observed):
            return 5.0
        return 4.0

    exact = 0
    partial = 0
    for observed_set, expected_set in [
        (must_observed, must_expected),
        (later_observed, later_expected),
        (optional_observed, optional_expected),
    ]:
        if observed_set == expected_set:
            exact += 1
        elif observed_set & expected_set or (not observed_set and not expected_set):
            partial += 1

    if exact == 3:
        return 5.0
    if exact == 2 and partial >= 1:
        return 4.0
    if exact == 1 or partial >= 2:
        return 2.5
    return 0.5


def score_actionability(action_plan: dict[str, list[str]], expected_disposition: str) -> float:
    immediate_count = len(action_plan.get("immediate_actions", []))
    review_count = len(action_plan.get("review_notes", []))
    combined_text = "\n".join(action_plan.get("immediate_actions", []) + action_plan.get("review_notes", [])).lower()

    if expected_disposition == "duplicate_review" and "review" not in combined_text and "human" not in combined_text:
        return 2.0 if immediate_count else 0.0

    if immediate_count >= 2 and review_count >= 1:
        return 5.0
    if immediate_count >= 2:
        return 4.0
    if immediate_count >= 1:
        return 2.5
    return 0.0


def score_confidence_calibration(actual_confidence: str | None, expected_confidence: str | None) -> float:
    if not actual_confidence or not expected_confidence:
        return 0.0
    if actual_confidence == expected_confidence:
        return 5.0

    ladder = ["low", "medium", "high"]
    if actual_confidence in ladder and expected_confidence in ladder:
        if abs(ladder.index(actual_confidence) - ladder.index(expected_confidence)) == 1:
            return 3.0
    return 1.0


def phrase_matches(phrase: str, rationale_text: str) -> bool:
    if phrase in rationale_text:
        return True

    phrase_tokens = meaningful_tokens(phrase)
    rationale_tokens = meaningful_tokens(rationale_text)
    if not phrase_tokens:
        return False

    overlap = len(set(phrase_tokens) & set(rationale_tokens))
    required_overlap = max(2, len(set(phrase_tokens)) - 1)
    required_overlap = min(required_overlap, len(set(phrase_tokens)))
    return overlap >= required_overlap


def meaningful_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9_]+", text.lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def map_task_scores_to_scorecard(
    criterion_scores: dict[str, float],
    execution_success: bool,
    contract_pass: bool,
) -> dict[str, float]:
    observability = 5.0 if execution_success and contract_pass else 2.0 if execution_success else 0.0
    return {
        "output_quality_and_task_success": round(
            (
                criterion_scores["matching_accuracy"]
                + criterion_scores["policy_application"]
                + criterion_scores["explanation_quality"]
                + criterion_scores["gap_prioritization"]
            )
            / 4,
            3,
        ),
        "reliability_and_repeatability": criterion_scores["confidence_calibration"],
        "human_review_quality": round(
            (criterion_scores["explanation_quality"] + criterion_scores["actionability"]) / 2,
            3,
        ),
        "tooling_tracing_and_observability": observability,
        "runtime_speed": 0.0,
        "cost_efficiency": 0.0,
    }


def evaluate_run(run_dir: Path, fixture_dir: Path) -> dict:
    workspace_dir = run_dir / "workspace"
    gold = load_json(fixture_dir / "gold-expected.json")
    run_result_payload = try_load_json(run_dir / "run_result.json") or {}
    normalized_outputs, resolved_paths = resolve_outputs(run_dir, workspace_dir)
    exact_outputs = {name: (run_dir / name).exists() for name in CANONICAL_OUTPUTS}

    execution_success = False
    trace_path = run_dir / "agent-trace.jsonl"
    if trace_path.exists():
        trace_text = trace_path.read_text(encoding="utf-8")
        execution_success = (
            '"subtype": "success"' in trace_text
            or '"type": "final_output"' in trace_text
        )

    triage = load_triage_decision(resolved_paths)
    match_table = load_match_table(resolved_paths)
    ranked_candidates = derive_ranked_candidates(match_table or {})
    rationale_text = normalize_rationale_text(triage)
    gap_analysis = normalize_gap_analysis(resolved_paths, triage)
    action_plan = normalize_action_plan(resolved_paths)
    inferred_action_plan_used = False
    if not action_plan.get("immediate_actions") and not action_plan.get("review_notes"):
        action_plan = infer_action_plan_from_triage(triage, gap_analysis)
        inferred_action_plan_used = bool(
            action_plan.get("immediate_actions") or action_plan.get("review_notes")
        )

    semantic_checks = {
        "disposition_matches": bool(triage) and triage.get("disposition") == gold.get("expected_disposition"),
        "best_match_matches": bool(triage)
        and triage.get("best_match_record_id") == gold.get("expected_best_match_record_id"),
        "top_candidate_matches": bool(ranked_candidates)
        and ranked_candidates[0] == gold.get("expected_top_ranked_candidates", [None])[0],
    }

    hard_gate_failures = []
    critical_outputs = [
        "triage_decision.json",
        "candidate_match_table.json",
    ]
    for output_name in critical_outputs:
        if not normalized_outputs.get(output_name, False):
            hard_gate_failures.append(f"missing critical artifact after normalization: {output_name}")
    if not execution_success:
        hard_gate_failures.append("execution did not end in success")

    soft_contract_failures = []
    for output_name in ["gap_analysis.md", "next_actions.md"]:
        if not normalized_outputs.get(output_name, False):
            soft_contract_failures.append(f"missing supplemental artifact after normalization: {output_name}")

    expected_missing_fields = gold.get("expected_missing_fields", {})
    criterion_scores = {
        "matching_accuracy": score_matching_accuracy(semantic_checks),
        "policy_application": score_policy_application(rationale_text, triage, gold),
        "explanation_quality": score_explanation_quality(rationale_text, gold),
        "gap_prioritization": score_gap_prioritization(gap_analysis, expected_missing_fields),
        "actionability": score_actionability(action_plan, gold.get("expected_disposition", "")),
        "confidence_calibration": score_confidence_calibration(
            (triage or {}).get("confidence"),
            gold.get("expected_confidence"),
        ),
    }

    quality_failures = []
    if not semantic_checks["disposition_matches"]:
        quality_failures.append("disposition does not match gold expectation")
    if not semantic_checks["best_match_matches"]:
        quality_failures.append("best match does not match gold expectation")
    if not semantic_checks["top_candidate_matches"]:
        quality_failures.append("top-ranked candidate does not match gold expectation")

    contract_pass = not hard_gate_failures
    weighted_score = weighted_average(criterion_scores, TASK_WEIGHTS)
    if hard_gate_failures:
        final_score = 0.0
        outcome = "fail"
    elif quality_failures:
        final_score = round(min(weighted_score, 3.5), 3)
        outcome = "partial"
    else:
        final_score = round(weighted_score, 3)
        outcome = "pass"

    scorecard_breakdown = map_task_scores_to_scorecard(
        criterion_scores,
        execution_success=execution_success,
        contract_pass=contract_pass,
    )

    summary = {
        "framework": run_result_payload.get("framework", "unknown-framework"),
        "task_id": "intake_triage",
        "run_dir": str(run_dir),
        "fixture_dir": str(fixture_dir),
        "duration": run_result_payload.get("duration"),
        "cost": run_result_payload.get("cost"),
        "execution_success": execution_success,
        "contract_pass": contract_pass,
        "exact_output_presence": exact_outputs,
        "normalized_output_presence": normalized_outputs,
        "resolved_output_paths": resolved_paths,
        "semantic_checks": semantic_checks,
        "criterion_scores": criterion_scores,
        "scorecard_breakdown": scorecard_breakdown,
        "hard_gate_failures": hard_gate_failures,
        "soft_contract_failures": soft_contract_failures,
        "quality_failures": quality_failures,
        "final_score": final_score,
        "outcome": outcome,
        "notes": [
            "Deterministic evaluator normalizes equivalent artifact names and formats before checking hard gates.",
            "Only core decision artifacts are hard-gated; missing supplemental artifacts reduce quality scores but do not automatically fail the run.",
            "Supplemental action plans may be inferred from structured correction data when the explicit file is missing.",
            f"Inferred action plan used: {inferred_action_plan_used}.",
            "Gemini 3.1 Pro Preview is the locked judge target for later qualitative evaluation assistance.",
        ],
    }
    return summary


def update_run_result(run_dir: Path, summary: dict) -> None:
    run_result_path = run_dir / "run_result.json"
    if run_result_path.exists():
        payload = load_json(run_result_path)
    else:
        payload = {
            "framework": summary["framework"],
            "task_id": summary["task_id"],
            "task_type": "intake_decisioning",
            "run_id": run_dir.name,
        }

    payload["outcome"] = summary["outcome"]
    payload["final_score"] = summary["final_score"]
    payload["score_breakdown"] = summary["scorecard_breakdown"]
    payload["criterion_scores"] = summary["criterion_scores"]
    payload.setdefault("notes", {})
    payload["notes"]["status"] = "Task evaluation completed."
    payload["notes"]["task_evaluation_path"] = str(run_dir / "evaluation_summary.json")
    payload["notes"]["contract_pass"] = summary["contract_pass"]
    payload["notes"]["soft_contract_failures"] = summary.get("soft_contract_failures", [])
    run_result_path.write_text(f"{json.dumps(payload, indent=2)}\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    fixture_dir = Path(args.fixture_dir).resolve()
    summary = evaluate_run(run_dir, fixture_dir)

    output_path = run_dir / "evaluation_summary.json"
    output_path.write_text(f"{json.dumps(summary, indent=2)}\n", encoding="utf-8")
    update_run_result(run_dir, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
