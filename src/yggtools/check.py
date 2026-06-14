"""Structural audit logic for the yggtools check command."""

from __future__ import annotations

import re
import stat
from pathlib import Path

from yggtools.models import CheckResult

_REQUIRED_SCRIPTS = [
    "check.sh",
    "check_docstrings.py",
    "code_metrics.py",
    "security_deps.sh",
    "publish.sh",
]

_REQUIRED_MAKEFILE_TARGETS = [
    "check",
    "ci",
    "test",
    "lint",
    "typecheck",
    "build",
    "publish",
]

_REQUIRED_DEV_TOOLS = [
    "ruff",
    "flake8",
    "mypy",
    "pytest",
    "pytest-cov",
    "bandit",
    "pip-audit",
    "twine",
]


def run_check(project_dir: Path) -> list[CheckResult]:
    """Audit a project directory for yggtools structural conformance.

    Checks for required directories, scripts, Makefile targets, dev
    dependencies, and the ``work/.gitkeep`` sentinel file.

    Args:
        project_dir: Absolute path to the project root to inspect.

    Returns:
        List of CheckResult objects, one per audited item.
    """
    results: list[CheckResult] = []
    results += _check_directories(project_dir)
    results += _check_scripts(project_dir)
    results += _check_makefile(project_dir)
    results += _check_pyproject(project_dir)
    results += _check_misc(project_dir)
    return results


def _check_directories(project_dir: Path) -> list[CheckResult]:
    """Check that required project directories exist.

    Args:
        project_dir: Project root directory.

    Returns:
        CheckResult list for directory checks.
    """
    required = ["src", "tests", "scripts", "work", "doc"]
    return [
        CheckResult(
            label=f"Directory {name}/",
            passed=(project_dir / name).is_dir(),
            detail=(
                "" if (project_dir / name).is_dir() else f"{name}/ not found"
            ),
        )
        for name in required
    ]


def _check_scripts(project_dir: Path) -> list[CheckResult]:
    """Check that all required quality scripts are present.

    Args:
        project_dir: Project root directory.

    Returns:
        CheckResult list for script checks.
    """
    results = []
    for script in _REQUIRED_SCRIPTS:
        path = project_dir / "scripts" / script
        exists = path.exists()
        is_sh = script.endswith(".sh")
        passed = (exists and _is_executable(path)) if is_sh else exists
        if not exists:
            detail = "file not found"
        elif is_sh and not _is_executable(path):
            detail = "file not executable"
        else:
            detail = ""
        results.append(
            CheckResult(
                label=f"scripts/{script}",
                passed=passed,
                detail=detail,
            ),
        )
    return results


def _check_makefile(project_dir: Path) -> list[CheckResult]:
    """Check that the Makefile contains the required targets.

    Args:
        project_dir: Project root directory.

    Returns:
        CheckResult list for Makefile target checks.
    """
    makefile = project_dir / "Makefile"
    if not makefile.exists():
        return [
            CheckResult(
                label="Makefile",
                passed=False,
                detail="Makefile not found",
            ),
        ]

    content = makefile.read_text(encoding="utf-8")
    results = []
    for target in _REQUIRED_MAKEFILE_TARGETS:
        pattern = rf"^{re.escape(target)}\s*:"
        found = bool(re.search(pattern, content, re.MULTILINE))
        results.append(
            CheckResult(
                label=f"Makefile target: {target}",
                passed=found,
                detail=(
                    "" if found else f"target '{target}' not found in Makefile"
                ),
            ),
        )
    return results


def _check_pyproject(project_dir: Path) -> list[CheckResult]:
    """Check that pyproject.toml declares the required dev tools.

    Args:
        project_dir: Project root directory.

    Returns:
        CheckResult list for pyproject.toml checks.
    """
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.exists():
        return [
            CheckResult(
                label="pyproject.toml",
                passed=False,
                detail="pyproject.toml not found",
            ),
        ]

    content = pyproject.read_text(encoding="utf-8")
    results = []
    for tool in _REQUIRED_DEV_TOOLS:
        found = tool in content
        results.append(
            CheckResult(
                label=f"dev dep: {tool}",
                passed=found,
                detail=(
                    "" if found else f"'{tool}' not found in pyproject.toml"
                ),
            ),
        )
    return results


def _check_misc(project_dir: Path) -> list[CheckResult]:
    """Check miscellaneous required files.

    Args:
        project_dir: Project root directory.

    Returns:
        CheckResult list for miscellaneous file checks.
    """
    checks = [
        (".python-version", (project_dir / ".python-version").exists()),
        ("work/.gitkeep", (project_dir / "work" / ".gitkeep").exists()),
    ]
    return [
        CheckResult(
            label=label,
            passed=passed,
            detail="" if passed else f"{label} not found",
        )
        for label, passed in checks
    ]


def _is_executable(path: Path) -> bool:
    """Return whether a file has the executable permission bit set.

    Args:
        path: File path to inspect.

    Returns:
        True if any executable bit is set.
    """
    return bool(
        path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
    )
