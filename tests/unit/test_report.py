"""Unit tests for yggtools.quality.report."""

from __future__ import annotations

from pathlib import Path

from yggtools.quality.report import (
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
