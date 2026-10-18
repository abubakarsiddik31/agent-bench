"""Tests for agent-trace analysis and tool-call metrics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluation.evaluate_framework import analyze_trace, compute_tool_call_metrics


def tool_call(name: str) -> dict:
    return {"type": "assistant", "content": [{"kind": "tool", "value": name}]}


class TraceTestCase(unittest.TestCase):
    """Base class providing a self-cleaning trace file helper."""

    def write_trace(self, records: list[object]) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "agent-trace.jsonl"
        lines = [
            record if isinstance(record, str) else json.dumps(record)
            for record in records
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


class AnalyzeTraceTests(TraceTestCase):
    def test_missing_trace_returns_zeroed_stats(self) -> None:
        stats = analyze_trace(Path("/nonexistent/agent-trace.jsonl"))
        self.assertEqual(stats["tool_messages"], 0)
        self.assertEqual(stats["failed_tool_calls_detected"], 0)
        self.assertEqual(stats["unique_tools"], [])

    def test_tool_calls_are_counted_classified_and_deduplicated(self) -> None:
        path = self.write_trace(
            [
                tool_call("read_workspace_file"),
                tool_call("search_workspace"),
                tool_call("write_workspace_file"),
                tool_call("write_workspace_file"),
                {"type": "MessageOutputItem"},
            ]
        )
        stats = analyze_trace(path)

        self.assertEqual(stats["tool_messages"], 4)
        # Both "assistant" tool-call records and "MessageOutputItem" records
        # increment the assistant message count.
        self.assertEqual(stats["assistant_messages"], 5)
        self.assertEqual(stats["write_calls"], 2)
        self.assertEqual(stats["read_like_calls"], 2)
        self.assertEqual(
            stats["unique_tools"],
            ["read_workspace_file", "search_workspace", "write_workspace_file"],
        )
        self.assertEqual(stats["failed_tool_calls_detected"], 0)

    def test_benign_mentions_of_error_are_not_failures(self) -> None:
        """A trace that merely talks about errors must not be scored as failing."""
        path = self.write_trace(
            [
                {
                    "type": "assistant",
                    "content": [{"kind": "text", "value": "No error was found in the intake packet."}],
                },
                tool_call("write_workspace_file"),
                # A tool whose *name* contains "read" is not a failure either.
                tool_call("read_workspace_file"),
            ]
        )
        stats = analyze_trace(path)

        self.assertEqual(stats["failed_tool_calls_detected"], 0)
        self.assertEqual(stats["passed_tool_calls_detected"], 2)

    def test_explicit_error_events_count_as_failures(self) -> None:
        path = self.write_trace(
            [
                tool_call("write_workspace_file"),
                tool_call("read_workspace_file"),
                {"type": "tool_error"},
            ]
        )
        self.assertEqual(analyze_trace(path)["failed_tool_calls_detected"], 1)

    def test_failed_count_is_capped_at_total_calls(self) -> None:
        path = self.write_trace(
            [
                tool_call("write_workspace_file"),
                {"type": "error"},
                {"type": "error"},
                {"type": "error"},
            ]
        )
        stats = analyze_trace(path)
        self.assertEqual(stats["failed_tool_calls_detected"], 1)
        self.assertEqual(stats["passed_tool_calls_detected"], 0)

    def test_tool_call_item_status_is_respected(self) -> None:
        path = self.write_trace(
            [
                {"type": "ToolCallItem", "raw_item": {"name": "read_workspace_file", "status": "completed"}},
                {"type": "ToolCallItem", "raw_item": {"name": "read_workspace_file", "status": "failed"}},
            ]
        )
        stats = analyze_trace(path)
        self.assertEqual(stats["tool_messages"], 2)
        self.assertEqual(stats["failed_tool_calls_detected"], 1)
        self.assertEqual(stats["passed_tool_calls_detected"], 1)

    def test_malformed_lines_are_skipped(self) -> None:
        path = self.write_trace(["{not json", tool_call("write_workspace_file")])
        self.assertEqual(analyze_trace(path)["tool_messages"], 1)


class ToolCallMetricsTests(unittest.TestCase):
    def test_rates_and_composite_efficiency(self) -> None:
        stats = {
            "tool_messages": 4,
            "failed_tool_calls_detected": 0,
            "passed_tool_calls_detected": 4,
            "write_calls": 4,
            "tool_calls_by_name": {"write_workspace_file": 4},
            "unique_tools": ["write_workspace_file"],
            "read_like_calls": 0,
        }
        summary = {
            "normalized_output_presence": {
                "triage_decision.json": True,
                "candidate_match_table.json": True,
            }
        }
        metrics = compute_tool_call_metrics(stats, summary)

        self.assertEqual(metrics["total_tool_calls"], 4)
        self.assertEqual(metrics["required_artifacts_produced"], 2)
        self.assertEqual(metrics["required_artifacts_expected"], 2)
        self.assertEqual(metrics["tool_call_success_rate"], 1.0)
        self.assertEqual(metrics["write_completion_rate"], 0.5)
        self.assertEqual(metrics["output_coverage_rate"], 1.0)
        self.assertEqual(metrics["custom_tool_efficiency"], 0.875)
        self.assertTrue(metrics["tool_call_passed"])

    def test_zero_calls_does_not_divide_by_zero(self) -> None:
        metrics = compute_tool_call_metrics(
            {
                "tool_messages": 0,
                "failed_tool_calls_detected": 0,
                "passed_tool_calls_detected": 0,
                "write_calls": 0,
                "unique_tools": [],
            },
            {"normalized_output_presence": {}},
        )
        self.assertEqual(metrics["tool_call_success_rate"], 0.0)
        self.assertEqual(metrics["write_completion_rate"], 0.0)
        self.assertEqual(metrics["output_coverage_rate"], 0.0)
        self.assertFalse(metrics["tool_call_passed"])


if __name__ == "__main__":
    unittest.main()
