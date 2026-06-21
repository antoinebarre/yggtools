"""Quality check: static type checking via mypy."""

from __future__ import annotations

import re
from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


def _parse_mypy_findings(output: str) -> list[dict[str, object]]:
    """Extract structured findings from mypy output.

    Parses lines matching ``path:line: error: message``.

    Args:
        output: Combined stdout and stderr from mypy.

    Returns:
        List of finding dicts with ``path``, ``line``, and ``message``.
    """
    pattern = re.compile(
        r"^(?P<path>[^:]+):(?P<line>\d+):\s*error:\s*(?P<message>.+)$",
    )
    findings: list[dict[str, object]] = []
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if match:
            findings.append(
                {
                    "path": match.group("path"),
                    "line": int(match.group("line")),
                    "message": match.group("message"),
                }
            )
    return findings


@register("typecheck")
def check_typecheck(project_dir: Path) -> CheckResult:
    """Check for type errors using mypy in strict mode.

    Runs ``uv run mypy src tests`` in the project directory.  mypy
    configuration (strict mode, cache dir) is expected in ``pyproject.toml``.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with a success message or the error count.
    """
    args = ["run", "mypy", "src", "tests"]
    result = run_uv(
        args,
        cwd=project_dir,
        capture=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return CheckResult(
            name="typecheck",
            passed=True,
            detail=output or "Success",
            command=("uv", *args),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    findings = _parse_mypy_findings(output)
    count = len(findings)
    return CheckResult(
        name="typecheck",
        passed=False,
        detail=f"{count} error(s)",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={
            "error_count": count,
            "findings": findings,
        },
    )
