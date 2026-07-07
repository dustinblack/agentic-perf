"""Tests for evaluate agent benchmark artifact tools."""

from __future__ import annotations

import json


class TestListArtifacts:
    async def test_lists_files(self, tmp_path):
        from agents.evaluate.server import list_benchmark_artifacts

        results_dir = tmp_path / "results-2025-01-01"
        results_dir.mkdir()
        (results_dir / "host_1_boot_time_logs.json").write_text("{}")
        (results_dir / "host_1_serial-1.json").write_text("{}")
        (results_dir / "host_1_journal.log").write_text("log")
        (results_dir / "collection_status.json").write_text("{}")

        result = json.loads(await list_benchmark_artifacts(str(tmp_path)))
        assert result["count"] == 4
        types = {a["type"] for a in result["artifacts"]}
        assert "serial_capture" in types
        assert "journal_log" in types
        assert "boot_timing_data" in types
        assert "collection_status" in types

    async def test_missing_directory(self):
        from agents.evaluate.server import list_benchmark_artifacts

        result = json.loads(await list_benchmark_artifacts("/nonexistent/path"))
        assert "error" in result

    async def test_classifies_types(self, tmp_path):
        from agents.evaluate.server import _classify_artifact

        assert _classify_artifact("foo-serial-1.json") == "serial_capture"
        assert _classify_artifact("foo_journal.log") == "journal_log"
        assert _classify_artifact("foo_trace.log") == "trace_log"
        assert _classify_artifact("foo_summary.json") == "timing_summary"
        assert _classify_artifact("merged-results.json") == "merged_results"
        assert _classify_artifact("metadata.json") == "system_metadata"
        assert _classify_artifact("random.txt") == "other"


class TestReadArtifact:
    async def test_reads_file(self, tmp_path):
        from agents.evaluate.server import read_benchmark_artifact

        (tmp_path / "test.log").write_text("\n".join(f"line {i}" for i in range(50)))
        result = json.loads(
            await read_benchmark_artifact(str(tmp_path), "test.log", offset=0, limit=10)
        )
        assert result["total_lines"] == 50
        assert result["lines_returned"] == 10
        assert result["has_more"] is True
        assert "line 0" in result["content"]
        assert "line 9" in result["content"]

    async def test_offset_pagination(self, tmp_path):
        from agents.evaluate.server import read_benchmark_artifact

        (tmp_path / "test.log").write_text("\n".join(f"line {i}" for i in range(20)))
        result = json.loads(
            await read_benchmark_artifact(
                str(tmp_path), "test.log", offset=15, limit=10
            )
        )
        assert result["lines_returned"] == 5
        assert result["has_more"] is False
        assert "line 15" in result["content"]

    async def test_missing_file(self, tmp_path):
        from agents.evaluate.server import read_benchmark_artifact

        result = json.loads(
            await read_benchmark_artifact(str(tmp_path), "nonexistent.log")
        )
        assert "error" in result

    async def test_path_traversal_blocked(self, tmp_path):
        from agents.evaluate.server import read_benchmark_artifact

        result = json.loads(
            await read_benchmark_artifact(str(tmp_path), "../../etc/passwd")
        )
        assert "error" in result
        assert "traversal" in result["error"].lower()
