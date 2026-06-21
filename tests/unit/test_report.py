"""Unit tests for yggtools.quality.report."""

from __future__ import annotations

from pathlib import Path

from yggtools.quality.report import (
    write_check_json_reports,
    write_check_report,
    write_check_reports,
    write_report,
)
from yggtools.quality.runner import CheckResult


def _results() -> list[CheckResult]:
    """Build a sample list of check results.

    Returns:
        Two CheckResult instances: one passing, one failing.
    """
    return [
        CheckResult(
            name="format",
            passed=True,
            detail="0 file(s) to reformat",
        ),
        CheckResult(name="ruff", passed=False, detail="3 error(s)"),
    ]


def test_write_report_creates_file(tmp_path: Path) -> None:
    """Requirement: write_report must create the output file."""
    output = tmp_path / "work" / "report.md"
    write_report(_results(), tmp_path, output)
    assert output.exists()


def test_write_report_contains_check_names(tmp_path: Path) -> None:
    """Requirement: write_report must include each check name in the output."""
    output = tmp_path / "work" / "report.md"
    write_report(_results(), tmp_path, output)
    content = output.read_text()
    assert "format" in content
    assert "ruff" in content


def test_write_report_marks_pass_and_fail(tmp_path: Path) -> None:
    """Requirement: write_report must mark pass and fail checks."""
    output = tmp_path / "work" / "report.md"
    write_report(_results(), tmp_path, output)
    content = output.read_text()
    assert "PASS" in content
    assert "FAIL" in content


def test_write_report_includes_summary_counts(tmp_path: Path) -> None:
    """Requirement: write_report summary must show passed and failed counts."""
    output = tmp_path / "work" / "report.md"
    write_report(_results(), tmp_path, output)
    content = output.read_text()
    assert "1 passed" in content
    assert "1 failed" in content


def test_write_report_creates_parent_directories(tmp_path: Path) -> None:
    """Requirement: write_report must create missing parent directories."""
    output = tmp_path / "deeply" / "nested" / "report.md"
    write_report(_results(), tmp_path, output)
    assert output.exists()


def test_write_check_report_includes_detailed_fields(tmp_path: Path) -> None:
    """Requirement: per-check report must include command and output."""
    output = tmp_path / "work" / "ci" / "reports" / "ruff.md"
    result = CheckResult(
        name="ruff",
        passed=False,
        detail="1 error(s)",
        command=("uv", "run", "ruff", "check"),
        duration_seconds=1.25,
        stdout="src/pkg.py:1:1: E999 boom",
        stderr="warning",
        metadata={"error_count": 1, "nested": {"count": 1}},
        artifacts=(Path("/outside/artifact.txt"),),
    )
    write_check_report(result, tmp_path, output)
    content = output.read_text()
    assert "CI step - ruff" in content
    assert "uv run ruff check" in content
    assert "src/pkg.py" in content
    assert "artifact.txt" in content
    assert "warning" in content
    assert '"count": 1' in content


def test_write_check_reports_creates_one_file_per_result(
    tmp_path: Path,
) -> None:
    """Requirement: per-check reports must be generated for all results."""
    output_dir = tmp_path / "work" / "ci" / "reports"
    paths = write_check_reports(_results(), tmp_path, output_dir)
    assert paths == [output_dir / "format.md", output_dir / "ruff.md"]
    assert all(path.exists() for path in paths)


def test_write_check_json_reports_creates_json_and_checksum(
    tmp_path: Path,
) -> None:
    """Requirement: JSON reports must include sidecar checksums."""
    output_dir = tmp_path / "work" / "ci" / "results"
    reports = write_check_json_reports(_results(), tmp_path, output_dir)
    path, digest = reports["format"]
    assert path == output_dir / "format.json"
    assert path.exists()
    assert path.with_suffix(".json.sha256").exists()
    assert path.with_suffix(".json.sha256").read_text().startswith(digest)


def test_write_check_json_reports_contains_structured_metadata(
    tmp_path: Path,
) -> None:
    """Requirement: JSON reports must preserve metadata for exploitation."""
    output_dir = tmp_path / "work" / "ci" / "results"
    result = CheckResult(
        name="metrics",
        passed=True,
        detail="ok",
        metadata={
            "files": [{"path": "src/a.py", "logical_lines": 3}],
            "paths": (tmp_path / "src" / "a.py",),
        },
    )
    reports = write_check_json_reports([result], tmp_path, output_dir)
    content = reports["metrics"][0].read_text()
    assert '"schema": "yggtools.ci.check.v1"' in content
    assert '"logical_lines": 3' in content
    assert '"src/a.py"' in content
