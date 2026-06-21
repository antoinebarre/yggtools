"""Typer commands for yggtools repository scaffolding workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from yggtools.repo_init import display
from yggtools.repo_init.pipeline import (
    STEPS,
    STEPS_INIT,
    STEPS_RESET,
    STEPS_RESET_AI,
    STEPS_RESET_CI,
    STEPS_RESET_SCRIPTS,
    PipelineStep,
)
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError, check_uv_available

_console = Console()
_err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    """Register repository initialisation commands on the root app.

    Args:
        app: Root Typer application.
    """
    app.command("init-repo")(init_repo)
    app.command("init")(init_inplace)
    app.command("reset")(reset_cmd)


def init_repo(
    project_name: Annotated[
        str | None,
        typer.Argument(
            help="Project name. Defaults to the current directory name.",
        ),
    ] = None,
    python: Annotated[
        str,
        typer.Option("--python", help="Target Python version."),
    ] = "3.12",
    no_git: Annotated[
        bool,
        typer.Option(
            "--no-git/--git",
            help="Skip CI workflow generation and final git commit.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Show what would be done without writing anything.",
        ),
    ] = False,
) -> None:
    """Scaffold a new Python package using uv and the yggtools pipeline.

    Args:
        project_name: Optional project name.
        python: Target Python version.
        no_git: Whether to skip git and CI artifacts.
        dry_run: Whether to print actions without writing files.
    """
    resolved_name = project_name or Path.cwd().name
    parent = Path.cwd() if project_name else Path.cwd().parent
    ctx = RepoContext(
        project_name=resolved_name,
        python_version=python,
        parent_dir=parent,
        no_git=no_git,
        dry_run=dry_run,
    )

    if dry_run:
        display.print_dry_run_plan(ctx, include_uv_init=True)
        return

    _ensure_uv_available()
    _console.print(
        f"[bold]Initialising[/bold] [cyan]{ctx.project_name}[/cyan] "
        f"(Python {ctx.python_version})",
    )
    _run_steps_or_exit(ctx, steps=STEPS)
    display.print_init_success(ctx.project_name)


def init_inplace(
    python: Annotated[
        str,
        typer.Option("--python", help="Target Python version."),
    ] = "3.12",
    no_git: Annotated[
        bool,
        typer.Option(
            "--no-git/--git",
            help="Skip CI workflow generation and final git commit.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Show what would be done without writing anything.",
        ),
    ] = False,
) -> None:
    """Complete the yggtools scaffold in the current directory.

    Args:
        python: Target Python version.
        no_git: Whether to skip git and CI artifacts.
        dry_run: Whether to print actions without writing files.
    """
    cwd = Path.cwd()
    _ensure_pyproject_exists(cwd, missing_uv_init_hint=True)
    ctx = RepoContext(
        project_name=cwd.name,
        python_version=python,
        parent_dir=cwd.parent,
        no_git=no_git,
        dry_run=dry_run,
    )

    if dry_run:
        display.print_dry_run_plan(ctx, include_uv_init=False)
        return

    _ensure_uv_available()
    _console.print(
        f"[bold]Initialising[/bold] [cyan]{ctx.project_name}[/cyan] "
        f"(Python {ctx.python_version})",
    )
    _run_steps_or_exit(ctx, steps=STEPS_INIT)
    display.print_inplace_success()


def reset_cmd(
    only: Annotated[
        str | None,
        typer.Option(
            "--only",
            help="Subset to reset: all, ai, ci, or scripts.",
        ),
    ] = None,
    python: Annotated[
        str | None,
        typer.Option(
            "--python",
            help=(
                "Target Python version for CI "
                "(default: .python-version or 3.12)."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Show what would be reset without writing anything.",
        ),
    ] = False,
) -> None:
    """Restore yggtools-generated files in the current repository.

    Args:
        only: Optional reset subset.
        python: Optional Python version for generated CI files.
        dry_run: Whether to print actions without writing files.
    """
    cwd = Path.cwd()
    _ensure_pyproject_exists(cwd, missing_uv_init_hint=False)

    steps = reset_steps(only)
    if steps is None:
        _err_console.print(
            "[bold red]Error:[/bold red] --only must be one of: "
            "all, ai, ci, scripts.",
        )
        raise typer.Exit(1)

    ctx = RepoContext(
        project_name=cwd.name,
        python_version=python or read_python_version(cwd),
        parent_dir=cwd.parent,
        dry_run=dry_run,
    )

    if dry_run:
        display.print_reset_dry_run_plan(ctx, steps)
        return

    _console.print(
        "[bold]Resetting yggtools files[/bold] - "
        f"[cyan]{ctx.project_name}[/cyan]"
    )
    _run_steps_or_exit(ctx, steps=steps)
    display.print_reset_success()


def _ensure_pyproject_exists(
    project_dir: Path,
    *,
    missing_uv_init_hint: bool,
) -> None:
    """Exit when the current directory is not a uv project.

    Args:
        project_dir: Current project directory.
        missing_uv_init_hint: Whether to include the uv init guidance.
    """
    if (project_dir / "pyproject.toml").exists():
        return
    message = "[bold red]Error:[/bold red] No pyproject.toml found in the "
    if missing_uv_init_hint:
        message += "current directory. Run ``uv init PROJECT_NAME`` first."
    else:
        message += "current directory."
    _err_console.print(message)
    raise typer.Exit(1)


def _ensure_uv_available() -> None:
    """Exit when uv is unavailable."""
    try:
        check_uv_available()
    except UvNotFoundError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc


def _run_steps_or_exit(ctx: RepoContext, *, steps: list[PipelineStep]) -> None:
    """Run selected repository steps and convert failures to CLI exits.

    Args:
        ctx: Pipeline context.
        steps: Pipeline steps to execute.
    """
    try:
        run_with_progress(ctx, steps=steps)
    except StepError as exc:
        _err_console.print(f"\n[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        _err_console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(1) from exc


def run_with_progress(
    ctx: RepoContext,
    steps: list[PipelineStep] | None = None,
) -> None:
    """Execute a pipeline and print a progress line per step.

    Args:
        ctx: Pipeline context passed to each step.
        steps: List of PipelineStep to execute. Defaults to ``STEPS``.

    Raises:
        StepError: Propagated from any failing step.
    """
    active_steps = steps if steps is not None else STEPS
    for step in active_steps:
        step.fn(ctx)
        _console.print(f"  [green]✓[/green] {step.name}")


def reset_steps(only: str | None) -> list[PipelineStep] | None:
    """Return reset steps for the requested subset.

    Args:
        only: Optional subset name from the CLI.

    Returns:
        The matching reset steps, or None for an invalid subset.
    """
    normalized = (only or "all").lower()
    groups = {
        "all": STEPS_RESET,
        "ai": STEPS_RESET_AI,
        "ci": STEPS_RESET_CI,
        "scripts": STEPS_RESET_SCRIPTS,
    }
    return groups.get(normalized)


def read_python_version(project_dir: Path) -> str:
    """Read the project's Python version for generated CI files.

    Args:
        project_dir: Project root directory.

    Returns:
        The .python-version content, or the yggtools default.
    """
    python_version = project_dir / ".python-version"
    if not python_version.exists():
        return "3.12"
    content = python_version.read_text(encoding="utf-8").strip()
    return content or "3.12"
