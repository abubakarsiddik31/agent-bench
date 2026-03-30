import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.evaluate_framework import evaluate_framework  # noqa: E402
from evaluation.evaluate_intake_run import evaluate_run, update_run_result  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-script", required=True)
    parser.add_argument("--fixture", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--framework-dir")
    parser.add_argument("--skip-agent", action="store_true")
    parser.add_argument("--skip-judge", action="store_true")
    return parser.parse_args()


def run_agent(agent_script: Path, fixture_dir: Path, out_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(agent_script),
            "--fixture",
            str(fixture_dir),
            "--out",
            str(out_dir),
        ],
        check=True,
        cwd=str(REPO_ROOT),
    )


def combine_scores(task_summary: dict, framework_summary: dict) -> dict:
    task_score = float(task_summary.get("final_score", 0))
    framework_score = float(framework_summary.get("final_score", 0))
    combined_score = round((task_score * 0.5) + (framework_score * 0.5), 3)

    if task_summary.get("outcome") == "fail":
        outcome = "fail"
    elif task_summary.get("outcome") == "partial":
        outcome = "partial"
    else:
        outcome = "pass"

    return {
        "framework": framework_summary.get("framework"),
        "task_id": task_summary.get("task_id"),
        "run_dir": task_summary.get("run_dir"),
        "cost": task_summary.get("cost"),
        "duration": task_summary.get("duration"),
        "task_score": task_score,
        "framework_quality_score": framework_score,
        "combined_score": combined_score,
        "outcome": outcome,
        "weights": {
            "task_performance_score": 50,
            "framework_quality_score": 50,
        },
        "task_evaluation_path": str(Path(task_summary["run_dir"]) / "evaluation_summary.json"),
        "framework_evaluation_path": str(Path(task_summary["run_dir"]) / "framework_evaluation.json"),
    }


def main() -> None:
    args = parse_args()
    agent_script = Path(args.agent_script).resolve()
    fixture_dir = Path(args.fixture).resolve()
    out_dir = Path(args.out).resolve()
    framework_dir = Path(args.framework_dir).resolve() if args.framework_dir else agent_script.parent

    if not args.skip_agent:
        run_agent(agent_script=agent_script, fixture_dir=fixture_dir, out_dir=out_dir)

    task_summary = evaluate_run(run_dir=out_dir, fixture_dir=fixture_dir)
    (out_dir / "evaluation_summary.json").write_text(
        f"{json.dumps(task_summary, indent=2)}\n",
        encoding="utf-8",
    )
    update_run_result(out_dir, task_summary)

    framework_summary = evaluate_framework(
        run_dir=out_dir,
        fixture_dir=fixture_dir,
        framework_dir=framework_dir,
        skip_judge=args.skip_judge,
    )
    benchmark_summary = combine_scores(task_summary, framework_summary)

    benchmark_summary_path = out_dir / "benchmark_summary.json"
    benchmark_summary_path.write_text(
        f"{json.dumps(benchmark_summary, indent=2)}\n",
        encoding="utf-8",
    )

    run_result_path = out_dir / "run_result.json"
    if run_result_path.exists():
        run_result = json.loads(run_result_path.read_text(encoding="utf-8"))
        run_result["framework_quality_score"] = framework_summary["final_score"]
        run_result["combined_score"] = benchmark_summary["combined_score"]
        run_result.setdefault("notes", {})
        run_result["notes"]["framework_evaluation_path"] = str(out_dir / "framework_evaluation.json")
        run_result["notes"]["benchmark_summary_path"] = str(benchmark_summary_path)
        run_result_path.write_text(f"{json.dumps(run_result, indent=2)}\n", encoding="utf-8")

    print(json.dumps(benchmark_summary, indent=2))


if __name__ == "__main__":
    main()
