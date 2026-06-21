"""Project version bumping helpers."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from yggtools.quality.checks.version import (
    _package_dir,
    _read_pyproject_identity,
)
from yggtools.uv import CommandError, run_uv

_SEMVER_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)$",
)
_SECTION_PATTERN = re.compile(r"^\s*\[[^\]]+\]\s*$")
_VERSION_LINE_PATTERN = re.compile(
    r"^(?P<prefix>\s*version\s*=\s*)"
    r"(?P<quote>[\"'])"
    r"(?P<version>[^\"']+)"
    r"(?P=quote)"
    r"(?P<suffix>\s*(?:#.*)?)$",
)
_INIT_VERSION_PATTERN = re.compile(
    r"^(?P<prefix>\s*__version__\s*=\s*)"
    r"(?P<quote>[\"'])"
    r"(?P<version>[^\"']+)"
    r"(?P=quote)"
    r"(?P<suffix>\s*(?:#.*)?)$",
    re.MULTILINE,
)
_PACKAGE_HEADER_PATTERN = re.compile(r"^\s*\[\[package\]\]\s*$")
_NAME_LINE_PATTERN = re.compile(r"^\s*name\s*=\s*[\"'](?P<name>[^\"']+)[\"']")
_PATCH_LEVEL = 1
_MINOR_LEVEL = 2
_MAJOR_LEVEL = 3


class VersionError(RuntimeError):
    """Raised when the project version cannot be bumped safely."""


@dataclass(frozen=True)
class VersionUpdate:
    """Summary of a version update.

    Attributes:
        project_name: Distribution name from pyproject.toml.
        old_version: Version before the bump.
        new_version: Version after the bump.
        files: Files updated by the bump.
    """

    project_name: str
    old_version: str
    new_version: str
    files: tuple[Path, ...]


def bump_semver(version: str, level: int) -> str:
    """Increase a stable SemVer version by numeric release level.

    Args:
        version: Stable ``MAJOR.MINOR.PATCH`` version.
        level: 1 for patch, 2 for minor, 3 for major.

    Returns:
        Increased SemVer version.

    Raises:
        VersionError: If level or version is unsupported.
    """
    if level not in {_PATCH_LEVEL, _MINOR_LEVEL, _MAJOR_LEVEL}:
        msg = "Level must be 1 (patch), 2 (minor), or 3 (major)."
        raise VersionError(msg)
    match = _SEMVER_PATTERN.fullmatch(version)
    if match is None:
        msg = (
            "Only stable SemVer versions are supported "
            f"(MAJOR.MINOR.PATCH), got {version!r}."
        )
        raise VersionError(msg)
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    if level == _PATCH_LEVEL:
        return f"{major}.{minor}.{patch + 1}"
    if level == _MINOR_LEVEL:
        return f"{major}.{minor + 1}.0"
    return f"{major + 1}.0.0"


def increase_project_version(
    project_dir: Path,
    level: int,
    *,
    update_lock: bool = True,
) -> VersionUpdate:
    """Increase the project version across all managed artifacts.

    Args:
        project_dir: Project root directory.
        level: 1 for patch, 2 for minor, 3 for major.
        update_lock: Run ``uv lock`` after text updates.

    Returns:
        VersionUpdate summary.

    Raises:
        VersionError: If the project version cannot be updated safely.
    """
    pyproject = project_dir / "pyproject.toml"
    project_name, old_version = _read_pyproject_identity(pyproject)
    if not project_name or old_version is None:
        msg = "pyproject.toml must define [project].name and version."
        raise VersionError(msg)

    new_version = bump_semver(old_version, level)
    package_init = (
        project_dir / "src" / _package_dir(project_name) / "__init__.py"
    )
    lock_file = project_dir / "uv.lock"
    updated_files = (
        pyproject,
        package_init,
        lock_file,
    )

    _write_replaced(pyproject, _replace_project_version, new_version)
    _write_replaced(package_init, _replace_init_version, new_version)
    _write_replaced(
        lock_file,
        lambda content, version: _replace_lock_version(
            content,
            project_name,
            version,
        ),
        new_version,
    )
    if update_lock:
        try:
            run_uv(["lock"], cwd=project_dir, check=True)
        except CommandError as exc:
            msg = f"uv lock failed after version update: {exc}"
            raise VersionError(msg) from exc

    return VersionUpdate(
        project_name=project_name,
        old_version=old_version,
        new_version=new_version,
        files=updated_files,
    )


def _write_replaced(
    path: Path,
    replace: Callable[[str, str], str],
    new_version: str,
) -> None:
    """Replace a version in one file.

    Args:
        path: File to update.
        replace: Replacement function.
        new_version: New version string.

    Raises:
        VersionError: If the file is absent or the version is not found.
    """
    if not path.exists():
        msg = f"Version artifact not found: {path}"
        raise VersionError(msg)
    content = path.read_text(encoding="utf-8")
    updated = replace(content, new_version)
    path.write_text(updated, encoding="utf-8")


def _replace_project_version(content: str, new_version: str) -> str:
    """Replace ``[project].version`` in pyproject.toml content.

    Args:
        content: Original file content.
        new_version: New version string.

    Returns:
        Updated content.

    Raises:
        VersionError: If no project version line is found.
    """
    lines = content.splitlines(keepends=True)
    in_project = False
    for index, line in enumerate(lines):
        bare_line = line.rstrip("\r\n")
        if bare_line.strip() == "[project]":
            in_project = True
            continue
        if in_project and _SECTION_PATTERN.match(bare_line):
            break
        if not in_project:
            continue
        updated = _replace_version_line(bare_line, new_version)
        if updated is not None:
            lines[index] = updated + _line_ending(line)
            return "".join(lines)
    msg = "Could not find [project].version in pyproject.toml."
    raise VersionError(msg)


def _replace_init_version(content: str, new_version: str) -> str:
    """Replace ``__version__`` in package initializer content.

    Args:
        content: Original file content.
        new_version: New version string.

    Returns:
        Updated content.

    Raises:
        VersionError: If no ``__version__`` assignment is found.
    """
    updated, count = _INIT_VERSION_PATTERN.subn(
        lambda match: (
            f"{match.group('prefix')}{match.group('quote')}"
            f"{new_version}{match.group('quote')}{match.group('suffix')}"
        ),
        content,
        count=1,
    )
    if count == 0:
        msg = "Could not find __version__ in package __init__.py."
        raise VersionError(msg)
    return updated


def _replace_lock_version(
    content: str,
    project_name: str,
    new_version: str,
) -> str:
    """Replace the current project package version in uv.lock content.

    Args:
        content: Original uv.lock content.
        project_name: Distribution name to update.
        new_version: New version string.

    Returns:
        Updated content.

    Raises:
        VersionError: If no package block matches.
    """
    lines = content.splitlines(keepends=True)
    blocks = _package_blocks(lines)
    for start, end in blocks:
        block = lines[start:end]
        if not _is_project_block(block, project_name):
            continue
        for offset, line in enumerate(block):
            bare_line = line.rstrip("\r\n")
            updated = _replace_version_line(bare_line, new_version)
            if updated is not None:
                lines[start + offset] = updated + _line_ending(line)
                return "".join(lines)
    msg = f"Could not find package {project_name!r} in uv.lock."
    raise VersionError(msg)


def _replace_version_line(line: str, new_version: str) -> str | None:
    """Replace a TOML version assignment line.

    Args:
        line: One line without line ending.
        new_version: New version string.

    Returns:
        Updated line, or None when the line is not a version assignment.
    """
    match = _VERSION_LINE_PATTERN.match(line)
    if match is None:
        return None
    return (
        f"{match.group('prefix')}{match.group('quote')}"
        f"{new_version}{match.group('quote')}{match.group('suffix')}"
    )


def _package_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return start/end offsets for every uv.lock package block.

    Args:
        lines: uv.lock lines.

    Returns:
        List of half-open ``(start, end)`` line ranges.
    """
    starts = [
        index
        for index, line in enumerate(lines)
        if _PACKAGE_HEADER_PATTERN.match(line.rstrip("\r\n"))
    ]
    return [
        (start, starts[index + 1] if index + 1 < len(starts) else len(lines))
        for index, start in enumerate(starts)
    ]


def _is_project_block(block: list[str], project_name: str) -> bool:
    """Return whether a uv.lock package block matches the current project.

    Args:
        block: Lines from one ``[[package]]`` block.
        project_name: Expected package name.

    Returns:
        True when the package name matches.
    """
    for line in block:
        bare_line = line.rstrip("\r\n")
        name_match = _NAME_LINE_PATTERN.match(bare_line)
        if name_match is not None and name_match.group("name") == project_name:
            return True
    return False


def _line_ending(line: str) -> str:
    """Return the original line ending for a split line.

    Args:
        line: Original line.

    Returns:
        Original line ending, or an empty string.
    """
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""
