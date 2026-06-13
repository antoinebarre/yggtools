"""Unit tests for uvforge.suppressions."""

from __future__ import annotations

from pathlib import Path

from uvforge.suppressions import (
    _extract_suppressions,
    _scan_file,
    scan_suppressions,
)


def _write(tmp_path: Path, rel: str, content: str) -> Path:
    """Write content to a file relative to tmp_path and return its path.

    Args:
        tmp_path: Pytest temporary directory.
        rel: Relative path within tmp_path.
        content: File content to write.

    Returns:
        Absolute path of the written file.
    """
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_extract_noqa_with_code() -> None:
    """Requirement: noqa with code is captured correctly."""
    items = _extract_suppressions("f.py", 5, "x = 1  # noqa: E501")
    assert len(items) == 1
    assert items[0].kind == "noqa"
    assert items[0].code == "E501"
    assert items[0].line == 5


def test_extract_noqa_bare() -> None:
    """Requirement: bare noqa without code is captured."""
    items = _extract_suppressions("f.py", 1, "x = 1  # noqa")
    assert len(items) == 1
    assert items[0].kind == "noqa"
    assert items[0].code == ""


def test_extract_nosec_with_code() -> None:
    """Requirement: nosec with code is captured correctly."""
    items = _extract_suppressions("f.py", 3, "subprocess.run(x)  # nosec B603")
    assert len(items) == 1
    assert items[0].kind == "nosec"
    assert items[0].code == "B603"


def test_extract_nosec_bare() -> None:
    """Requirement: bare nosec without code is captured."""
    items = _extract_suppressions("f.py", 2, "x = y  # nosec")
    assert len(items) == 1
    assert items[0].kind == "nosec"
    assert items[0].code == ""


def test_extract_type_ignore_with_code() -> None:
    """Requirement: type: ignore with bracketed code is captured."""
    items = _extract_suppressions(
        "f.py",
        7,
        "x = y  # type: ignore[attr-defined]",
    )
    assert len(items) == 1
    assert items[0].kind == "type: ignore"
    assert items[0].code == "attr-defined"


def test_extract_type_ignore_bare() -> None:
    """Requirement: bare type: ignore is captured."""
    items = _extract_suppressions("f.py", 8, "x = y  # type: ignore")
    assert len(items) == 1
    assert items[0].kind == "type: ignore"
    assert items[0].code == ""


def test_extract_pragma_no_cover() -> None:
    """Requirement: pragma: no cover is captured."""
    items = _extract_suppressions(
        "f.py",
        10,
        "def main():  # pragma: no cover",
    )
    assert len(items) == 1
    assert items[0].kind == "pragma: no cover"
    assert items[0].code == ""


def test_extract_multiple_on_same_line() -> None:
    """Requirement: multiple suppression kinds on one line are all found."""
    items = _extract_suppressions(
        "f.py",
        1,
        "x = y  # noqa: E501  # nosec B603",
    )
    kinds = {i.kind for i in items}
    assert "noqa" in kinds
    assert "nosec" in kinds


def test_extract_no_suppression() -> None:
    """Requirement: lines without suppressions return an empty list."""
    items = _extract_suppressions("f.py", 1, "x = 1 + 2")
    assert items == []


def test_extract_deduplicates_same_kind_code() -> None:
    """Requirement: identical kind/code pairs on one line are deduplicated."""
    items = _extract_suppressions(
        "f.py",
        1,
        "x  # noqa: E501  # noqa: E501",
    )
    noqa_items = [i for i in items if i.kind == "noqa" and i.code == "E501"]
    assert len(noqa_items) == 1


def test_extract_stores_excerpt() -> None:
    """Requirement: excerpt stores the stripped source line text."""
    items = _extract_suppressions("f.py", 1, "   x = 1  # noqa: E501")
    assert items[0].excerpt == "x = 1  # noqa: E501"


def test_extract_suppressions_deduplicates_across_patterns() -> None:
    """Requirement: duplicate kind/code pairs across patterns are skipped."""
    items = _extract_suppressions("f.py", 1, "x  # noqa: E501")
    noqa_e501 = [i for i in items if i.kind == "noqa" and i.code == "E501"]
    assert len(noqa_e501) == 1


def test_scan_file_skips_unreadable_file(tmp_path: Path) -> None:
    """Requirement: _scan_file returns empty list for a missing file."""
    path = tmp_path / "ghost.py"
    result = _scan_file(path, tmp_path)
    assert result == []


def test_scan_suppressions_finds_items(tmp_path: Path) -> None:
    """Requirement: suppressions are found across multiple source files."""
    _write(tmp_path, "src/a.py", "x = 1  # noqa: E501\ny = 2\n")
    _write(tmp_path, "src/b.py", "z = 3  # nosec B603\n")
    items = scan_suppressions([tmp_path / "src"], tmp_path)
    assert len(items) == 2
    files = {i.file for i in items}
    assert "src/a.py" in files
    assert "src/b.py" in files


def test_scan_suppressions_sorted_by_file_then_line(tmp_path: Path) -> None:
    """Requirement: results are sorted by file path then line number."""
    _write(
        tmp_path,
        "src/z.py",
        "a = 1  # noqa\nb = 2  # nosec\n",
    )
    _write(tmp_path, "src/a.py", "c = 3  # noqa\n")
    items = scan_suppressions([tmp_path / "src"], tmp_path)
    assert items[0].file == "src/a.py"
    assert items[1].file == "src/z.py"
    assert items[1].line < items[2].line


def test_scan_suppressions_empty_dir(tmp_path: Path) -> None:
    """Requirement: empty directory with no .py files returns empty list."""
    src = tmp_path / "src"
    src.mkdir()
    items = scan_suppressions([src], tmp_path)
    assert items == []


def test_scan_suppressions_missing_dir(tmp_path: Path) -> None:
    """Requirement: non-existent directories are silently skipped."""
    items = scan_suppressions([tmp_path / "nonexistent"], tmp_path)
    assert items == []


def test_scan_suppressions_relative_path(tmp_path: Path) -> None:
    """Requirement: file paths in results are relative to project_root."""
    _write(tmp_path, "src/pkg/mod.py", "x = 1  # noqa: E501\n")
    items = scan_suppressions([tmp_path / "src"], tmp_path)
    assert items[0].file == "src/pkg/mod.py"


def test_scan_suppressions_multiple_dirs(tmp_path: Path) -> None:
    """Requirement: all provided directories are scanned."""
    _write(tmp_path, "src/a.py", "x = 1  # noqa\n")
    _write(tmp_path, "tests/b.py", "y = 2  # nosec\n")
    items = scan_suppressions(
        [tmp_path / "src", tmp_path / "tests"],
        tmp_path,
    )
    assert len(items) == 2
