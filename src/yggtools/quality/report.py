"""Markdown report writer for quality pipeline results."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from yggtools.quality.runner import CheckResult


def write_report(
    results: list[CheckResult],
    project_dir: Path,
    output: Path,
) -> None:
    """Write a Markdown quality report to disk.

    Creates ``output`` and any required parent directories.

    Args:
        results: Ordered list of check results to include.
        project_dir: Project root directory (used as the report title).
        output: Destination path for the Markdown file.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines: list[str] = [
        f"# Quality report — {project_dir.name}",
        "",
        f"Generated: {timestamp}",
        "",
        "## Results",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        lines.append(f"| `{r.name}` | {status} | {r.detail} |")

    lines += [
        "",
        "## Summary",
        "",
        f"**{passed} passed** / **{failed} failed**",
        "",
    ]

    output.write_text("\n".join(lines), encoding="utf-8")
