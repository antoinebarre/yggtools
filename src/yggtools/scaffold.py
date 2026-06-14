"""Filesystem scaffold operations for yggtools project initialisation."""

from __future__ import annotations

import shutil
import stat
from pathlib import Path

from yggtools.models import ProjectContext

_GITKEEP = ".gitkeep"

_SMOKE_TEST_TEMPLATE = '''\
"""Tests for {package_name}."""


def test_{package_name}_imports() -> None:
    """Requirement: the package must be importable after scaffolding."""
    import {package_name}  # noqa: F401
'''


def scaffold_project(ctx: ProjectContext) -> list[Path]:
    """Create the full directory and file structure for a new project.

    Creates ``src/<package>/``, ``tests/``, ``scripts/``, ``work/``,
    and ``doc/`` directories, then writes stub files into each.  All
    operations are skipped when ``ctx.dry_run`` is True.

    Args:
        ctx: Project context carrying name, version, and flags.

    Returns:
        List of paths that were created (or would be created on dry-run).
    """
    created: list[Path] = []
    created += _create_directories(ctx)
    created += _write_stub_files(ctx)
    return created


def _create_directories(ctx: ProjectContext) -> list[Path]:
    """Create the required project directories.

    Args:
        ctx: Project context.

    Returns:
        List of directory paths created.
    """
    dirs = [
        ctx.project_dir / "src" / ctx.package_name,
        ctx.project_dir / "tests",
        ctx.project_dir / "scripts",
        ctx.project_dir / "work",
        ctx.project_dir / "doc",
    ]
    created = []
    for directory in dirs:
        if not ctx.dry_run:
            directory.mkdir(parents=True, exist_ok=True)
        created.append(directory)
    return created


def _write_stub_files(ctx: ProjectContext) -> list[Path]:
    """Write the initial stub files into the scaffolded directories.

    Args:
        ctx: Project context.

    Returns:
        List of file paths written.
    """
    stubs: list[tuple[Path, str, bool]] = [
        (
            ctx.project_dir / "src" / ctx.package_name / "__init__.py",
            f'"""{ctx.project_name}."""\n',
            False,
        ),
        (ctx.project_dir / "src" / ctx.package_name / "py.typed", "", False),
        (
            ctx.project_dir / "tests" / "__init__.py",
            '"""Test suite."""\n',
            False,
        ),
        (
            ctx.project_dir / "tests" / f"test_{ctx.package_name}.py",
            _SMOKE_TEST_TEMPLATE.format(package_name=ctx.package_name),
            False,
        ),
        (
            ctx.project_dir / "scripts" / "__init__.py",
            '"""Quality pipeline scripts."""\n',
            False,
        ),
        (ctx.project_dir / "work" / _GITKEEP, "", False),
        (ctx.project_dir / "doc" / _GITKEEP, "", False),
    ]
    created = []
    for path, content, executable in stubs:
        write_file(path, content, executable=executable, dry_run=ctx.dry_run)
        created.append(path)
    return created


def write_file(
    path: Path,
    content: str,
    *,
    executable: bool = False,
    dry_run: bool = False,
) -> None:
    """Write text content to a file, creating parent directories as needed.

    Args:
        path: Destination file path.
        content: Text content to write (UTF-8).
        executable: When True, set the executable bit on the file.
        dry_run: When True, skip the actual write.
    """
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        current = path.stat().st_mode
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def copy_script(
    source: Path,
    destination: Path,
    *,
    dry_run: bool = False,
) -> None:
    """Copy a script file and set the executable bit.

    Args:
        source: Path to the source script.
        destination: Destination path inside the project's ``scripts/`` dir.
        dry_run: When True, skip the actual copy.
    """
    if dry_run:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    current = destination.stat().st_mode
    destination.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
