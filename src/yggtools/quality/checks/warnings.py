"""Quality warning checks for tracked technical debt markers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from yggtools.quality.runner import CheckResult, register

_SUPPRESSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("noqa", re.compile(r"#\s*noqa(?::\s*[\w,\s-]+)?")),
    ("type-ignore", re.compile(r"#\s*type:\s*ignore(?:\[[^\]]+\])?")),
    ("pragma-no-cover", re.compile(r"#\s*pragma:\s*no cover")),
    ("nosec", re.compile(r"#\s*nosec(?:\s+[\w,\s-]+)?")),
    ("pylint-disable", re.compile(r"#\s*pylint:\s*disable=[\w,\s-]+")),
    ("ruff-noqa", re.compile(r"#\s*ruff:\s*noqa(?::\s*[\w,\s-]+)?")),
    ("fmt-off", re.compile(r"#\s*(?:fmt|ruff:\s*fmt):\s*off")),
)
_TODO_PATTERN = re.compile(r"#\s*(TODO|FIXME|XXX)\b(?P<message>.*)")


@dataclass(frozen=True)
class _MarkerFinding:
    """A source-code marker found by a warning check.

    Attributes:
        path: File path relative to the project root.
        line: One-based source line number.
        marker: Marker category.
        text: Full matching line text.
    """

    path: str
    line: int
    marker: str
    text: str


def _iter_python_files(root: Path) -> list[Path]:
    """Return Python source files below root, excluding generated artifacts.

    Args:
        root: Directory to scan.

    Returns:
        Sorted Python files under root.
    """
    if not root.exists():
        return []
    return sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )


def _relative_to(path: Path, project_dir: Path) -> str:
    """Return path relative to project_dir when possible.

    Args:
        path: Absolute or relative path.
        project_dir: Project root directory.

    Returns:
        Relative path string.
    """
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _finding_payload(finding: _MarkerFinding) -> dict[str, object]:
    """Convert a marker finding to JSON-safe metadata.

    Args:
        finding: Marker finding to serialize.

    Returns:
        JSON-safe finding payload.
    """
    return {
        "path": finding.path,
        "line": finding.line,
        "marker": finding.marker,
        "text": finding.text,
    }


def collect_lint_suppressions(project_dir: Path) -> list[dict[str, object]]:
    """Collect source lines that suppress lint or quality checks.

    Args:
        project_dir: Project root directory.

    Returns:
        JSON-safe suppression finding payloads.
    """
    findings: list[_MarkerFinding] = []
    for path in _iter_python_files(project_dir / "src" / "yggtools"):
        findings.extend(_collect_suppressions_in_file(path, project_dir))
    return [_finding_payload(finding) for finding in findings]


def _collect_suppressions_in_file(
    path: Path,
    project_dir: Path,
) -> list[_MarkerFinding]:
    """Collect suppression markers in one Python file.

    Args:
        path: Python file to scan.
        project_dir: Project root directory.

    Returns:
        Suppression findings in source order.
    """
    findings: list[_MarkerFinding] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        for marker, pattern in _SUPPRESSION_PATTERNS:
            if pattern.search(line):
                findings.append(
                    _MarkerFinding(
                        path=_relative_to(path, project_dir),
                        line=line_number,
                        marker=marker,
                        text=line.strip(),
                    )
                )
    return findings


def collect_todos(project_dir: Path) -> list[dict[str, object]]:
    """Collect TODO-like source markers in the package.

    Args:
        project_dir: Project root directory.

    Returns:
        JSON-safe TODO finding payloads.
    """
    findings: list[_MarkerFinding] = []
    for path in _iter_python_files(project_dir / "src" / "yggtools"):
        findings.extend(_collect_todos_in_file(path, project_dir))
    return [_finding_payload(finding) for finding in findings]


def _collect_todos_in_file(
    path: Path,
    project_dir: Path,
) -> list[_MarkerFinding]:
    """Collect TODO-like markers in one Python file.

    Args:
        path: Python file to scan.
        project_dir: Project root directory.

    Returns:
        TODO findings in source order.
    """
    findings: list[_MarkerFinding] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        match = _TODO_PATTERN.search(line)
        if match:
            findings.append(
                _MarkerFinding(
                    path=_relative_to(path, project_dir),
                    line=line_number,
                    marker=match.group(1).lower(),
                    text=line.strip(),
                )
            )
    return findings


def _warning_result(
    *,
    name: str,
    label: str,
    findings: list[dict[str, object]],
) -> CheckResult:
    """Build a non-blocking warning check result.

    Args:
        name: Check name.
        label: Human-readable finding label.
        findings: Structured findings.

    Returns:
        Passing CheckResult carrying warning metadata.
    """
    count = len(findings)
    return CheckResult(
        name=name,
        passed=True,
        detail=f"{count} {label}(s)",
        metadata={
            "severity": "warning",
            "warning_count": count,
            "findings": findings,
        },
    )


@register("lint-suppressions")
def check_lint_suppressions(project_dir: Path) -> CheckResult:
    """Report lint suppression markers without failing the pipeline.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        Passing CheckResult with warning metadata and suppression findings.
    """
    return _warning_result(
        name="lint-suppressions",
        label="suppression",
        findings=collect_lint_suppressions(project_dir),
    )


@register("todos")
def check_todos(project_dir: Path) -> CheckResult:
    """Report TODO-like package markers without failing the pipeline.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        Passing CheckResult with warning metadata and TODO findings.
    """
    return _warning_result(
        name="todos",
        label="todo",
        findings=collect_todos(project_dir),
    )
