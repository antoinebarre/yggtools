"""Quality check: package version consistency."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from yggtools.quality.runner import CheckResult, register

_INIT_VERSION_PATTERN = re.compile(
    r"^__version__\s*=\s*[\"'](?P<version>[^\"']+)[\"']",
    re.MULTILINE,
)


@dataclass(frozen=True)
class VersionArtifact:
    """Version value extracted from one project artifact.

    Attributes:
        name: Stable artifact identifier.
        path: Artifact path.
        version: Extracted version string, or None when unavailable.
        required: Whether a missing version should fail the check.
    """

    name: str
    path: Path
    version: str | None
    required: bool = True


@register("version-consistency")
def check_version_consistency(project_dir: Path) -> CheckResult:
    """Check that package version artifacts agree.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult describing missing or conflicting versions.
    """
    artifacts = _collect_version_artifacts(project_dir)
    missing = [a for a in artifacts if a.required and a.version is None]
    versions = {a.version for a in artifacts if a.version is not None}
    passed = not missing and len(versions) <= 1

    if passed:
        version = next(iter(versions), "unknown")
        detail = f"{len(artifacts)} artifact(s), version {version}"
    else:
        issue_count = len(missing) + max(len(versions) - 1, 0)
        detail = f"{issue_count} version consistency issue(s)"

    return CheckResult(
        name="version-consistency",
        passed=passed,
        detail=detail,
        metadata={
            "artifacts": [
                {
                    "name": artifact.name,
                    "path": _relative_to(project_dir, artifact.path),
                    "version": artifact.version,
                    "required": artifact.required,
                }
                for artifact in artifacts
            ],
            "missing": [artifact.name for artifact in missing],
            "versions": sorted(versions),
        },
    )


def _collect_version_artifacts(project_dir: Path) -> list[VersionArtifact]:
    """Read all known package version artifacts.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        Version artifacts extracted from project files.
    """
    pyproject = project_dir / "pyproject.toml"
    project_name, project_version = _read_pyproject_identity(pyproject)
    package_dir = _package_dir(project_name)
    return [
        VersionArtifact(
            name="pyproject.project.version",
            path=pyproject,
            version=project_version,
        ),
        VersionArtifact(
            name="package.__version__",
            path=project_dir / "src" / package_dir / "__init__.py",
            version=_read_init_version(
                project_dir / "src" / package_dir / "__init__.py",
            ),
        ),
        VersionArtifact(
            name="uv.lock.package.version",
            path=project_dir / "uv.lock",
            version=_read_lock_version(project_dir / "uv.lock", project_name),
        ),
    ]


def _read_pyproject_identity(path: Path) -> tuple[str, str | None]:
    """Read project name and version from pyproject.toml.

    Args:
        path: pyproject.toml path.

    Returns:
        Tuple of normalized project name and version.
    """
    if not path.exists():
        return "", None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    if not isinstance(project, dict):
        return "", None
    name = project.get("name")
    version = project.get("version")
    return (
        str(name) if isinstance(name, str) else "",
        str(version) if isinstance(version, str) else None,
    )


def _read_init_version(path: Path) -> str | None:
    """Read ``__version__`` from a package ``__init__.py``.

    Args:
        path: Package initializer path.

    Returns:
        Version string when found.
    """
    if not path.exists():
        return None
    match = _INIT_VERSION_PATTERN.search(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    return match.group("version")


def _read_lock_version(path: Path, project_name: str) -> str | None:
    """Read the local package version from uv.lock.

    Args:
        path: uv.lock path.
        project_name: Project name from pyproject.toml.

    Returns:
        Version string when a package matching the current project is found.
    """
    if not path.exists() or not project_name:
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    packages = data.get("package", [])
    if not isinstance(packages, list):
        return None
    for package in packages:
        if not isinstance(package, dict):
            continue
        if package.get("name") != project_name:
            continue
        version = package.get("version")
        return str(version) if isinstance(version, str) else None
    return None


def _package_dir(project_name: str) -> str:
    """Return the conventional import package directory for a project.

    Args:
        project_name: Distribution name from pyproject.toml.

    Returns:
        Import package directory name.
    """
    return project_name.replace("-", "_")


def _relative_to(project_dir: Path, path: Path) -> str:
    """Return path relative to the project when possible.

    Args:
        project_dir: Project root directory.
        path: Path to display.

    Returns:
        Relative path string.
    """
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)
