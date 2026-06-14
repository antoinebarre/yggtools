"""Unit tests for yggtools.check."""

from __future__ import annotations

import stat
from pathlib import Path

from yggtools.check import run_check


def _make_minimal_project(base: Path) -> Path:
    """Create a minimal project structure that satisfies all checks.

    Args:
        base: Temporary directory base.

    Returns:
        Path to the created project directory.
    """
    project = base / "myproject"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "scripts").mkdir()
    (project / "work").mkdir()
    (project / "doc").mkdir()
    (project / "work" / ".gitkeep").touch()
    (project / ".python-version").write_text("3.12\n")

    required_scripts = [
        "check.sh",
        "check_docstrings.py",
        "code_metrics.py",
        "security_deps.sh",
        "publish.sh",
    ]
    for script in required_scripts:
        path = project / "scripts" / script
        path.write_text("#!/usr/bin/env bash\n")
        if script.endswith(".sh"):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)

    makefile = project / "Makefile"
    makefile.write_text(
        "check:\n\t@echo ok\n"
        "ci:\n\t@echo ok\n"
        "test:\n\t@echo ok\n"
        "lint:\n\t@echo ok\n"
        "typecheck:\n\t@echo ok\n"
        "build:\n\t@echo ok\n"
        "publish:\n\t@echo ok\n",
    )

    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        "[dependency-groups]\ndev = [\n"
        '  "ruff>=0.4",\n  "flake8>=7",\n  "mypy>=1.10",\n'
        '  "pytest>=8",\n  "pytest-cov>=6",\n  "bandit>=1.8",\n'
        '  "pip-audit>=2.8",\n  "twine>=6",\n]\n',
    )
    return project


def test_check_passes_on_complete_project(tmp_path: Path) -> None:
    """Requirement: run_check must return all PASS for a complete project."""
    project = _make_minimal_project(tmp_path)
    results = run_check(project)
    failed = [r for r in results if not r.passed]
    assert failed == [], f"Unexpected failures: {[r.label for r in failed]}"


def test_check_fails_missing_src(tmp_path: Path) -> None:
    """Requirement: run_check must report FAIL when src/ is absent."""
    project = _make_minimal_project(tmp_path)
    (project / "src").rmdir()
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert "Directory src/" in labels


def test_check_fails_missing_work_gitkeep(tmp_path: Path) -> None:
    """Requirement: run_check must report FAIL when work/.gitkeep is absent."""
    project = _make_minimal_project(tmp_path)
    (project / "work" / ".gitkeep").unlink()
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert "work/.gitkeep" in labels


def test_check_fails_missing_check_sh(tmp_path: Path) -> None:
    """Requirement: run_check must report FAIL when check.sh is absent."""
    project = _make_minimal_project(tmp_path)
    (project / "scripts" / "check.sh").unlink()
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert "scripts/check.sh" in labels


def test_check_fails_non_executable_check_sh(tmp_path: Path) -> None:
    """Requirement: run_check must report FAIL when check.sh is not exec."""
    project = _make_minimal_project(tmp_path)
    path = project / "scripts" / "check.sh"
    path.chmod(
        path.stat().st_mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
    )
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert "scripts/check.sh" in labels


def test_check_fails_missing_makefile_target(tmp_path: Path) -> None:
    """Requirement: run_check must report FAIL for missing Makefile target."""
    project = _make_minimal_project(tmp_path)
    (project / "Makefile").write_text("all:\n\t@echo hi\n")
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert "Makefile target: check" in labels


def test_check_fails_missing_pyproject(tmp_path: Path) -> None:
    """Requirement: run_check must report FAIL when pyproject.toml absent."""
    project = _make_minimal_project(tmp_path)
    (project / "pyproject.toml").unlink()
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert "pyproject.toml" in labels


def test_check_fails_missing_python_version_file(tmp_path: Path) -> None:
    """Requirement: run_check must FAIL when .python-version is absent."""
    project = _make_minimal_project(tmp_path)
    (project / ".python-version").unlink()
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert ".python-version" in labels


def test_check_reports_fail_when_makefile_absent(tmp_path: Path) -> None:
    """Requirement: run_check must FAIL with 'Makefile' label when absent."""
    project = _make_minimal_project(tmp_path)
    (project / "Makefile").unlink()
    results = run_check(project)
    labels = {r.label for r in results if not r.passed}
    assert "Makefile" in labels


def test_check_result_labels_are_strings(tmp_path: Path) -> None:
    """Requirement: all CheckResult labels must be non-empty strings."""
    project = _make_minimal_project(tmp_path)
    results = run_check(project)
    for result in results:
        assert isinstance(result.label, str)
        assert len(result.label) > 0
