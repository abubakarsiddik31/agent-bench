import argparse
import json
from pathlib import Path


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--fixture-dir", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def main() -> None:
    args = parse_args()
    run_dir = Path(args.run_dir).resolve()
    fixture_dir = Path(args.fixture_dir).resolve()
    workspace_dir = run_dir / "workspace"
    gold = load_json(fixture_dir / "gold-expected.json")
    normalized_outputs, resolved_paths = resolve_outputs(run_dir, workspace_dir)

    exact_outputs = {name: (run_dir / name).exists() for name in CANONICAL_OUTPUTS}

    execution_success = False
    trace_path = run_dir / "agent-trace.jsonl"
    if trace_path.exists():
        trace_text = trace_path.read_text(encoding="utf-8")
        execution_success = '"subtype": "success"' in trace_text

    semantic_checks = {
        "disposition_matches": False,
        "best_match_matches": False,
        "top_candidate_matches": False,
    }

    triage = load_triage_decision(resolved_paths)
    if triage:
        semantic_checks["disposition_matches"] = (
            triage.get("disposition") == gold.get("expected_disposition")
        )
        semantic_checks["best_match_matches"] = (
            triage.get("best_match_record_id") == gold.get("expected_best_match_record_id")
        )

    match_table = load_match_table(resolved_paths)
    if match_table:
        ranked_candidates = derive_ranked_candidates(match_table)
        if ranked_candidates:
            first = ranked_candidates[0]
            semantic_checks["top_candidate_matches"] = (
                first == gold.get("expected_top_ranked_candidates", [None])[0]
            )

    hard_gate_failures = []
    for output_name, present in normalized_outputs.items():
        if not present:
            hard_gate_failures.append(f"missing required artifact after normalization: {output_name}")
    if not execution_success:
        hard_gate_failures.append("execution did not end in success")

    quality_failures = []
    if not semantic_checks["disposition_matches"]:
        quality_failures.append("disposition does not match gold expectation")
    if not semantic_checks["best_match_matches"]:
        quality_failures.append("best match does not match gold expectation")
    if not semantic_checks["top_candidate_matches"]:
        quality_failures.append("top-ranked candidate does not match gold expectation")

    contract_pass = not hard_gate_failures
    if hard_gate_failures:
        final_score = 0.0
        outcome = "fail"
    elif quality_failures:
        final_score = 2.5
        outcome = "partial"
    else:
        final_score = 5.0
        outcome = "pass"

    summary = {
        "framework": "anthropic-agent-sdk",
        "task_id": "intake_triage",
        "run_dir": str(run_dir),
        "fixture_dir": str(fixture_dir),
        "execution_success": execution_success,
        "contract_pass": contract_pass,
        "exact_output_presence": exact_outputs,
        "normalized_output_presence": normalized_outputs,
        "resolved_output_paths": resolved_paths,
        "semantic_checks": semantic_checks,
        "hard_gate_failures": hard_gate_failures,
        "quality_failures": quality_failures,
        "final_score": final_score,
        "outcome": outcome,
        "notes": [
            "Deterministic evaluator normalizes equivalent artifact names and formats before checking hard gates.",
            "Gemini 3.1 Pro Preview is the locked judge target for later qualitative evaluation assistance.",
        ],
    }

    output_path = run_dir / "evaluation_summary.json"
    output_path.write_text(f"{json.dumps(summary, indent=2)}\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
