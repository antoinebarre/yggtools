"""Shared helpers for yggtools command-line modules."""

from __future__ import annotations

from pathlib import Path


def relative_to_project(path: Path, project_dir: Path) -> str:
    """Return a display path relative to the project when possible.

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


def resolve_report_dir(project_dir: Path, report_dir: str | None) -> Path:
    """Resolve the artifact output directory.

    Args:
        project_dir: Project root directory.
        report_dir: Optional user-specified directory.

    Returns:
        Resolved absolute path for artifact output.
    """
    if report_dir is None:
        return project_dir / "work" / "reports"
    requested = Path(report_dir)
    if requested.is_absolute():
        return requested
    return project_dir / requested


def short_text(value: str, limit: int) -> str:
    """Shorten a console field while keeping it recognizable.

    Args:
        value: Text to shorten.
        limit: Maximum character length.

    Returns:
        Shortened string with trailing ellipsis if truncated.
    """
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}..."


def tail(text: str, *, max_lines: int = 20) -> str:
    """Return the last lines of captured output for console display.

    Args:
        text: Raw captured output.
        max_lines: Maximum lines to return.

    Returns:
        Trimmed text with blank lines removed.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])
