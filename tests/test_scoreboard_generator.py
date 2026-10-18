"""Tests for the README scoreboard generator.

These tests are hermetic: they do not read the ``results/`` tree, which is
gitignored and absent on a fresh clone.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

import scripts.build_scoreboard as scoreboard


def make_row(**overrides: object) -> scoreboard.ScoreboardRow:
    defaults: dict[str, object] = {
        "display_name": "Example",
        "framework": "example",
        "model": "gpt-5.4",
        "run_label": "stress_v1/run-001",
        "provider_agnostic": True,
        "lines_of_code": 150,
        "task_score": 4.0,
        "framework_score": 4.0,
        "combined_score": 4.0,
        "duration_seconds": 10.0,
        "outcome": "pass",
        "tool_metrics": {
            "tool_call_passed": True,
            "total_tool_calls": 10,
            "passed_tool_calls_detected": 10,
            "failed_tool_calls_detected": 0,
            "unique_tools_used": ["a", "b"],
            "write_calls": 4,
            "required_artifacts_produced": 4,
            "required_artifacts_expected": 4,
            "tool_call_success_rate": 1.0,
            "write_completion_rate": 1.0,
            "output_coverage_rate": 1.0,
            "custom_tool_efficiency": 1.0,
        },
    }
    defaults.update(overrides)
    return scoreboard.ScoreboardRow(**defaults)  # type: ignore[arg-type]


class RenderRankingTests(unittest.TestCase):
    def test_header_columns_match_constants(self) -> None:
        rendered = scoreboard.render_ranking_table([make_row()])
        lines = rendered.splitlines()
        self.assertEqual(lines[0].strip("| ").split(" | "), scoreboard.RANKING_COLUMNS)
        self.assertEqual(lines[1].strip("| ").split(" | "), scoreboard.RANKING_ALIGNMENT)

    def test_ties_share_a_rank_and_skip_numbers(self) -> None:
        rows = [
            make_row(display_name="A", combined_score=4.5),
            make_row(display_name="B", combined_score=4.5),
            make_row(display_name="C", combined_score=3.0),
        ]
        rendered = scoreboard.render_ranking_table(rows)
        ranks = [line.split("|")[1].strip() for line in rendered.splitlines()[2:]]
        self.assertEqual(ranks, ["1", "1", "3"])

    def test_ranking_links_to_the_framework_directory(self) -> None:
        rendered = scoreboard.render_ranking_table([make_row(framework="crewai")])
        self.assertIn("[Example](./frameworks/crewai)", rendered)

    def test_missing_duration_renders_placeholder(self) -> None:
        rendered = scoreboard.render_ranking_table([make_row(duration_seconds=None)])
        self.assertIn("`n/a`", rendered)

    def test_provider_agnostic_flag_is_rendered(self) -> None:
        rendered = scoreboard.render_ranking_table(
            [make_row(provider_agnostic=False), make_row(display_name="B", provider_agnostic=True)]
        )
        self.assertIn("`No`", rendered)
        self.assertIn("`Yes`", rendered)


class RenderToolMetricsTests(unittest.TestCase):
    def test_header_columns_match_constants(self) -> None:
        rendered = scoreboard.render_tool_metrics_table([make_row()])
        lines = rendered.splitlines()
        self.assertEqual(lines[0].strip("| ").split(" | "), scoreboard.TOOL_METRIC_COLUMNS)
        self.assertEqual(lines[1].strip("| ").split(" | "), scoreboard.TOOL_METRIC_ALIGNMENT)

    def test_run_label_and_artifact_counts_are_rendered(self) -> None:
        rendered = scoreboard.render_tool_metrics_table([make_row()])
        self.assertIn("`stress_v1/run-001`", rendered)
        self.assertIn("`4 / 4`", rendered)


class SpliceTests(unittest.TestCase):
    def test_splice_replaces_only_the_sentinel_region(self) -> None:
        readme = "before\n<!-- A -->\nold\n<!-- B -->\nafter\n"
        self.assertEqual(
            scoreboard.splice(readme, "<!-- A -->", "<!-- B -->", "new"),
            "before\n<!-- A -->\nnew\n<!-- B -->\nafter\n",
        )

    def test_splice_raises_when_sentinels_are_missing(self) -> None:
        with self.assertRaises(scoreboard.ScoreboardError):
            scoreboard.splice("no markers here", "<!-- A -->", "<!-- B -->", "new")


class BuildRowsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

        self._original_root = scoreboard.REPO_ROOT
        scoreboard.REPO_ROOT = self.root
        self.addCleanup(self._restore_root)

    def _restore_root(self) -> None:
        scoreboard.REPO_ROOT = self._original_root

    def _make_run(self, framework: str, run: str, combined: float, outcome: str = "pass") -> str:
        run_dir = self.root / "results" / framework / "intake-triage" / "stress_v1" / run
        run_dir.mkdir(parents=True)

        (run_dir / "benchmark_summary.json").write_text(
            json.dumps(
                {
                    "outcome": outcome,
                    "duration": {"value": 12.5},
                    "task_score": combined,
                    "framework_quality_score": combined,
                    "combined_score": combined,
                }
            ),
            encoding="utf-8",
        )
        (run_dir / "evaluation_summary.json").write_text(
            json.dumps({"final_score": combined}), encoding="utf-8"
        )
        (run_dir / "framework_evaluation.json").write_text(
            json.dumps(
                {
                    "implementation_metrics": {"lines_of_code": 123},
                    "tool_call_metrics": {"total_tool_calls": 7},
                }
            ),
            encoding="utf-8",
        )
        return f"results/{framework}/intake-triage/stress_v1/{run}"

    def test_rows_are_sorted_by_combined_score_descending(self) -> None:
        manifest = {
            "entries": [
                {
                    "framework": "low",
                    "display_name": "Low",
                    "model": "gpt-5.4",
                    "provider_agnostic": True,
                    "run": self._make_run("low", "run-001", 2.0),
                },
                {
                    "framework": "high",
                    "display_name": "High",
                    "model": "gpt-5.4",
                    "provider_agnostic": True,
                    "run": self._make_run("high", "run-001", 4.9),
                },
            ]
        }
        rows = scoreboard.build_rows(manifest)
        self.assertEqual([row.framework for row in rows], ["high", "low"])
        self.assertEqual(rows[0].run_label, "stress_v1/run-001")
        self.assertEqual(rows[0].lines_of_code, 123)

    def test_missing_artifact_raises_instead_of_rendering_partial_data(self) -> None:
        run = self._make_run("ghost", "run-001", 3.0)
        (self.root / run / "evaluation_summary.json").unlink()
        manifest = {
            "entries": [
                {
                    "framework": "ghost",
                    "display_name": "Ghost",
                    "model": "gpt-5.4",
                    "provider_agnostic": True,
                    "run": run,
                }
            ]
        }
        with self.assertRaises(scoreboard.ScoreboardError):
            scoreboard.build_rows(manifest)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_valid_yaml_with_required_fields(self) -> None:
        manifest = yaml.safe_load(scoreboard.MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["task_id"], "intake_triage")
        self.assertEqual(manifest["dataset_split"], "stress_v1")
        self.assertTrue(manifest["entries"], "scoreboard manifest has no entries")

        required = {"framework", "display_name", "model", "provider_agnostic", "run"}
        seen_runs = set()
        for entry in manifest["entries"]:
            with self.subTest(framework=entry.get("framework")):
                self.assertTrue(required.issubset(entry), f"entry missing keys: {required - set(entry)}")
                self.assertTrue(entry["run"].startswith("results/"))
                self.assertNotIn(entry["run"], seen_runs, "duplicate run referenced twice")
                seen_runs.add(entry["run"])


if __name__ == "__main__":
    unittest.main()
