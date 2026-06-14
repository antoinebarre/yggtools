"""Build and save the yggtools check report using mkforge."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from mkforge import (
    Chapter,
    Paragraph,
    Report,
    Section,
    Table,
)

from yggtools import __version__
from yggtools.check import run_check
from yggtools.models import (
    CheckResult,
    FileChecksum,
    ReportData,
    SuppressionItem,
)
from yggtools.suppressions import scan_suppressions

_AUDITED_GLOBS: list[str] = [
    "src/**/*.py",
    "tests/**/*.py",
    "scripts/**",
    "pyproject.toml",
    "Makefile",
    ".python-version",
]

_SUPPRESSION_SRC_DIRS: list[str] = ["src", "tests", "scripts"]


def build_report_data(project_dir: Path) -> ReportData:
    """Collect all data needed to render the check report.

    Runs structural checks, computes file checksums, and scans for
    inline suppression comments.

    Args:
        project_dir: Absolute path to the audited project root.

    Returns:
        Populated ReportData instance ready for rendering.
    """
    check_results = run_check(project_dir)
    checksums = collect_checksums(project_dir)
    src_dirs = [
        project_dir / d
        for d in _SUPPRESSION_SRC_DIRS
        if (project_dir / d).is_dir()
    ]
    suppressions = scan_suppressions(src_dirs, project_dir)

    return ReportData(
        project_name=project_dir.name,
        project_dir=project_dir,
        yggtools_version=__version__,
        generated_at=datetime.now(tz=UTC),
        check_results=check_results,
        checksums=checksums,
        suppressions=suppressions,
    )


def collect_checksums(project_dir: Path) -> list[FileChecksum]:
    """Compute SHA-256 checksums for audited files in the project.

    Expands each glob pattern relative to ``project_dir`` and hashes
    every matched regular file. Directories and missing patterns are
    silently skipped.

    Args:
        project_dir: Absolute path to the project root.

    Returns:
        Sorted list of FileChecksum objects, one per matched file.
    """
    seen: set[Path] = set()
    results: list[FileChecksum] = []

    for pattern in _AUDITED_GLOBS:
        for path in sorted(project_dir.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            digest = _sha256(path)
            results.append(
                FileChecksum(
                    path=str(path.relative_to(project_dir)),
                    sha256=digest,
                ),
            )

    results.sort(key=lambda c: c.path)
    return results


def render_report(data: ReportData) -> Report:
    """Assemble a mkforge Report from ReportData.

    Args:
        data: Aggregated check run data.

    Returns:
        Rendered mkforge Report object ready to call ``.save()`` or
        ``.render()`` on.
    """
    report = Report(
        title=f"yggtools check report — {data.project_name}",
        toc=True,
        auto_numbering=False,
    )
    report.add(
        _summary_chapter(data),
        _check_results_chapter(data.check_results),
        _checksums_chapter(data.checksums),
        _suppressions_chapter(data.suppressions),
    )
    return report


def save_report(data: ReportData, output: Path) -> None:
    """Render the report and write it to a Markdown file.

    Args:
        data: Aggregated check run data.
        output: Destination path for the Markdown file.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    render_report(data).save(output)


def _summary_chapter(data: ReportData) -> Chapter:
    """Build the Summary chapter.

    Args:
        data: Report data.

    Returns:
        Chapter with generation metadata and pass/fail counts.
    """
    passed = sum(1 for r in data.check_results if r.passed)
    failed = len(data.check_results) - passed
    suppression_count = len(data.suppressions)

    table = Table(
        headers=("Field", "Value"),
        rows=(
            ("Project", data.project_name),
            ("Directory", str(data.project_dir)),
            ("yggtools version", data.yggtools_version),
            (
                "Generated at",
                data.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            ),
            ("Checks passed", str(passed)),
            ("Checks failed", str(failed)),
            ("Suppressions found", str(suppression_count)),
        ),
    )
    return Chapter(title="Summary").add(table)


def _check_results_chapter(results: list[CheckResult]) -> Chapter:
    """Build the Check Results chapter.

    Args:
        results: Ordered list of check outcomes.

    Returns:
        Chapter with a table row per check.
    """
    rows = tuple(
        (r.label, "PASS" if r.passed else "FAIL", r.detail) for r in results
    )
    table = Table(
        headers=("Check", "Status", "Detail"),
        rows=rows,
    )
    return Chapter(title="Check results").add(table)


def _checksums_chapter(checksums: list[FileChecksum]) -> Chapter:
    """Build the File Checksums chapter.

    Args:
        checksums: List of file path / SHA-256 pairs.

    Returns:
        Chapter with a table row per file.
    """
    if not checksums:
        return Chapter(title="File checksums").add(
            Paragraph("No files matched the audit patterns."),
        )
    rows = tuple((c.path, c.sha256) for c in checksums)
    table = Table(headers=("File", "SHA-256"), rows=rows)
    return Chapter(title="File checksums").add(table)


def _suppressions_chapter(
    suppressions: list[SuppressionItem],
) -> Chapter:
    """Build the Security Suppressions chapter.

    Groups suppression items by source file and renders one Section
    with a detail table per file. An empty chapter is produced when
    no suppressions are found.

    Args:
        suppressions: Flat list of all suppression items.

    Returns:
        Chapter with one Section per file containing suppressions.
    """
    chapter = Chapter(title="Security suppressions")

    if not suppressions:
        chapter.add(
            Paragraph(
                "No inline suppressions found in the audited source tree.",
            ),
        )
        return chapter

    by_file: dict[str, list[SuppressionItem]] = {}
    for item in suppressions:
        by_file.setdefault(item.file, []).append(item)

    total = len(suppressions)
    chapter.add(
        Paragraph(
            f"{total} suppression(s) found across "
            f"{len(by_file)} file(s). "
            "Review each entry — suppressed rules bypass automated "
            "quality gates.",
        ),
    )

    for file_path in sorted(by_file):
        items = by_file[file_path]
        rows = tuple((str(i.line), i.kind, i.code, i.excerpt) for i in items)
        section = Section(title=file_path).add(
            Table(
                headers=("Line", "Type", "Code", "Excerpt"),
                rows=rows,
            ),
        )
        chapter.add(section)

    return chapter


def _sha256(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file.

    Args:
        path: Path to the file to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()
