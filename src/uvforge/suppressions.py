"""Scan Python source files for inline suppression comments."""

from __future__ import annotations

import re
from pathlib import Path

from uvforge.models import SuppressionItem

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("noqa", re.compile(r"#\s*noqa:\s*([A-Z0-9,\s]+)", re.IGNORECASE)),
    ("noqa", re.compile(r"#\s*noqa\b(?!:)", re.IGNORECASE)),
    ("nosec", re.compile(r"#\s*nosec\s+([A-Z0-9,\s]+)", re.IGNORECASE)),
    ("nosec", re.compile(r"#\s*nosec\b(?!\s+[A-Z])", re.IGNORECASE)),
    (
        "type: ignore",
        re.compile(r"#\s*type:\s*ignore\[([^\]]+)\]", re.IGNORECASE),
    ),
    (
        "type: ignore",
        re.compile(r"#\s*type:\s*ignore\b(?!\[)", re.IGNORECASE),
    ),
    (
        "pragma: no cover",
        re.compile(r"#\s*pragma:\s*no\s+cover\b", re.IGNORECASE),
    ),
]


def scan_suppressions(
    src_dirs: list[Path],
    project_root: Path,
) -> list[SuppressionItem]:
    """Scan Python source files for inline suppression comments.

    Walks each directory in ``src_dirs``, reads every ``*.py`` file, and
    collects all lines that contain ``# noqa``, ``# nosec``,
    ``# type: ignore``, or ``# pragma: no cover`` annotations.

    Args:
        src_dirs: Directories to search recursively for ``.py`` files.
        project_root: Project root used to compute relative file paths
            in the returned items.

    Returns:
        Ordered list of SuppressionItem objects, sorted by file path
        then line number.
    """
    items: list[SuppressionItem] = []
    for src_dir in src_dirs:
        for py_file in sorted(src_dir.rglob("*.py")):
            items.extend(_scan_file(py_file, project_root))
    items.sort(key=lambda s: (s.file, s.line))
    return items


def _scan_file(path: Path, project_root: Path) -> list[SuppressionItem]:
    """Scan a single Python file for suppression comments.

    Args:
        path: Absolute path to the ``.py`` file to read.
        project_root: Used to compute the relative path stored in each item.

    Returns:
        List of SuppressionItem objects found in this file.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []

    rel = str(path.relative_to(project_root))
    items: list[SuppressionItem] = []
    for lineno, text in enumerate(lines, start=1):
        items.extend(_extract_suppressions(rel, lineno, text))
    return items


def _extract_suppressions(
    rel_path: str,
    lineno: int,
    text: str,
) -> list[SuppressionItem]:
    """Extract all suppression annotations from a single source line.

    Applies each known pattern in order. A line may carry multiple
    independent suppressions (e.g. ``# noqa: E501  # nosec B603``).

    Args:
        rel_path: Relative file path for the SuppressionItem.
        lineno: 1-based line number.
        text: Raw source line text.

    Returns:
        List of SuppressionItem objects found on this line.
    """
    items: list[SuppressionItem] = []
    excerpt = text.strip()
    emitted: set[tuple[str, str]] = set()

    for kind, pattern in _PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        code = match.group(1).strip() if match.lastindex else ""
        key = (kind, code)
        if key not in emitted:
            emitted.add(key)
            items.append(
                SuppressionItem(
                    file=rel_path,
                    line=lineno,
                    kind=kind,
                    code=code,
                    excerpt=excerpt,
                ),
            )
    return items
