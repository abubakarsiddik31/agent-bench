"""Regression tests for the shared benchmark workspace helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from common import benchmark_utils
from tests import REPO_ROOT

CASE_101 = REPO_ROOT / "benchmarks" / "intake-triage" / "stress_v1" / "fixtures" / "case-101"


class PrepareWorkspaceTests(unittest.TestCase):
    """The fixture workspace must never contain the answer key."""

    def test_gold_expected_is_excluded_from_workspace(self) -> None:
        self.assertIn("gold-expected.json", benchmark_utils.EXCLUDED_FIXTURE_FILES)
        self.assertTrue(
            (CASE_101 / "gold-expected.json").exists(),
            "fixture is missing gold-expected.json; the test would be vacuous",
        )

        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            benchmark_utils.prepare_workspace(REPO_ROOT, CASE_101, workspace)

            self.assertFalse(
                (workspace / "gold-expected.json").exists(),
                "gold-expected.json leaked into the agent workspace",
            )
            self.assertTrue((workspace / "intake-packet.json").exists())
            self.assertTrue((workspace / "shared" / "matching-policy.json").exists())

    def test_stale_gold_expected_is_removed_from_existing_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir(parents=True)
            stale = workspace / "gold-expected.json"
            stale.write_text('{"leaked": true}', encoding="utf-8")

            benchmark_utils.prepare_workspace(REPO_ROOT, CASE_101, workspace)

            self.assertFalse(stale.exists())


class SafePathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name) / "workspace"
        self.workspace.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def test_allows_paths_inside_workspace(self) -> None:
        nested = benchmark_utils.safe_path(self.workspace, "out/nested/file.txt")
        self.assertEqual(nested, (self.workspace / "out" / "nested" / "file.txt").resolve())

    def test_rejects_parent_traversal(self) -> None:
        with self.assertRaises(ValueError):
            benchmark_utils.safe_path(self.workspace, "../escape.txt")

    def test_rejects_absolute_path_outside_workspace(self) -> None:
        with self.assertRaises(ValueError):
            benchmark_utils.safe_path(self.workspace, "/etc/passwd")


class WorkspaceToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name) / "workspace"
        self.workspace.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def test_write_read_list_roundtrip(self) -> None:
        message = benchmark_utils.write_file_in_workspace(self.workspace, "a/b.txt", "hello agent")
        self.assertIn("a/b.txt", message)
        self.assertEqual(benchmark_utils.read_file_in_workspace(self.workspace, "a/b.txt"), "hello agent")
        self.assertIn("a/b.txt", benchmark_utils.list_files_in_workspace(self.workspace))

    def test_search_finds_matches_and_reports_absence(self) -> None:
        benchmark_utils.write_file_in_workspace(self.workspace, "notes.md", "Stale licensure signal")
        self.assertIn("Stale licensure", benchmark_utils.search_text_in_workspace(self.workspace, "licensure"))
        self.assertEqual(
            benchmark_utils.search_text_in_workspace(self.workspace, "unicorn"),
            "No matches found.",
        )

    def test_tool_calls_are_appended_to_trace(self) -> None:
        trace: list[str] = []
        benchmark_utils.write_file_in_workspace(self.workspace, "x.txt", "body", trace)
        benchmark_utils.read_file_in_workspace(self.workspace, "x.txt", trace)

        names = [json.loads(line)["content"][0]["value"] for line in trace]
        self.assertEqual(names, ["write_workspace_file", "read_workspace_file"])

    def test_missing_required_outputs_lists_absent_files(self) -> None:
        benchmark_utils.write_file_in_workspace(self.workspace, "triage_decision.json", "{}")
        missing = benchmark_utils.missing_required_outputs(self.workspace)
        self.assertNotIn("triage_decision.json", missing)
        self.assertEqual(len(missing), len(benchmark_utils.REQUIRED_OUTPUTS) - 1)


class PromptPackTests(unittest.TestCase):
    def test_prompt_pack_is_resolvable_and_parses(self) -> None:
        prompt_pack_path = benchmark_utils.infer_prompt_pack_path(CASE_101)
        self.assertTrue(prompt_pack_path.exists(), prompt_pack_path)

        prompt_pack = benchmark_utils.read_prompt_pack(prompt_pack_path)
        self.assertEqual(prompt_pack["task_id"], "intake_triage")
        self.assertEqual(prompt_pack["dataset_split"], "stress_v1")
        for key in ("objective", "system_prompt", "user_prompt_template"):
            self.assertTrue(prompt_pack[key].strip(), f"prompt pack field '{key}' is empty")

    def test_build_prompt_mentions_shared_and_outputs(self) -> None:
        prompt = benchmark_utils.build_prompt(
            {"objective": "OBJ", "user_prompt_template": "TEMPLATE"}
        )
        self.assertIn("OBJ", prompt)
        self.assertIn("TEMPLATE", prompt)
        self.assertIn("./shared", prompt)


class ArgumentParsingTests(unittest.TestCase):
    def test_parse_args_requires_both_flags(self) -> None:
        with self.assertRaises(ValueError):
            benchmark_utils.parse_args(["--fixture", "x"])

    def test_parse_args_resolves_paths(self) -> None:
        fixture, out_dir = benchmark_utils.parse_args(["--fixture", ".", "--out", "."])
        self.assertTrue(fixture.is_absolute())
        self.assertTrue(out_dir.is_absolute())


class JsonSafeTests(unittest.TestCase):
    def test_common_types_are_serializable(self) -> None:
        payload = {
            "path": Path("/tmp/x"),
            "nested": {"set": {1, 2}},
            "none": None,
            "flag": True,
        }
        encoded = json.dumps(benchmark_utils.to_json_safe(payload))
        self.assertIn("/tmp/x", encoded)
        self.assertIn("1", encoded)


class RunResultTests(unittest.TestCase):
    def _write(self, out_dir: Path, presence: dict[str, bool]) -> dict:
        benchmark_utils.write_run_result(
            out_dir=out_dir,
            fixture_dir=CASE_101,
            prompt_pack={"id": "intake_triage_stress_v1", "task_id": "intake_triage", "dataset_split": "stress_v1"},
            output_presence=presence,
            trace_path=out_dir / "agent-trace.jsonl",
            runtime_metadata={"duration_seconds": 1.5, "total_cost_usd": None},
            framework_name="unit-test",
        )
        return json.loads((out_dir / "run_result.json").read_text(encoding="utf-8"))

    def test_outcome_is_partial_only_when_every_output_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            complete = self._write(out_dir, {name: True for name in benchmark_utils.REQUIRED_OUTPUTS})
            self.assertEqual(complete["outcome"], "partial")
            self.assertEqual(complete["run_id"], "stress_v1-case-101")

            incomplete = self._write(out_dir, {name: False for name in benchmark_utils.REQUIRED_OUTPUTS})
            self.assertEqual(incomplete["outcome"], "fail")


if __name__ == "__main__":
    unittest.main()
