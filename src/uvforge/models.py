"""Shared data models for uvforge scaffold operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass(frozen=True)
class SuppressionItem:
    """A single inline suppression comment found in a source file.

    Attributes:
        file: Path of the source file relative to the project root.
        line: 1-based line number where the suppression appears.
        kind: Suppression type: ``noqa``, ``nosec``, ``type: ignore``,
            or ``pragma: no cover``.
        code: Specific rule code suppressed, e.g. ``E501``, or empty
            string when no code is given.
        excerpt: The source line text, stripped of leading whitespace.
    """

    file: str
    line: int
    kind: str
    code: str
    excerpt: str


@dataclass(frozen=True)
class FileChecksum:
    """SHA-256 checksum for a single file in the audited project.

    Attributes:
        path: File path relative to the project root.
        sha256: Lowercase hexadecimal SHA-256 digest.
    """

    path: str
    sha256: str


@dataclass
class ReportData:
    """Aggregated data produced by a single uvforge check run.

    Attributes:
        project_name: Human-readable name of the audited project.
        project_dir: Absolute path to the audited project root.
        uvforge_version: Version string of the running uvforge tool.
        generated_at: UTC timestamp of report generation.
        check_results: Ordered list of structural check outcomes.
        checksums: SHA-256 digests for all audited source files.
        suppressions: All inline suppression comments found in sources.
    """

    project_name: str
    project_dir: Path
    uvforge_version: str
    generated_at: datetime
    check_results: list[CheckResult] = field(default_factory=list)
    checksums: list[FileChecksum] = field(default_factory=list)
    suppressions: list[SuppressionItem] = field(default_factory=list)


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
