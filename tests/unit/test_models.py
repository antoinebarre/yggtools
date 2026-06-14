"""Unit tests for yggtools.models."""

from __future__ import annotations

from pathlib import Path

import pytest

from yggtools.models import CheckResult, ProjectContext, make_package_name


def test_make_package_name_hyphen() -> None:
    """Requirement: hyphens in project names must become underscores."""
    assert make_package_name("my-lib") == "my_lib"


def test_make_package_name_uppercase() -> None:
    """Requirement: make_package_name must lowercase the result."""
    assert make_package_name("MyLib") == "mylib"


def test_make_package_name_mixed() -> None:
    """Requirement: make_package_name must handle mixed-case with hyphens."""
    assert make_package_name("My-Great-Lib") == "my_great_lib"


def test_make_package_name_no_change() -> None:
    """Requirement: make_package_name must leave valid names unchanged."""
    assert make_package_name("mylib") == "mylib"


def test_project_context_defaults(tmp_path: Path) -> None:
    """Requirement: ProjectContext default flags must all be False."""
    ctx = ProjectContext(
        project_name="demo",
        package_name="demo",
        python_version="3.12",
        project_dir=tmp_path,
    )
    assert ctx.dry_run is False
    assert ctx.force is False
    assert ctx.no_git is False


def test_project_context_flags(tmp_path: Path) -> None:
    """Requirement: ProjectContext must store non-default flag values."""
    ctx = ProjectContext(
        project_name="demo",
        package_name="demo",
        python_version="3.12",
        project_dir=tmp_path,
        dry_run=True,
        force=True,
        no_git=True,
    )
    assert ctx.dry_run is True
    assert ctx.force is True
    assert ctx.no_git is True


def test_project_context_is_frozen(tmp_path: Path) -> None:
    """Requirement: ProjectContext must be immutable after construction."""
    ctx = ProjectContext(
        project_name="demo",
        package_name="demo",
        python_version="3.12",
        project_dir=tmp_path,
    )
    with pytest.raises(
        AttributeError,
        match="cannot assign to field",
    ):
        ctx.project_name = "other"  # type: ignore[misc]


def test_check_result_passed() -> None:
    """Requirement: CheckResult must store a passing state without detail."""
    result = CheckResult(label="src/", passed=True)
    assert result.passed is True
    assert result.detail == ""


def test_check_result_failed() -> None:
    """Requirement: CheckResult must store a failing state with detail."""
    result = CheckResult(label="src/", passed=False, detail="not found")
    assert result.passed is False
    assert result.detail == "not found"
