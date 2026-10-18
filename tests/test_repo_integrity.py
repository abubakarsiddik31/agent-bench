"""Repository-level hygiene checks that are cheap to run and catch real regressions.

These guard the properties that make the published benchmark auditable:
no answer-key leakage, a syntactically valid manifest/CI config, and citation
metadata that actually parses.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from tests import REPO_ROOT

EXCLUDED_DIR_PARTS = {
    ".git",
    ".venv",
    ".plans",
    ".axiom",
    "results",
    "node_modules",
    "__pycache__",
    "site-packages",
}

FRAMEWORKS = sorted(
    path.name
    for path in (REPO_ROOT / "frameworks").iterdir()
    if path.is_dir() and not path.name.startswith(".")
)


def iter_tracked_like_files(pattern: str):
    for path in REPO_ROOT.rglob(pattern):
        if EXCLUDED_DIR_PARTS.intersection(path.parts):
            continue
        yield path


class AnswerKeyIsolationTests(unittest.TestCase):
    def test_no_framework_implementation_references_the_answer_key(self) -> None:
        offenders = []
        for path in (REPO_ROOT / "frameworks").rglob("*.py"):
            if EXCLUDED_DIR_PARTS.intersection(path.parts):
                continue
            if "gold" in path.read_text(encoding="utf-8").lower():
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], "framework code must never read the gold answer key")

    def test_answer_key_lives_only_in_fixture_directories(self) -> None:
        for path in iter_tracked_like_files("gold-expected.json"):
            self.assertIn("fixtures", path.parts, f"unexpected answer-key location: {path}")


class GitignoreTests(unittest.TestCase):
    def test_uv_lock_is_tracked_for_reproducibility(self) -> None:
        patterns = {
            line.strip()
            for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        self.assertNotIn("uv.lock", patterns)
        self.assertTrue((REPO_ROOT / "uv.lock").exists(), "uv.lock is missing")


class ReadmeSentinelTests(unittest.TestCase):
    def test_readme_has_both_generated_regions(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for sentinel in (
            "<!-- SCOREBOARD:START -->",
            "<!-- SCOREBOARD:END -->",
            "<!-- TOOL-METRICS:START -->",
            "<!-- TOOL-METRICS:END -->",
        ):
            self.assertIn(sentinel, readme)


class YamlValidityTests(unittest.TestCase):
    def test_every_repository_yaml_file_parses(self) -> None:
        yaml_files = sorted(
            {*iter_tracked_like_files("*.yml"), *iter_tracked_like_files("*.yaml")}
        )
        self.assertTrue(yaml_files, "no YAML files found; the filter is wrong")

        for path in yaml_files:
            with self.subTest(path=str(path.relative_to(REPO_ROOT))):
                yaml.safe_load(path.read_text(encoding="utf-8"))


class ExecutionContractTests(unittest.TestCase):
    def test_model_control_is_locked_to_real_models(self) -> None:
        contract = yaml.safe_load(
            (REPO_ROOT / "evaluation" / "benchmark-execution.yml").read_text(encoding="utf-8")
        )
        model_control = contract["model_control"]

        self.assertEqual(model_control["status"], "locked")
        self.assertNotIn("TBD", json.dumps(model_control))

        locked = model_control["locked_models"]
        self.assertTrue(locked)
        for entry in locked:
            self.assertTrue(entry["model_id"].strip())
            self.assertTrue(entry["used_by"], "every locked model must name its frameworks")

    def test_judge_model_is_pinned(self) -> None:
        judge = yaml.safe_load(
            (REPO_ROOT / "evaluation" / "judge-model.yml").read_text(encoding="utf-8")
        )
        self.assertNotIn("TBD", json.dumps(judge))


class FrameworkLayoutTests(unittest.TestCase):
    def test_every_framework_has_a_readme(self) -> None:
        self.assertTrue(FRAMEWORKS, "no frameworks found")
        for framework in FRAMEWORKS:
            with self.subTest(framework=framework):
                self.assertTrue((REPO_ROOT / "frameworks" / framework / "README.md").exists())

    def test_every_framework_has_an_intake_triage_entry_point(self) -> None:
        for framework in FRAMEWORKS:
            with self.subTest(framework=framework):
                agent = REPO_ROOT / "frameworks" / framework / "intake-triage" / "agent.py"
                self.assertTrue(agent.exists())
                self.assertGreater(agent.stat().st_size, 0)


class CitationTests(unittest.TestCase):
    def test_citation_metadata_parses_and_is_complete(self) -> None:
        citation = yaml.safe_load((REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8"))

        for key in ("cff-version", "message", "title", "type", "authors", "license", "repository-code"):
            with self.subTest(key=key):
                self.assertIn(key, citation)

        self.assertEqual(citation["cff-version"], "1.2.0")
        self.assertEqual(citation["type"], "software")
        self.assertTrue(citation["authors"][0]["family-names"])
        self.assertTrue(citation["authors"][0]["given-names"])


if __name__ == "__main__":
    unittest.main()
