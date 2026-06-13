"""Unit tests for uvforge.renderer."""

from __future__ import annotations

from pathlib import Path

import pytest

from uvforge.models import ProjectContext
from uvforge.renderer import (
    embedded_script_path,
    list_embedded_scripts,
    list_templates,
    render_template,
)


def _ctx(tmp_path: Path) -> ProjectContext:
    """Build a minimal ProjectContext for renderer tests.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Configured ProjectContext.
    """
    return ProjectContext(
        project_name="my-lib",
        package_name="my_lib",
        python_version="3.12",
        project_dir=tmp_path / "my-lib",
    )


def test_list_templates_returns_tmpl_files() -> None:
    """Requirement: list_templates must return only .tmpl files."""
    templates = list_templates()
    assert all(t.endswith(".tmpl") for t in templates)


def test_list_templates_contains_pyproject() -> None:
    """Requirement: list_templates must include pyproject.toml.tmpl."""
    assert "pyproject.toml.tmpl" in list_templates()


def test_list_templates_contains_makefile() -> None:
    """Requirement: list_templates must include Makefile.tmpl."""
    assert "Makefile.tmpl" in list_templates()


def test_list_templates_contains_gitignore() -> None:
    """Requirement: list_templates must include gitignore.tmpl."""
    assert "gitignore.tmpl" in list_templates()


def test_list_templates_contains_readme() -> None:
    """Requirement: list_templates must include README.md.tmpl."""
    assert "README.md.tmpl" in list_templates()


def test_render_pyproject_contains_project_name(tmp_path: Path) -> None:
    """Requirement: rendered pyproject.toml must contain the project name."""
    ctx = _ctx(tmp_path)
    result = render_template("pyproject.toml.tmpl", ctx)
    assert "my-lib" in result


def test_render_pyproject_contains_package_name(tmp_path: Path) -> None:
    """Requirement: rendered pyproject.toml must contain the package name."""
    ctx = _ctx(tmp_path)
    result = render_template("pyproject.toml.tmpl", ctx)
    assert "my_lib" in result


def test_render_pyproject_contains_python_version(tmp_path: Path) -> None:
    """Requirement: rendered pyproject.toml must contain the python version."""
    ctx = _ctx(tmp_path)
    result = render_template("pyproject.toml.tmpl", ctx)
    assert "3.12" in result


def test_render_makefile_contains_phony(tmp_path: Path) -> None:
    """Requirement: rendered Makefile must contain a .PHONY declaration."""
    ctx = _ctx(tmp_path)
    result = render_template("Makefile.tmpl", ctx)
    assert ".PHONY" in result


def test_render_makefile_contains_check_target(tmp_path: Path) -> None:
    """Requirement: rendered Makefile must define the check target."""
    ctx = _ctx(tmp_path)
    result = render_template("Makefile.tmpl", ctx)
    assert "check:" in result


def test_render_gitignore_excludes_work(tmp_path: Path) -> None:
    """Requirement: rendered .gitignore must exclude the work/ directory."""
    ctx = _ctx(tmp_path)
    result = render_template("gitignore.tmpl", ctx)
    assert "work/*" in result


def test_render_gitignore_preserves_gitkeep(tmp_path: Path) -> None:
    """Requirement: rendered .gitignore must preserve work/.gitkeep."""
    ctx = _ctx(tmp_path)
    result = render_template("gitignore.tmpl", ctx)
    assert "!work/.gitkeep" in result


def test_render_readme_contains_project_name(tmp_path: Path) -> None:
    """Requirement: rendered README must contain the project name."""
    ctx = _ctx(tmp_path)
    result = render_template("README.md.tmpl", ctx)
    assert "my-lib" in result


def test_render_template_unknown_raises(tmp_path: Path) -> None:
    """Requirement: render_template must raise FileNotFoundError."""
    ctx = _ctx(tmp_path)
    with pytest.raises(FileNotFoundError):
        render_template("nonexistent.tmpl", ctx)


def test_list_embedded_scripts_nonempty() -> None:
    """Requirement: list_embedded_scripts must return at least one script."""
    scripts = list_embedded_scripts()
    assert len(scripts) > 0


def test_list_embedded_scripts_contains_check_sh() -> None:
    """Requirement: embedded scripts must include check.sh."""
    assert "check.sh" in list_embedded_scripts()


def test_list_embedded_scripts_contains_publish_sh() -> None:
    """Requirement: embedded scripts must include publish.sh."""
    assert "publish.sh" in list_embedded_scripts()


def test_embedded_script_path_returns_existing_file() -> None:
    """Requirement: embedded_script_path must return an existing path."""
    path = embedded_script_path("check.sh")
    assert path.exists()


def test_embedded_script_path_unknown_raises() -> None:
    """Requirement: embedded_script_path must raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        embedded_script_path("nonexistent.sh")
