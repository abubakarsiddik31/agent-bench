"""Render the public scoreboard tables in README.md from saved run artifacts.

The scoreboard is a derived view, never a hand-edited one. This script reads
``evaluation/scoreboard.yml`` for the canonical run list, pulls the numbers out
of each run's saved artifacts, renders Markdown, and splices the result between
sentinel comments in ``README.md``.

Usage:
    python scripts/build_scoreboard.py            # print tables to stdout
    python scripts/build_scoreboard.py --check    # fail if README is stale
    python scripts/build_scoreboard.py --write     # update README.md in place

Run artifacts are gitignored, so ``--check`` is only meaningful on a machine
that has the ``results/`` tree present (i.e. after running the benchmark).
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = REPO_ROOT / "evaluation" / "scoreboard.yml"
README_PATH = REPO_ROOT / "README.md"

SCOREBOARD_START = "<!-- SCOREBOARD:START -->"
SCOREBOARD_END = "<!-- SCOREBOARD:END -->"
TOOL_METRICS_START = "<!-- TOOL-METRICS:START -->"
TOOL_METRICS_END = "<!-- TOOL-METRICS:END -->"

RANKING_COLUMNS = [
    "Rank",
    "Framework",
    "Runtime Model",
    "Provider-Agnostic?",
    "Framework LOC",
    "Task Score",
    "Framework Score",
    "Final Score",
    "Duration",
    "Outcome",
]

TOOL_METRIC_COLUMNS = [
    "Framework",
    "Run",
    "Tool Pass",
    "Total Calls",
    "Passed Calls",
    "Failed Calls",
    "Unique Tools",
    "Write Calls",
    "Artifacts Produced",
    "Success Rate",
    "Write Completion",
    "Output Coverage",
    "Custom Tool Efficiency",
]

RANKING_ALIGNMENT = [
    ":---:",
    "---",
    "---",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
]

TOOL_METRIC_ALIGNMENT = [
    "---",
    "---",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
    ":---:",
]

OUTCOME_LABELS = {"pass": "Pass", "partial": "Partial", "fail": "Fail"}


class ScoreboardError(RuntimeError):
    """Raised when a run referenced by the manifest is missing or malformed."""


@dataclass
class ScoreboardRow:
    display_name: str
    framework: str
    model: str
    run_label: str
    provider_agnostic: bool
    lines_of_code: int
    task_score: float
    framework_score: float
    combined_score: float
    duration_seconds: float | None
    outcome: str
    tool_metrics: dict


def load_json(path: Path) -> dict:
    if not path.exists():
        raise ScoreboardError(f"missing artifact: {path}")
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _score(value: object) -> float:
    return round(float(value or 0), 3)


def build_rows(manifest: dict) -> list[ScoreboardRow]:
    rows: list[ScoreboardRow] = []
    for entry in manifest.get("entries", []):
        run_dir = REPO_ROOT / entry["run"]
        run_path = Path(entry["run"])
        run_label = "/".join(run_path.parts[-2:])

        benchmark = load_json(run_dir / "benchmark_summary.json")
        task = load_json(run_dir / "evaluation_summary.json")
        framework = load_json(run_dir / "framework_evaluation.json")
        metrics = framework.get("tool_call_metrics", {})

        duration = (benchmark.get("duration") or {}).get("value")

        rows.append(
            ScoreboardRow(
                display_name=entry["display_name"],
                framework=entry["framework"],
                model=entry["model"],
                run_label=run_label,
                provider_agnostic=bool(entry["provider_agnostic"]),
                lines_of_code=int(
                    framework.get("implementation_metrics", {}).get("lines_of_code", 0)
                ),
                task_score=_score(task.get("final_score")),
                framework_score=_score(benchmark.get("framework_quality_score")),
                combined_score=_score(benchmark.get("combined_score")),
                duration_seconds=float(duration) if isinstance(duration, (int, float)) else None,
                outcome=str(benchmark.get("outcome", "unknown")).lower(),
                tool_metrics=metrics,
            )
        )

    rows.sort(key=lambda row: row.combined_score, reverse=True)
    return rows


def render_ranking_table(rows: list[ScoreboardRow]) -> str:
    """Render the main ranking table. Ties share a rank number."""
    lines = [
        "| " + " | ".join(RANKING_COLUMNS) + " |",
        "| " + " | ".join(RANKING_ALIGNMENT) + " |",
    ]

    previous_score: float | None = None
    rank = 0
    for index, row in enumerate(rows, start=1):
        if row.combined_score != previous_score:
            rank = index
            previous_score = row.combined_score

        label = f"[{row.display_name}](./frameworks/{row.framework})"
        duration = f"`{row.duration_seconds:.3f}s`" if row.duration_seconds is not None else "`n/a`"

        lines.append(
            "| "
            + " | ".join(
                [
                    str(rank),
                    label,
                    f"`{row.model}`",
                    "`Yes`" if row.provider_agnostic else "`No`",
                    f"`{row.lines_of_code}`",
                    f"`{row.task_score} / 5.0`",
                    f"`{row.framework_score} / 5.0`",
                    f"**`{row.combined_score} / 5.0`**",
                    duration,
                    f"`{OUTCOME_LABELS.get(row.outcome, row.outcome.title())}`",
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def render_tool_metrics_table(rows: list[ScoreboardRow]) -> str:
    lines = [
        "| " + " | ".join(TOOL_METRIC_COLUMNS) + " |",
        "| " + " | ".join(TOOL_METRIC_ALIGNMENT) + " |",
    ]

    for row in rows:
        m = row.tool_metrics
        expected = m.get("required_artifacts_expected", 0)
        produced = m.get("required_artifacts_produced", 0)
        lines.append(
            "| "
            + " | ".join(
                [
                    row.display_name,
                    f"`{row.run_label}`",
                    "`Pass`" if m.get("tool_call_passed") else "`Fail`",
                    f"`{m.get('total_tool_calls', 0)}`",
                    f"`{m.get('passed_tool_calls_detected', 0)}`",
                    f"`{m.get('failed_tool_calls_detected', 0)}`",
                    f"`{len(m.get('unique_tools_used', []))}`",
                    f"`{m.get('write_calls', 0)}`",
                    f"`{produced} / {expected}`",
                    f"`{m.get('tool_call_success_rate', 0)}`",
                    f"`{m.get('write_completion_rate', 0)}`",
                    f"`{m.get('output_coverage_rate', 0)}`",
                    f"`{m.get('custom_tool_efficiency', 0)}`",
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def splice(readme: str, start: str, end: str, body: str) -> str:
    if start not in readme or end not in readme:
        raise ScoreboardError(f"README is missing sentinel comments {start} / {end}")

    prefix, remainder = readme.split(start, 1)
    _, suffix = remainder.split(end, 1)
    return f"{prefix}{start}\n{body}\n{end}{suffix}"


def build_readme(readme: str, rows: list[ScoreboardRow]) -> str:
    updated = splice(readme, SCOREBOARD_START, SCOREBOARD_END, render_ranking_table(rows))
    updated = splice(
        updated,
        TOOL_METRICS_START,
        TOOL_METRICS_END,
        render_tool_metrics_table(rows),
    )
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true", help="rewrite README.md in place")
    group.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if README.md does not match the generated tables",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    manifest = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    rows = build_rows(manifest)
    readme = README_PATH.read_text(encoding="utf-8")
    rendered = build_readme(readme, rows)

    if args.check:
        if rendered != readme:
            print("README scoreboard is out of date; run: uv run python scripts/build_scoreboard.py --write")
            return 1
        print(f"README scoreboard is up to date ({len(rows)} rows).")
        return 0

    if args.write:
        README_PATH.write_text(rendered, encoding="utf-8")
        print(f"Updated {README_PATH.relative_to(REPO_ROOT)} with {len(rows)} rows.")
        return 0

    print(render_ranking_table(rows))
    print()
    print(render_tool_metrics_table(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
