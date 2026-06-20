"""Quality check: linting via ruff and flake8."""

from __future__ import annotations

from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


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
    lines = (result.stdout + result.stderr).splitlines()
    errors = [ln for ln in lines if ln and not ln.startswith("Found")]
    count = len(errors)
    first = errors[0] if errors else ""
    return CheckResult(
        name="ruff",
        passed=False,
        detail=f"{count} error(s) — {first}" if first else f"{count} error(s)",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={"error_count": count, "first_error": first},
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
    lines = [
        ln for ln in (result.stdout + result.stderr).splitlines() if ln.strip()
    ]
    return CheckResult(
        name="flake8",
        passed=False,
        detail=f"{len(lines)} violation(s)",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={"violation_count": len(lines), "violations": lines},
    )
