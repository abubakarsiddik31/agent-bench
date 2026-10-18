"""Tests for the deterministic scoring helpers in common/evaluation_utils.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from common.evaluation_utils import (
    count_non_comment_lines,
    list_framework_source_files,
    parse_markdown_sections,
    read_yaml_scalar,
    score_loc_required,
    try_load_json,
    weighted_average,
)


class WeightedAverageTests(unittest.TestCase):
    def test_weights_are_normalized(self) -> None:
        self.assertEqual(weighted_average({"a": 5.0, "b": 0.0}, {"a": 1, "b": 1}), 2.5)

    def test_missing_keys_count_as_zero(self) -> None:
        self.assertEqual(weighted_average({"a": 5.0}, {"a": 50, "b": 50}), 2.5)

    def test_zero_total_weight_is_zero_not_error(self) -> None:
        self.assertEqual(weighted_average({"a": 5.0}, {}), 0.0)

    def test_is_deterministic_and_rounded(self) -> None:
        scores = {"a": 4.3, "b": 3.9, "c": 2.2}
        weights = {"a": 25, "b": 20, "c": 15}
        self.assertEqual(weighted_average(scores, weights), weighted_average(scores, weights))
        self.assertEqual(weighted_average(scores, weights), round(
            (4.3 * 25 + 3.9 * 20 + 2.2 * 15) / 60, 3
        ))


class ScoreLocRequiredTests(unittest.TestCase):
    def test_boundaries_are_inclusive(self) -> None:
        cases = {
            0: 5.0,
            120: 5.0,
            121: 4.0,
            200: 4.0,
            201: 3.0,
            300: 3.0,
            301: 2.0,
            450: 2.0,
            451: 1.0,
            10_000: 1.0,
        }
        for lines_of_code, expected in cases.items():
            with self.subTest(lines_of_code=lines_of_code):
                self.assertEqual(score_loc_required(lines_of_code), expected)

    def test_is_monotonic_non_increasing(self) -> None:
        scores = [score_loc_required(n) for n in range(0, 600, 7)]
        self.assertEqual(scores, sorted(scores, reverse=True))


class CountLinesTests(unittest.TestCase):
    def test_skips_blanks_and_comment_styles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text(
                "\n".join(
                    [
                        "import os",
                        "",
                        "# a comment",
                        "// not python but still skipped",
                        "/* block start */",
                        "* docstring-ish line",
                        "value = 1",
                    ]
                ),
                encoding="utf-8",
            )
            self.assertEqual(count_non_comment_lines(path), 2)


class ListSourceFilesTests(unittest.TestCase):
    def test_filters_extensions_and_pycache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "intake-triage"
            (root / "__pycache__").mkdir(parents=True)
            (root / "agent.py").write_text("x = 1\n", encoding="utf-8")
            (root / "notes.md").write_text("# notes\n", encoding="utf-8")
            (root / "__pycache__" / "agent.cpython-312.pyc").write_text("", encoding="utf-8")

            found = [path.name for path in list_framework_source_files(root)]
            self.assertEqual(found, ["agent.py"])


class MarkdownSectionTests(unittest.TestCase):
    def test_sections_are_keyed_by_heading_text(self) -> None:
        sections = parse_markdown_sections("# One\nalpha\n\n## Two\nbeta\n")
        self.assertEqual(sections["One"], "alpha")
        self.assertEqual(sections["Two"], "beta")

    def test_text_before_first_heading_is_ignored(self) -> None:
        self.assertEqual(parse_markdown_sections("preamble\n# H\nbody"), {"H": "body"})


class YamlScalarTests(unittest.TestCase):
    def test_missing_key_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "f.yml"
            path.write_text("id: abc\n", encoding="utf-8")
            self.assertEqual(read_yaml_scalar(path, "id"), "abc")
            with self.assertRaises(ValueError):
                read_yaml_scalar(path, "nope")


class TryLoadJsonTests(unittest.TestCase):
    def test_returns_none_instead_of_raising(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text("{not json", encoding="utf-8")
            self.assertIsNone(try_load_json(path))
            self.assertIsNone(try_load_json(Path(tmp) / "missing.json"))


if __name__ == "__main__":
    unittest.main()
