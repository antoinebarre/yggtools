"""Quality check: test suite execution via pytest."""

from __future__ import annotations

import re
from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


def _parse_summary(output: str) -> str:
    """Extract a compact summary line from pytest output.

    Combines the pytest result counts with the coverage percentage into a
    single human-readable string, e.g. ``"103 passed · coverage 100%"``.
    Falls back to the raw last line when no structured data is found.

    Args:
        output: Combined stdout + stderr from the pytest run.

    Returns:
        Compact summary string.
    """
    lines = output.splitlines()

    result_line = next(
        (
            ln
            for ln in reversed(lines)
            if re.search(r"\d+ (passed|failed|error)", ln)
        ),
        "",
    )
    counts = re.sub(r"=+\s*", "", result_line).strip() if result_line else ""

    cov_match = re.search(r"Total coverage:\s*([\d.]+%)", output)
    coverage = f"coverage {cov_match.group(1)}" if cov_match else ""

    if counts and coverage:
        return f"{counts} · {coverage}"
    return counts or coverage or (lines[-1] if lines else "")


def _parse_test_findings(output: str) -> list[dict[str, object]]:
    """Extract structured findings from pytest failure output.

    Parses ``FAILED path::test_name`` lines from pytest output.

    Args:
        output: Combined stdout and stderr from the pytest run.

    Returns:
        List of finding dicts with ``path`` and ``message`` keys.
    """
    pattern = re.compile(r"FAILED\s+(?P<path>[^:]+)::(?P<test>.+)")
    findings: list[dict[str, object]] = []
    for line in output.splitlines():
        match = pattern.search(line)
        if match:
            findings.append(
                {
                    "path": match.group("path"),
                    "message": f"FAILED {match.group('test')}",
                }
            )
    return findings


@register("tests")
def check_tests(project_dir: Path) -> CheckResult:
    """Run the test suite with pytest and enforce 100 % coverage.

    Runs ``uv run pytest`` in the project directory.  Coverage thresholds
    and reporting are expected in ``pyproject.toml`` under
    ``[tool.pytest.ini_options]``.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with a compact summary combining pass counts and
        coverage.
    """
    args = ["run", "pytest"]
    result = run_uv(
        args,
        cwd=project_dir,
        capture=True,
    )
    output = (result.stdout + result.stderr).strip()
    summary = _parse_summary(output)
    if result.returncode == 0:
        return CheckResult(
            name="tests",
            passed=True,
            detail=summary,
            command=("uv", *args),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    findings = _parse_test_findings(output)
    return CheckResult(
        name="tests",
        passed=False,
        detail=summary,
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={
            "failure_count": len(findings),
            "findings": findings,
        },
    )
