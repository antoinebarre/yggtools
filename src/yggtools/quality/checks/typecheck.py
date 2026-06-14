"""Quality check: static type checking via mypy."""

from __future__ import annotations

from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


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
    result = run_uv(
        ["run", "mypy", "src", "tests"],
        cwd=project_dir,
        capture=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return CheckResult(name="typecheck", passed=True, detail=output or "Success")
    lines = [ln for ln in output.splitlines() if ": error:" in ln]
    count = len(lines)
    return CheckResult(
        name="typecheck",
        passed=False,
        detail=f"{count} error(s)",
    )
