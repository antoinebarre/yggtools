"""Orchestration logic for the uvforge init command."""

from __future__ import annotations

import stat

from rich.console import Console

from uvforge.models import ProjectContext
from uvforge.renderer import (
    embedded_script_path,
    list_embedded_scripts,
    render_template,
)
from uvforge.scaffold import copy_script, scaffold_project, write_file
from uvforge.uv_runner import (
    DEV_DEPS,
    check_uv_available,
    git_add_all,
    git_commit,
    git_init,
    uv_add_dev_deps,
    uv_sync,
)

_console = Console()

_CONFIG_TEMPLATES: list[tuple[str, str]] = [
    ("pyproject.toml.tmpl", "pyproject.toml"),
    ("Makefile.tmpl", "Makefile"),
    ("gitignore.tmpl", ".gitignore"),
    ("README.md.tmpl", "README.md"),
]


class ConflictError(RuntimeError):
    """Raised when an existing project would be overwritten without --force."""


class InitError(RuntimeError):
    """Raised when project initialisation fails for a recoverable reason."""


def run_init(ctx: ProjectContext) -> None:
    """Execute the full uvforge init workflow.

    Creates the project scaffold, renders configuration files, copies
    embedded quality scripts, installs dev dependencies via uv, and
    optionally initialises a git repository.

    Args:
        ctx: Project context with name, version, and option flags.

    Raises:
        UvNotFoundError: If uv is not found in PATH.
        ConflictError: If a pyproject.toml already exists and --force is off.
        InitError: If a required step fails for a recoverable reason.
    """
    _validate_preconditions(ctx)

    if ctx.dry_run:
        _print_dry_run_plan(ctx)
        return

    _console.print(
        f"[bold]Initialising project[/bold] [cyan]{ctx.project_name}[/cyan]",
    )

    scaffold_project(ctx)
    _console.print("  [green]✓[/green] Directory structure created")

    _write_config_files(ctx)
    _console.print("  [green]✓[/green] Configuration files written")

    _copy_scripts(ctx)
    _console.print("  [green]✓[/green] Quality scripts installed")

    _install_dev_deps(ctx)
    _console.print("  [green]✓[/green] Dev dependencies installed")

    if not ctx.no_git:
        _init_git(ctx)
        _console.print("  [green]✓[/green] Git repository initialised")

    _print_summary(ctx)


def _validate_preconditions(ctx: ProjectContext) -> None:
    """Check that all prerequisites for initialisation are met.

    Args:
        ctx: Project context.

    Raises:
        UvNotFoundError: If uv is not accessible.
        ConflictError: If the project directory already contains
            pyproject.toml.
    """
    check_uv_available()
    existing = ctx.project_dir / "pyproject.toml"
    if existing.exists() and not ctx.force:
        msg = (
            f"pyproject.toml already exists in {ctx.project_dir}. "
            "Use --force to overwrite."
        )
        raise ConflictError(msg)


def _write_config_files(ctx: ProjectContext) -> None:
    """Render and write all configuration templates to the project directory.

    Args:
        ctx: Project context used for template variable substitution.
    """
    for template_name, output_name in _CONFIG_TEMPLATES:
        content = render_template(template_name, ctx)
        write_file(
            ctx.project_dir / output_name,
            content,
            dry_run=ctx.dry_run,
        )

    write_file(
        ctx.project_dir / ".python-version",
        f"{ctx.python_version}\n",
        dry_run=ctx.dry_run,
    )


def _copy_scripts(ctx: ProjectContext) -> None:
    """Copy all embedded quality scripts into the project's scripts/ directory.

    Args:
        ctx: Project context.
    """
    for script_name in list_embedded_scripts():
        if ctx.dry_run:
            continue
        source = embedded_script_path(script_name)
        dest = ctx.project_dir / "scripts" / script_name
        copy_script(source, dest, dry_run=False)
        if not script_name.endswith(".sh"):
            current = dest.stat().st_mode
            dest.chmod(
                current & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
            )


def _install_dev_deps(ctx: ProjectContext) -> None:
    """Install dev dependencies into the project via uv.

    Args:
        ctx: Project context.
    """
    uv_add_dev_deps(ctx.project_dir, DEV_DEPS)
    uv_sync(ctx.project_dir)


def _init_git(ctx: ProjectContext) -> None:
    """Initialise a git repository and create the first commit.

    Args:
        ctx: Project context.
    """
    git_init(ctx.project_dir)
    git_add_all(ctx.project_dir)
    git_commit(ctx.project_dir, "chore: uvforge init")


def _print_dry_run_plan(ctx: ProjectContext) -> None:
    """Display the list of files that would be created without --dry-run.

    Args:
        ctx: Project context.
    """
    _console.print(
        "[bold yellow]Dry run — nothing will be written[/bold yellow]",
    )
    _console.print(
        f"Project: [cyan]{ctx.project_name}[/cyan] → {ctx.project_dir}",
    )
    paths = [
        f"src/{ctx.package_name}/__init__.py",
        f"src/{ctx.package_name}/py.typed",
        "tests/__init__.py",
        f"tests/test_{ctx.package_name}.py",
        "scripts/__init__.py",
        *[f"scripts/{s}" for s in list_embedded_scripts()],
        "work/.gitkeep",
        "doc/.gitkeep",
        "pyproject.toml",
        "Makefile",
        ".gitignore",
        "README.md",
        ".python-version",
    ]
    for p in paths:
        _console.print(f"  [dim]would create[/dim]  {p}")


def _print_summary(ctx: ProjectContext) -> None:
    """Print the post-initialisation summary and next steps.

    Args:
        ctx: Project context.
    """
    _console.print()
    _console.print("[bold green]Project ready.[/bold green]")
    _console.print()
    _console.print("Next steps:")
    _console.print(f"  cd {ctx.project_dir.name}")
    _console.print(
        "  make check    [dim]# run the full quality pipeline[/dim]",
    )
    _console.print("  make test     [dim]# run tests only[/dim]")
    _console.print("  make build    [dim]# build the package[/dim]")
