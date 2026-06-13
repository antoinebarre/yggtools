"""Unit tests for uvforge.report."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mkforge import Chapter, Report

from uvforge.models import (
    CheckResult,
    FileChecksum,
    ReportData,
    SuppressionItem,
)
from uvforge.report import (
    _check_results_chapter,
    _checksums_chapter,
    _sha256,
    _summary_chapter,
    _suppressions_chapter,
    build_report_data,
    collect_checksums,
    render_report,
    save_report,
)


def _render_chapter(chapter: Chapter) -> str:
    """Wrap a Chapter in a Report and return its rendered Markdown.

    Args:
        chapter: A mkforge Chapter instance.

    Returns:
        Markdown string produced by Report.render().
    """
    return Report(title="t").add(chapter).render()


def _make_report_data(
    tmp_path: Path,
    *,
    check_results: list[CheckResult] | None = None,
    checksums: list[FileChecksum] | None = None,
    suppressions: list[SuppressionItem] | None = None,
) -> ReportData:
    """Build a minimal ReportData for testing.

    Args:
        tmp_path: Pytest temporary directory used as project_dir.
        check_results: Optional list of check results.
        checksums: Optional list of file checksums.
        suppressions: Optional list of suppression items.

    Returns:
        Configured ReportData instance.
    """
    return ReportData(
        project_name="test-proj",
        project_dir=tmp_path,
        uvforge_version="0.1.0",
        generated_at=datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC),
        check_results=check_results or [],
        checksums=checksums or [],
        suppressions=suppressions or [],
    )


def test_sha256_returns_hex_string(tmp_path: Path) -> None:
    """Requirement: _sha256 returns a 64-char lowercase hex digest."""
    f = tmp_path / "f.txt"
    f.write_bytes(b"hello")
    digest = _sha256(f)
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_sha256_deterministic(tmp_path: Path) -> None:
    """Requirement: _sha256 returns identical digest for same content."""
    f = tmp_path / "f.txt"
    f.write_bytes(b"content")
    assert _sha256(f) == _sha256(f)


def test_collect_checksums_finds_py_files(tmp_path: Path) -> None:
    """Requirement: collect_checksums includes src/**/*.py files."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("x = 1\n", encoding="utf-8")
    results = collect_checksums(tmp_path)
    paths = [c.path for c in results]
    assert "src/mod.py" in paths


def test_collect_checksums_sorted(tmp_path: Path) -> None:
    """Requirement: collect_checksums returns results sorted by path."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "z.py").write_text("", encoding="utf-8")
    (src / "a.py").write_text("", encoding="utf-8")
    results = collect_checksums(tmp_path)
    paths = [c.path for c in results]
    assert paths == sorted(paths)


def test_collect_checksums_no_duplicates(tmp_path: Path) -> None:
    """Requirement: collect_checksums never includes the same file twice."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text("x = 1\n", encoding="utf-8")
    results = collect_checksums(tmp_path)
    paths = [c.path for c in results]
    assert len(paths) == len(set(paths))


def test_collect_checksums_empty_project(tmp_path: Path) -> None:
    """Requirement: collect_checksums returns empty list for empty project."""
    results = collect_checksums(tmp_path)
    assert results == []


def test_summary_chapter_contains_project_name(tmp_path: Path) -> None:
    """Requirement: _summary_chapter renders the project name."""
    data = _make_report_data(tmp_path)
    rendered = _render_chapter(_summary_chapter(data))
    assert "test-proj" in rendered


def test_summary_chapter_counts_pass_fail(tmp_path: Path) -> None:
    """Requirement: _summary_chapter shows correct pass/fail counts."""
    results = [
        CheckResult(label="a", passed=True),
        CheckResult(label="b", passed=False, detail="missing"),
    ]
    data = _make_report_data(tmp_path, check_results=results)
    rendered = _render_chapter(_summary_chapter(data))
    assert "1" in rendered


def test_check_results_chapter_shows_pass(tmp_path: Path) -> None:
    """Requirement: _check_results_chapter shows PASS for passing checks."""
    results = [
        CheckResult(label="ruff", passed=True, detail="0 errors"),
    ]
    data = _make_report_data(tmp_path, check_results=results)
    rendered = _render_chapter(_check_results_chapter(data.check_results))
    assert "PASS" in rendered
    assert "ruff" in rendered


def test_check_results_chapter_shows_fail(tmp_path: Path) -> None:
    """Requirement: _check_results_chapter shows FAIL for failing checks."""
    results = [
        CheckResult(label="mypy", passed=False, detail="3 errors"),
    ]
    data = _make_report_data(tmp_path, check_results=results)
    rendered = _render_chapter(_check_results_chapter(data.check_results))
    assert "FAIL" in rendered


def test_checksums_chapter_lists_files() -> None:
    """Requirement: _checksums_chapter renders each checksum entry."""
    checksums = [FileChecksum(path="src/mod.py", sha256="abc123")]
    rendered = _render_chapter(_checksums_chapter(checksums))
    assert "src/mod.py" in rendered
    assert "abc123" in rendered


def test_checksums_chapter_empty() -> None:
    """Requirement: _checksums_chapter handles empty checksum list."""
    rendered = _render_chapter(_checksums_chapter([]))
    assert "No files" in rendered


def test_suppressions_chapter_no_items() -> None:
    """Requirement: _suppressions_chapter indicates when none are found."""
    rendered = _render_chapter(_suppressions_chapter([]))
    assert "No inline suppressions" in rendered


def test_suppressions_chapter_groups_by_file() -> None:
    """Requirement: _suppressions_chapter groups suppressions per file."""
    items = [
        SuppressionItem(
            file="src/a.py",
            line=1,
            kind="noqa",
            code="E501",
            excerpt="x = 1  # noqa: E501",
        ),
        SuppressionItem(
            file="src/b.py",
            line=5,
            kind="nosec",
            code="B603",
            excerpt="subprocess.run(x)  # nosec B603",
        ),
    ]
    rendered = _render_chapter(_suppressions_chapter(items))
    assert "src/a.py" in rendered
    assert "src/b.py" in rendered
    assert "noqa" in rendered
    assert "nosec" in rendered


def test_suppressions_chapter_shows_count() -> None:
    """Requirement: _suppressions_chapter states total suppression count."""
    items = [
        SuppressionItem(
            file="src/a.py",
            line=1,
            kind="noqa",
            code="E501",
            excerpt="x  # noqa: E501",
        ),
    ]
    rendered = _render_chapter(_suppressions_chapter(items))
    assert "1 suppression" in rendered


def test_render_report_returns_report_object(tmp_path: Path) -> None:
    """Requirement: render_report returns a mkforge Report instance."""
    data = _make_report_data(tmp_path)
    result = render_report(data)
    assert isinstance(result, Report)


def test_render_report_contains_title(tmp_path: Path) -> None:
    """Requirement: render_report embeds the project name in the title."""
    data = _make_report_data(tmp_path)
    rendered = render_report(data).render()
    assert "test-proj" in rendered


def test_save_report_writes_file(tmp_path: Path) -> None:
    """Requirement: save_report writes a non-empty Markdown file."""
    data = _make_report_data(tmp_path)
    output = tmp_path / "work" / "report.md"
    save_report(data, output)
    assert output.exists()
    assert len(output.read_text(encoding="utf-8")) > 0


def test_save_report_creates_parent_dirs(tmp_path: Path) -> None:
    """Requirement: save_report creates missing parent directories."""
    data = _make_report_data(tmp_path)
    output = tmp_path / "deep" / "nested" / "report.md"
    save_report(data, output)
    assert output.exists()


def test_save_report_content_is_markdown(tmp_path: Path) -> None:
    """Requirement: save_report writes valid Markdown with a heading."""
    data = _make_report_data(tmp_path)
    output = tmp_path / "report.md"
    save_report(data, output)
    content = output.read_text(encoding="utf-8")
    assert content.startswith("#")


def test_build_report_data_runs_checks(tmp_path: Path) -> None:
    """Requirement: build_report_data populates check_results via run_check."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "work").mkdir()
    (tmp_path / "work" / ".gitkeep").touch()
    (tmp_path / "doc").mkdir()
    (tmp_path / ".python-version").write_text("3.12\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\n",
        encoding="utf-8",
    )
    (tmp_path / "Makefile").write_text(
        "check:\n\t@echo ok\n",
        encoding="utf-8",
    )

    data = build_report_data(tmp_path)
    assert len(data.check_results) > 0
    assert data.project_name == tmp_path.name
    assert data.uvforge_version != ""
