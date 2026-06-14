"""Generate a Markdown check report from work/ log files.

Called by check.sh after all pipeline steps have run. Reads the log
files produced in work/, scans the project source tree for inline
suppression comments, computes SHA-256 checksums, and writes a
structured Markdown report using mkforge.

Usage:
    python scripts/generate_report.py [--output PATH] [--project-dir PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    from mkforge import (
        Chapter,
        Paragraph,
        Report,
        Section,
        Table,
    )
except ImportError:
    print(  # noqa: T201
        "ERROR: mkforge is not installed. "
        "Add mkforge to your project dependencies and run uv sync.",
        file=sys.stderr,
    )
    sys.exit(1)

_WORK_DIR = Path("work")
_PIPELINE_STEPS = [
    "format",
    "ruff",
    "flake8",
    "docstrings",
    "typecheck",
    "metrics",
    "security-code",
    "security-deps",
    "tests",
]
_AUDITED_GLOBS = [
    "src/**/*.py",
    "tests/**/*.py",
    "scripts/**",
    "pyproject.toml",
    "Makefile",
    ".python-version",
]
_SUPPRESSION_SRC_DIRS = ["src", "tests", "scripts"]
_SUPPRESSION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
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


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed argument namespace with ``output`` and ``project_dir``.
    """
    parser = argparse.ArgumentParser(
        description="Generate yggtools check report.",
    )
    parser.add_argument(
        "--output",
        default=str(_WORK_DIR / "report.md"),
        help="Destination Markdown file (default: work/report.md).",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root directory (default: current directory).",
    )
    return parser.parse_args()


def _read_step_results(
    project_dir: Path,
) -> list[tuple[str, bool, str]]:
    """Read pipeline step outcomes from work/<step>.exit and .log files.

    Reads the exit-code sentinel ``work/<name>.exit`` written by check.sh.
    Falls back to ``True`` when a log exists but no exit file is present.

    Args:
        project_dir: Project root; work/ is resolved relative to it.

    Returns:
        List of (step_name, passed, detail) triples in pipeline order.
    """
    work = project_dir / _WORK_DIR
    results = []
    for step in _PIPELINE_STEPS:
        log = work / f"{step}.log"
        exit_file = work / f"{step}.exit"
        if exit_file.exists():
            passed = exit_file.read_text(encoding="utf-8").strip() == "0"
        else:
            passed = log.exists()
        detail = ""
        if log.exists():
            lines = log.read_text(encoding="utf-8").splitlines()
            detail = lines[-1].strip() if lines else ""
        results.append((step, passed, detail))
    return results


def _collect_checksums(project_dir: Path) -> list[tuple[str, str]]:
    """Compute SHA-256 checksums for audited project files.

    Args:
        project_dir: Project root.

    Returns:
        Sorted list of (relative_path, sha256_hex) pairs.
    """
    seen: set[Path] = set()
    items: list[tuple[str, str]] = []
    for pattern in _AUDITED_GLOBS:
        for path in sorted(project_dir.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            items.append((str(path.relative_to(project_dir)), digest))
    items.sort(key=lambda t: t[0])
    return items


def _scan_file_suppressions(
    py_file: Path,
    project_dir: Path,
) -> list[tuple[str, int, str, str, str]]:
    """Scan a single Python file for inline suppression comments.

    Args:
        py_file: Absolute path to the file to scan.
        project_dir: Project root used to compute relative paths.

    Returns:
        List of (file, line, kind, code, excerpt) tuples for this file.
    """
    rel = str(py_file.relative_to(project_dir))
    try:
        lines = py_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    items: list[tuple[str, int, str, str, str]] = []
    for lineno, text in enumerate(lines, start=1):
        items.extend(_extract_line_suppressions(rel, lineno, text))
    return items


def _extract_line_suppressions(
    rel: str,
    lineno: int,
    text: str,
) -> list[tuple[str, int, str, str, str]]:
    """Extract suppression annotations from a single source line.

    Args:
        rel: Relative file path for the result tuples.
        lineno: 1-based line number.
        text: Raw source line text.

    Returns:
        List of (file, line, kind, code, excerpt) tuples.
    """
    emitted: set[tuple[str, str]] = set()
    items: list[tuple[str, int, str, str, str]] = []
    excerpt = text.strip()
    for kind, pattern in _SUPPRESSION_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        code = m.group(1).strip() if m.lastindex else ""
        key = (kind, code)
        if key not in emitted:
            emitted.add(key)
            items.append((rel, lineno, kind, code, excerpt))
    return items


def _scan_suppressions(
    project_dir: Path,
) -> list[tuple[str, int, str, str, str]]:
    """Scan project source directories for inline suppression comments.

    Args:
        project_dir: Project root.

    Returns:
        Sorted list of (file, line, kind, code, excerpt) tuples.
    """
    items: list[tuple[str, int, str, str, str]] = []
    for src_name in _SUPPRESSION_SRC_DIRS:
        src_dir = project_dir / src_name
        if not src_dir.is_dir():
            continue
        for py_file in sorted(src_dir.rglob("*.py")):
            items.extend(_scan_file_suppressions(py_file, project_dir))
    items.sort(key=lambda t: (t[0], t[1]))
    return items


def _yggtools_version() -> str:
    """Return the installed yggtools version string.

    Reads from ``importlib.metadata``; returns ``"unknown"`` if the
    package is not installed in the current environment.

    Returns:
        Version string, or ``"unknown"`` if not determinable.
    """
    try:
        return importlib.metadata.version("yggtools")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _build_report(
    project_dir: Path,
    step_results: list[tuple[str, bool, str]],
    checksums: list[tuple[str, str]],
    suppressions: list[tuple[str, int, str, str, str]],
) -> Report:
    """Assemble the mkforge Report object.

    Args:
        project_dir: Project root directory.
        step_results: Pipeline step outcomes from _read_step_results.
        checksums: File checksum pairs from _collect_checksums.
        suppressions: Suppression items from _scan_suppressions.

    Returns:
        Fully assembled mkforge Report.
    """
    passed = sum(1 for _, ok, _ in step_results if ok)
    failed = len(step_results) - passed
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    version = _yggtools_version()
    project_name = project_dir.resolve().name

    summary = Chapter(title="Summary").add(
        Table(
            headers=("Field", "Value"),
            rows=(
                ("Project", project_name),
                ("Directory", str(project_dir.resolve())),
                ("yggtools version", version),
                ("Generated at", now),
                ("Checks passed", str(passed)),
                ("Checks failed", str(failed)),
                ("Suppressions found", str(len(suppressions))),
            ),
        ),
    )
    checks_chapter = Chapter(title="Check results").add(
        Table(
            headers=("Step", "Status", "Detail"),
            rows=tuple(
                (name, "PASS" if ok else "FAIL", detail)
                for name, ok, detail in step_results
            ),
        ),
    )
    checksums_chapter = _build_checksums_chapter(checksums)
    suppressions_chapter = _build_suppressions_chapter(suppressions)

    report = Report(
        title=f"yggtools check report — {project_name}",
        toc=True,
    )
    report.add(
        summary,
        checks_chapter,
        checksums_chapter,
        suppressions_chapter,
    )
    return report


def _build_checksums_chapter(
    checksums: list[tuple[str, str]],
) -> Chapter:
    """Build the File Checksums chapter.

    Args:
        checksums: List of (path, sha256) pairs.

    Returns:
        Chapter with a checksums table or a placeholder paragraph.
    """
    if checksums:
        return Chapter(title="File checksums").add(
            Table(
                headers=("File", "SHA-256"),
                rows=tuple(checksums),
            ),
        )
    return Chapter(title="File checksums").add(
        Paragraph("No files matched the audit patterns."),
    )


def _build_suppressions_chapter(
    suppressions: list[tuple[str, int, str, str, str]],
) -> Chapter:
    """Build the Security Suppressions chapter.

    Args:
        suppressions: Flat list of suppression tuples.

    Returns:
        Chapter with one section per file.
    """
    chapter = Chapter(title="Security suppressions")
    if not suppressions:
        chapter.add(
            Paragraph(
                "No inline suppressions found in the audited source tree.",
            ),
        )
        return chapter

    by_file: dict[str, list[tuple[str, int, str, str, str]]] = {}
    for item in suppressions:
        by_file.setdefault(item[0], []).append(item)

    chapter.add(
        Paragraph(
            f"{len(suppressions)} suppression(s) found across "
            f"{len(by_file)} file(s). "
            "Review each entry — suppressed rules bypass automated "
            "quality gates.",
        ),
    )
    for file_path in sorted(by_file):
        rows = tuple((str(i[1]), i[2], i[3], i[4]) for i in by_file[file_path])
        chapter.add(
            Section(title=file_path).add(
                Table(
                    headers=("Line", "Type", "Code", "Excerpt"),
                    rows=rows,
                ),
            ),
        )
    return chapter


def main() -> int:
    """Run the report generator.

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    args = _parse_args()
    project_dir = Path(args.project_dir).resolve()
    output = Path(args.output)

    step_results = _read_step_results(project_dir)
    checksums = _collect_checksums(project_dir)
    suppressions = _scan_suppressions(project_dir)
    report = _build_report(
        project_dir,
        step_results,
        checksums,
        suppressions,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    report.save(output)
    print(f"Report written to {output}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
