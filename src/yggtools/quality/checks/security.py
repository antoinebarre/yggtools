"""Quality check: security scanning via bandit and pip-audit."""

from __future__ import annotations

import re
from pathlib import Path

from yggtools.quality.runner import CheckResult, register
from yggtools.uv import run_uv


def _parse_bandit_findings(output: str) -> list[dict[str, object]]:
    """Extract structured findings from bandit output.

    Parses lines matching ``>> Issue: [CODE:LABEL] ...`` and the
    following ``Location: path:line:col`` line.

    Args:
        output: Combined stdout and stderr from bandit.

    Returns:
        List of finding dicts.
    """
    issue_pattern = re.compile(
        r">>\s*Issue:\s*\[(?P<code>[^\]]+)\]"
        r"\s*(?P<message>.+)",
    )
    location_pattern = re.compile(
        r"^\s*Location:\s*(?P<path>[^:]+):(?P<line>\d+)",
    )
    findings: list[dict[str, object]] = []
    lines = output.splitlines()
    for i, line in enumerate(lines):
        issue_match = issue_pattern.match(line)
        if issue_match:
            finding: dict[str, object] = {
                "code": issue_match.group("code"),
                "message": issue_match.group("message").strip(),
            }
            if i + 1 < len(lines):
                loc_match = location_pattern.match(lines[i + 1])
                if loc_match:
                    finding["path"] = loc_match.group("path")
                    finding["line"] = int(loc_match.group("line"))
            findings.append(finding)
    return findings


def _parse_pip_audit_findings(
    output: str,
) -> list[dict[str, object]]:
    """Extract structured findings from pip-audit output.

    Parses table-style lines with package, version, and vulnerability
    information.

    Args:
        output: Combined stdout and stderr from pip-audit.

    Returns:
        List of finding dicts with ``message`` key.
    """
    findings: list[dict[str, object]] = []
    for line in output.splitlines():
        lower = line.lower()
        if "vulnerability" in lower and not line.startswith("-"):
            findings.append({"message": line.strip()})
    return findings


@register("security-code")
def check_security_code(project_dir: Path) -> CheckResult:
    """Check source code for security issues using bandit.

    Runs ``uv run bandit -r src`` in the project directory.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with issue count or confirmation of no issues.
    """
    args = ["run", "bandit", "-r", "src"]
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
    findings = _parse_bandit_findings(output)
    count = len(findings) or 1
    return CheckResult(
        name="security-code",
        passed=False,
        detail=f"{count} issue(s)",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={
            "issue_count": count,
            "findings": findings,
        },
    )


@register("security-deps")
def check_security_deps(project_dir: Path) -> CheckResult:
    """Check runtime dependencies for known vulnerabilities.

    Runs ``uv run pip-audit`` in the project directory.  Skips cleanly
    when no runtime dependencies are declared.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult with vulnerability count or confirmation of none.
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
    findings = _parse_pip_audit_findings(output)
    count = len(findings) or 1
    return CheckResult(
        name="security-deps",
        passed=False,
        detail=f"{count} vulnerability(ies) found",
        command=("uv", *args),
        stdout=result.stdout,
        stderr=result.stderr,
        metadata={
            "vulnerability_count": count,
            "findings": findings,
        },
    )
