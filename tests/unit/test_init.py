"""Unit tests for uvforge.init."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uvforge.init import ConflictError, _copy_scripts, run_init
from uvforge.models import ProjectContext
from uvforge.uv_runner import UvNotFoundError


def _ctx(
    tmp_path: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    no_git: bool = True,
) -> ProjectContext:
    """Build a minimal ProjectContext for init tests.

    Args:
        tmp_path: Pytest temporary directory.
        dry_run: Enable dry-run mode.
        force: Enable force mode.
        no_git: Skip git initialisation (default True).

    Returns:
        Configured ProjectContext.
    """
    return ProjectContext(
        project_name="my-lib",
        package_name="my_lib",
        python_version="3.12",
        project_dir=tmp_path / "my-lib",
        dry_run=dry_run,
        force=force,
        no_git=no_git,
    )


def _patch_uv_runner() -> MagicMock:
    """Return a MagicMock that patches uv_runner calls in uvforge.init.

    Returns:
        MagicMock context that can be used as a patch target string.
    """
    return MagicMock(return_value=None)


def test_run_init_raises_when_uv_missing(tmp_path: Path) -> None:
    """Requirement: run_init must raise UvNotFoundError when uv is absent."""
    ctx = _ctx(tmp_path)
    with (
        patch(
            "uvforge.init.check_uv_available",
            side_effect=UvNotFoundError("no uv"),
        ),
        pytest.raises(UvNotFoundError),
    ):
        run_init(ctx)


def test_run_init_raises_conflict_when_pyproject_exists(
    tmp_path: Path,
) -> None:
    """Requirement: run_init must raise ConflictError for existing project."""
    ctx = _ctx(tmp_path)
    ctx.project_dir.mkdir(parents=True)
    (ctx.project_dir / "pyproject.toml").write_text("[project]\nname='x'\n")
    with (
        patch("uvforge.init.check_uv_available"),
        pytest.raises(ConflictError),
    ):
        run_init(ctx)


def test_run_init_force_overwrites_existing_project(tmp_path: Path) -> None:
    """Requirement: run_init with force=True must proceed despite conflict."""
    ctx = _ctx(tmp_path, force=True)
    ctx.project_dir.mkdir(parents=True)
    (ctx.project_dir / "pyproject.toml").write_text("[project]\nname='x'\n")
    with (
        patch("uvforge.init.check_uv_available"),
        patch("uvforge.init.uv_add_dev_deps"),
        patch("uvforge.init.uv_sync"),
    ):
        run_init(ctx)
    assert (ctx.project_dir / "Makefile").exists()


def test_run_init_dry_run_writes_nothing(tmp_path: Path) -> None:
    """Requirement: run_init with dry_run=True must not write to disk."""
    ctx = _ctx(tmp_path, dry_run=True)
    with patch("uvforge.init.check_uv_available"):
        run_init(ctx)
    assert not ctx.project_dir.exists()


def test_run_init_creates_project_structure(tmp_path: Path) -> None:
    """Requirement: run_init must create the full project structure."""
    ctx = _ctx(tmp_path)
    with (
        patch("uvforge.init.check_uv_available"),
        patch("uvforge.init.uv_add_dev_deps"),
        patch("uvforge.init.uv_sync"),
    ):
        run_init(ctx)
    assert (ctx.project_dir / "src" / "my_lib").is_dir()
    assert (ctx.project_dir / "tests").is_dir()
    assert (ctx.project_dir / "scripts").is_dir()
    assert (ctx.project_dir / "work" / ".gitkeep").exists()


def test_run_init_writes_pyproject_toml(tmp_path: Path) -> None:
    """Requirement: run_init must write a rendered pyproject.toml."""
    ctx = _ctx(tmp_path)
    with (
        patch("uvforge.init.check_uv_available"),
        patch("uvforge.init.uv_add_dev_deps"),
        patch("uvforge.init.uv_sync"),
    ):
        run_init(ctx)
    pyproject = ctx.project_dir / "pyproject.toml"
    assert pyproject.exists()
    assert "my-lib" in pyproject.read_text()


def test_run_init_writes_makefile(tmp_path: Path) -> None:
    """Requirement: run_init must write a Makefile with pipeline targets."""
    ctx = _ctx(tmp_path)
    with (
        patch("uvforge.init.check_uv_available"),
        patch("uvforge.init.uv_add_dev_deps"),
        patch("uvforge.init.uv_sync"),
    ):
        run_init(ctx)
    makefile = ctx.project_dir / "Makefile"
    assert makefile.exists()
    assert "check:" in makefile.read_text()


def test_run_init_copies_all_scripts(tmp_path: Path) -> None:
    """Requirement: run_init must copy all embedded scripts into scripts/."""
    ctx = _ctx(tmp_path)
    with (
        patch("uvforge.init.check_uv_available"),
        patch("uvforge.init.uv_add_dev_deps"),
        patch("uvforge.init.uv_sync"),
    ):
        run_init(ctx)
    scripts_dir = ctx.project_dir / "scripts"
    assert (scripts_dir / "check.sh").exists()
    assert (scripts_dir / "publish.sh").exists()
    assert (scripts_dir / "check_docstrings.py").exists()
    assert (scripts_dir / "code_metrics.py").exists()
    assert (scripts_dir / "security_deps.sh").exists()


def test_run_init_writes_python_version_file(tmp_path: Path) -> None:
    """Requirement: run_init must write .python-version with target version."""
    ctx = _ctx(tmp_path)
    with (
        patch("uvforge.init.check_uv_available"),
        patch("uvforge.init.uv_add_dev_deps"),
        patch("uvforge.init.uv_sync"),
    ):
        run_init(ctx)
    version_file = ctx.project_dir / ".python-version"
    assert version_file.exists()
    assert "3.12" in version_file.read_text()


def test_copy_scripts_dry_run_skips_copy(tmp_path: Path) -> None:
    """Requirement: _copy_scripts must skip writes when dry_run is True."""
    ctx = ProjectContext(
        project_name="my-lib",
        package_name="my_lib",
        python_version="3.12",
        project_dir=tmp_path / "my-lib",
        dry_run=True,
    )
    (ctx.project_dir / "scripts").mkdir(parents=True)
    _copy_scripts(ctx)
    scripts = list((ctx.project_dir / "scripts").iterdir())
    assert scripts == []


def test_run_init_calls_git_when_no_git_false(tmp_path: Path) -> None:
    """Requirement: run_init must run git init/add/commit when no_git=False."""
    ctx = ProjectContext(
        project_name="my-lib",
        package_name="my_lib",
        python_version="3.12",
        project_dir=tmp_path / "my-lib",
        no_git=False,
    )
    with (
        patch("uvforge.init.check_uv_available"),
        patch("uvforge.init.uv_add_dev_deps"),
        patch("uvforge.init.uv_sync"),
        patch("uvforge.init.git_init") as mock_git_init,
        patch("uvforge.init.git_add_all") as mock_git_add,
        patch("uvforge.init.git_commit") as mock_git_commit,
    ):
        run_init(ctx)
    mock_git_init.assert_called_once()
    mock_git_add.assert_called_once()
    mock_git_commit.assert_called_once()
