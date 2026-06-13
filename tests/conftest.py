"""Shared pytest fixtures for the uvforge test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from uvforge.models import ProjectContext
from uvforge.renderer import (
    embedded_script_path,
    list_embedded_scripts,
    render_template,
)
from uvforge.scaffold import copy_script, scaffold_project, write_file


@pytest.fixture
def project_ctx(tmp_path: Path) -> ProjectContext:
    """Return a minimal ProjectContext pointing to a temporary directory.

    Requirement: fixtures must provide isolated, deterministic project
    contexts.
    """
    return ProjectContext(
        project_name="my-lib",
        package_name="my_lib",
        python_version="3.12",
        project_dir=tmp_path / "my-lib",
    )


@pytest.fixture
def scaffolded_project(tmp_path: Path) -> Path:
    """Return a directory containing the minimal expected uvforge structure.

    Creates directories and stub files that a freshly initialised project
    would contain, without running the full init workflow.

    Requirement: integration fixtures must reproduce the full expected
    layout.
    """
    project_dir = tmp_path / "my-lib"
    ctx = ProjectContext(
        project_name="my-lib",
        package_name="my_lib",
        python_version="3.12",
        project_dir=project_dir,
    )
    scaffold_project(ctx)

    config_templates = [
        ("pyproject.toml.tmpl", "pyproject.toml"),
        ("Makefile.tmpl", "Makefile"),
        ("gitignore.tmpl", ".gitignore"),
        ("README.md.tmpl", "README.md"),
    ]
    for template_name, output_name in config_templates:
        content = render_template(template_name, ctx)
        write_file(project_dir / output_name, content)

    write_file(project_dir / ".python-version", "3.12\n")

    for script_name in list_embedded_scripts():
        source = embedded_script_path(script_name)
        dest = project_dir / "scripts" / script_name
        copy_script(source, dest)

    return project_dir
