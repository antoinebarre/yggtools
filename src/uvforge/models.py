"""Shared data models for uvforge scaffold operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    """Complete context for a uvforge project initialisation.

    Attributes:
        project_name: Human-readable project name, e.g. ``my-lib``.
        package_name: Python import name derived from project_name,
            e.g. ``my_lib``.
        python_version: Target Python version string, e.g. ``3.12``.
        project_dir: Absolute path to the project root directory.
        dry_run: When True, log actions without writing to disk.
        force: When True, overwrite existing files without confirmation.
        no_git: When True, skip git initialisation.
    """

    project_name: str
    package_name: str
    python_version: str
    project_dir: Path
    dry_run: bool = False
    force: bool = False
    no_git: bool = False


@dataclass(frozen=True)
class CheckResult:
    """Result of a single uvforge structural check.

    Attributes:
        label: Human-readable description of the check.
        passed: Whether the check succeeded.
        detail: Optional extra information shown on failure.
    """

    label: str
    passed: bool
    detail: str = ""


def make_package_name(project_name: str) -> str:
    """Derive the Python package name from a project name.

    Replaces hyphens with underscores and lowercases the result so
    the name is a valid Python identifier.

    Args:
        project_name: The raw project name, e.g. ``my-lib``.

    Returns:
        A valid Python package name, e.g. ``my_lib``.
    """
    return project_name.replace("-", "_").lower()
