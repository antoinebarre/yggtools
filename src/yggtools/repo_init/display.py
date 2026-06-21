"""Console rendering helpers for repository initialisation commands."""

from __future__ import annotations

from rich.console import Console

from yggtools.repo_init.pipeline import PipelineStep
from yggtools.repo_init.steps import RepoContext

_console = Console()


def print_dry_run_plan(
    ctx: RepoContext,
    *,
    include_uv_init: bool = True,
) -> None:
    """Print the list of actions the init pipeline would perform.

    Args:
        ctx: Pipeline context.
        include_uv_init: Whether to include the ``uv init --lib`` step.
    """
    _console.print(
        "[bold yellow]Dry run - nothing will be written[/bold yellow]",
    )
    _console.print(
        f"Project: [cyan]{ctx.project_name}[/cyan] -> {ctx.project_dir}",
    )
    for action in _init_dry_run_actions(ctx, include_uv_init=include_uv_init):
        _console.print(f"  [dim]would:[/dim] {action}")


def _init_dry_run_actions(
    ctx: RepoContext,
    *,
    include_uv_init: bool,
) -> list[str]:
    """Build the dry-run actions for init workflows.

    Args:
        ctx: Pipeline context.
        include_uv_init: Whether to include the uv project creation step.

    Returns:
        Planned action descriptions.
    """
    actions: list[str] = []
    if include_uv_init:
        actions.append(
            f"uv init --lib {ctx.project_name} --python {ctx.python_version}",
        )
    actions += [
        "ensure src/<package>/__init__.py with __version__",
        "uv add --dev yggtools + quality tools",
        "patch pyproject.toml ([tool.ruff], [tool.mypy], ...)",
        "write Makefile",
        "write CLAUDE.md",
        "create tests/__init__.py, tests/conftest.py",
        "create work/.gitkeep",
    ]
    if not ctx.no_git:
        actions += [
            "write .github/workflows/ci.yml",
            "write .gitlab-ci.yml",
            'git commit "chore: yggtools init-repo"',
        ]
    return actions


def print_reset_dry_run_plan(
    ctx: RepoContext,
    steps: list[PipelineStep],
) -> None:
    """Print the list of reset actions without writing files.

    Args:
        ctx: Pipeline context.
        steps: Reset steps selected by the CLI.
    """
    _console.print(
        "[bold yellow]Dry run - nothing will be written[/bold yellow]",
    )
    _console.print(
        f"Project: [cyan]{ctx.project_name}[/cyan] -> {ctx.project_dir}",
    )
    for step in steps:
        _console.print(f"  [dim]would:[/dim] {step.name}")


def print_init_success(project_name: str) -> None:
    """Print completion guidance for a new project.

    Args:
        project_name: Newly scaffolded project name.
    """
    _console.print()
    _console.print("[bold green]Project ready.[/bold green]")
    _console.print()
    _console.print("Next steps:")
    _console.print(f"  cd {project_name}")
    _console.print("  make check    [dim]# full quality pipeline[/dim]")
    _console.print("  make test     [dim]# tests only[/dim]")
    _console.print("  make format   [dim]# auto-format source[/dim]")


def print_inplace_success() -> None:
    """Print completion guidance for an in-place project init."""
    _console.print()
    _console.print("[bold green]Project ready.[/bold green]")
    _console.print()
    _console.print("Next steps:")
    _console.print("  make check    [dim]# full quality pipeline[/dim]")
    _console.print("  make test     [dim]# tests only[/dim]")


def print_reset_success() -> None:
    """Print the reset completion message."""
    _console.print()
    _console.print("[bold green]Generated files restored.[/bold green]")
