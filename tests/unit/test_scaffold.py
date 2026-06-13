"""Unit tests for uvforge.scaffold."""

from __future__ import annotations

import stat
from pathlib import Path

from uvforge.models import ProjectContext
from uvforge.scaffold import copy_script, scaffold_project, write_file


def _ctx(tmp_path: Path, *, dry_run: bool = False) -> ProjectContext:
    """Build a minimal ProjectContext for test use.

    Args:
        tmp_path: Pytest temporary directory.
        dry_run: Whether to enable dry-run mode.

    Returns:
        Configured ProjectContext.
    """
    return ProjectContext(
        project_name="my-lib",
        package_name="my_lib",
        python_version="3.12",
        project_dir=tmp_path / "my-lib",
        dry_run=dry_run,
    )


def test_scaffold_creates_src_directory(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create src/<package_name>/."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "src" / "my_lib").is_dir()


def test_scaffold_creates_tests_directory(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create tests/."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "tests").is_dir()


def test_scaffold_creates_scripts_directory(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create scripts/."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "scripts").is_dir()


def test_scaffold_creates_work_directory(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create work/."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "work").is_dir()


def test_scaffold_creates_doc_directory(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create doc/."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "doc").is_dir()


def test_scaffold_creates_work_gitkeep(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create work/.gitkeep."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "work" / ".gitkeep").exists()


def test_scaffold_creates_package_init(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create src/<package>/__init__.py."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "src" / "my_lib" / "__init__.py").exists()


def test_scaffold_creates_py_typed(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create src/<package>/py.typed."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "src" / "my_lib" / "py.typed").exists()


def test_scaffold_creates_smoke_test(tmp_path: Path) -> None:
    """Requirement: scaffold_project must create tests/test_<package>.py."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    assert (ctx.project_dir / "tests" / "test_my_lib.py").exists()


def test_scaffold_smoke_test_contains_package_name(tmp_path: Path) -> None:
    """Requirement: the smoke test file must reference the package name."""
    ctx = _ctx(tmp_path)
    scaffold_project(ctx)
    content = (ctx.project_dir / "tests" / "test_my_lib.py").read_text()
    assert "my_lib" in content


def test_scaffold_dry_run_creates_nothing(tmp_path: Path) -> None:
    """Requirement: dry_run=True must not write any files to disk."""
    ctx = _ctx(tmp_path, dry_run=True)
    scaffold_project(ctx)
    assert not ctx.project_dir.exists()


def test_write_file_creates_content(tmp_path: Path) -> None:
    """Requirement: write_file must create a file with the given content."""
    path = tmp_path / "sub" / "file.txt"
    write_file(path, "hello")
    assert path.read_text() == "hello"


def test_write_file_creates_parent_directories(tmp_path: Path) -> None:
    """Requirement: write_file must create parent directories as needed."""
    path = tmp_path / "a" / "b" / "c.txt"
    write_file(path, "x")
    assert path.exists()


def test_write_file_sets_executable_bit(tmp_path: Path) -> None:
    """Requirement: write_file with executable=True must set the exec bit."""
    path = tmp_path / "script.sh"
    write_file(path, "#!/bin/bash", executable=True)
    mode = path.stat().st_mode
    assert mode & stat.S_IXUSR


def test_write_file_dry_run_skips_write(tmp_path: Path) -> None:
    """Requirement: write_file with dry_run=True must not create the file."""
    path = tmp_path / "noop.txt"
    write_file(path, "should not exist", dry_run=True)
    assert not path.exists()


def test_copy_script_sets_executable(tmp_path: Path) -> None:
    """Requirement: copy_script must set the executable bit on dest."""
    source = tmp_path / "source.sh"
    source.write_text("#!/bin/bash\necho hi")
    dest = tmp_path / "dest" / "dest.sh"
    copy_script(source, dest)
    mode = dest.stat().st_mode
    assert mode & stat.S_IXUSR


def test_copy_script_preserves_content(tmp_path: Path) -> None:
    """Requirement: copy_script must copy file content unchanged."""
    source = tmp_path / "src.sh"
    source.write_text("#!/bin/bash\necho hello")
    dest = tmp_path / "dst.sh"
    copy_script(source, dest)
    assert dest.read_text() == source.read_text()


def test_copy_script_dry_run_skips_copy(tmp_path: Path) -> None:
    """Requirement: copy_script with dry_run=True must not create dest."""
    source = tmp_path / "src.sh"
    source.write_text("#!/bin/bash")
    dest = tmp_path / "dst.sh"
    copy_script(source, dest, dry_run=True)
    assert not dest.exists()
