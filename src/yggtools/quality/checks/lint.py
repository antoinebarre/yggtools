"""Quality check: linting via ruff and flake8."""

from __future__ import annotations

import re
from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


def _parse_lint_findings(output: str) -> list[dict[str, object]]:
    """Extract structured findings from ruff or flake8 output.

    Parses lines matching ``path:line:col: CODE message``.

    Args:
        output: Combined stdout and stderr from the linter.

    Returns:
        List of finding dicts.
    """
    pattern = re.compile(
        r"^(?P<path>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*"
        r"(?P<code>\S+)\s+(?P<message>.+)$",
    )
    findings: list[dict[str, object]] = []
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            findings.append(
                {
                    "path": match.group("path"),
                    "line": int(match.group("line")),
                    "column": int(match.group("col")),
                    "code": match.group("code"),
                    "message": match.group("message"),
                }
            )
    return findings


@register("ruff")
def check_ruff(project_dir: Path) -> CheckResult:
    """Check for lint errors using ruff.

    Runs ``uv run ruff check src tests`` in the project directory.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with the count of ruff errors found.
    """
    args = ["run", "ruff", "check", "src", "tests"]
    result = run_uv(
        args,
        cwd=project_dir,
        capture=True,
    )
    if result.returncode == 0:
        return CheckResult(
            name="ruff",
            passed=True,
            detail="0 error(s)",
            command=("uv", *args),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    output = result.stdout + result.stderr
    findings = _parse_lint_findings(output)
    count = len(findings)
    first_msg = findings[0]["message"] if findings else ""
    return CheckResult(
        name="ruff",
        passed=False,
        detail=(
            f"{count} error(s) — {first_msg}"
            if first_msg
            else f"{count} error(s)"
        ),
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={
            "error_count": count,
            "findings": findings,
        },
    )


@register("flake8")
def check_flake8(project_dir: Path) -> CheckResult:
    """Check for style violations using flake8.

    Runs ``uv run flake8 src tests`` in the project directory.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with the count of flake8 violations found.
    """
    args = ["run", "flake8", "src", "tests"]
    result = run_uv(
        args,
        cwd=project_dir,
        capture=True,
    )
    if result.returncode == 0:
        return CheckResult(
            name="flake8",
            passed=True,
            detail="0 violation(s)",
            command=("uv", *args),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    output = result.stdout + result.stderr
    findings = _parse_lint_findings(output)
    count = len(findings)
    return CheckResult(
        name="flake8",
        passed=False,
        detail=f"{count} violation(s)",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={
            "violation_count": count,
            "findings": findings,
        },
    )
