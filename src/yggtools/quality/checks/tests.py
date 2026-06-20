"""Quality check: test suite execution via pytest."""

from __future__ import annotations

from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


@register("tests")
def check_tests(project_dir: Path) -> CheckResult:
    """Run the test suite with pytest and enforce 100 % coverage.

    Runs ``uv run pytest`` in the project directory.  Coverage thresholds
    and reporting are expected in ``pyproject.toml`` under
    ``[tool.pytest.ini_options]``.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with a pass/fail summary line from pytest output.
    """
    result = run_uv(
        ["run", "pytest"],
        cwd=project_dir,
        capture=True,
    )
    output = (result.stdout + result.stderr).strip()
    summary = next(
        (
            ln
            for ln in reversed(output.splitlines())
            if "passed" in ln or "failed" in ln or "error" in ln
        ),
        output.splitlines()[-1] if output.splitlines() else "",
    )
    if result.returncode == 0:
        return CheckResult(name="tests", passed=True, detail=summary)
    return CheckResult(name="tests", passed=False, detail=summary)
