"""Quality check: code formatting via ruff."""

from __future__ import annotations

from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


@register("format")
def check_format(project_dir: Path) -> CheckResult:
    """Check that all source files are correctly formatted with ruff.

    Runs ``uv run ruff format --check src tests`` in the project directory.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with the count of files that would be reformatted.
    """
    result = run_uv(
        ["run", "ruff", "format", "--check", "src", "tests"],
        cwd=project_dir,
        capture=True,
    )
    if result.returncode == 0:
        return CheckResult(name="format", passed=True, detail="0 file(s) to reformat")
    lines = (result.stdout + result.stderr).splitlines()
    count = sum(1 for ln in lines if "would reformat" in ln)
    return CheckResult(
        name="format",
        passed=False,
        detail=f"{count} file(s) to reformat",
    )
