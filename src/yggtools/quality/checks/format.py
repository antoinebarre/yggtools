"""Quality check: code formatting via ruff."""

from __future__ import annotations

import re
from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


def _parse_findings(output: str) -> list[dict[str, object]]:
    """Extract structured findings from ruff format output.

    Args:
        output: Combined stdout and stderr from ruff format.

    Returns:
        List of finding dicts with ``path`` and ``message`` keys.
    """
    findings: list[dict[str, object]] = []
    for line in output.splitlines():
        match = re.match(r"Would reformat:\s*(.+)", line)
        if match:
            findings.append(
                {
                    "path": match.group(1).strip(),
                    "message": "file would be reformatted",
                }
            )
    return findings


@register("format")
def check_format(project_dir: Path) -> CheckResult:
    """Check that all source files are correctly formatted with ruff.

    Runs ``uv run ruff format --check src tests`` in the project directory.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with the count of files that would be reformatted.
    """
    args = ["run", "ruff", "format", "--check", "src", "tests"]
    result = run_uv(
        args,
        cwd=project_dir,
        capture=True,
    )
    if result.returncode == 0:
        return CheckResult(
            name="format",
            passed=True,
            detail="0 file(s) to reformat",
            command=("uv", *args),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    output = result.stdout + result.stderr
    findings = _parse_findings(output)
    count = len(findings)
    return CheckResult(
        name="format",
        passed=False,
        detail=f"{count} file(s) to reformat",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={
            "files_to_reformat": count,
            "findings": findings,
        },
    )
