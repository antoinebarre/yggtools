"""Quality check: security scanning via bandit and pip-audit."""

from __future__ import annotations

from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


@register("security-code")
def check_security_code(project_dir: Path) -> CheckResult:
    """Check source code for security issues using bandit.

    Runs ``uv run bandit -r src -q`` in the project directory.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with issue count or confirmation of no issues.
    """
    args = ["run", "bandit", "-r", "src", "-q"]
    result = run_uv(
        args,
        cwd=project_dir,
        capture=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return CheckResult(
            name="security-code",
            passed=True,
            detail="0 issue(s)",
            command=("uv", *args),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    lines = [ln for ln in output.splitlines() if ln.startswith(">>")]
    count = len(lines)
    return CheckResult(
        name="security-code",
        passed=False,
        detail=f"{count} issue(s)",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={"issue_count": count},
    )


@register("security-deps")
def check_security_deps(project_dir: Path) -> CheckResult:
    """Check runtime dependencies for known vulnerabilities using pip-audit.

    Runs ``uv run pip-audit`` in the project directory.  Skips cleanly when
    no runtime dependencies are declared.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with vulnerability count or confirmation of no issues.
    """
    args = ["run", "pip-audit", "--progress-spinner=off"]
    result = run_uv(
        args,
        cwd=project_dir,
        capture=True,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return CheckResult(
            name="security-deps",
            passed=True,
            detail="No vulnerabilities found",
            command=("uv", *args),
            stdout=result.stdout,
            stderr=result.stderr,
        )
    lines = [ln for ln in output.splitlines() if "vulnerability" in ln.lower()]
    count = len(lines) or 1
    return CheckResult(
        name="security-deps",
        passed=False,
        detail=f"{count} vulnerability(ies) found",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={"vulnerability_count": count},
    )
