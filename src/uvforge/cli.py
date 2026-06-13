"""Command-line interface for uvforge."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from uvforge.check import run_check
from uvforge.init import ConflictError, run_init
from uvforge.models import ProjectContext, make_package_name
from uvforge.uv_runner import UvNotFoundError

app = typer.Typer(
    name="uvforge",
    help="uv overlay for opinionated Python package scaffolding.",
    no_args_is_help=True,
)
_console = Console()
_err_console = Console(stderr=True)


@app.command()
def init(
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
            help="Skip git repository initialisation.",
        ),
    ] = False,
    force: Annotated[
        bool,
        typer.Option(
            "--force/--no-force",
            help="Overwrite existing files without confirmation.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Show what would be created without writing anything.",
        ),
    ] = False,
) -> None:
    """Initialise a new Python package with the uvforge quality pipeline.

    Creates the full project structure including src/ layout, embedded
    quality scripts, Makefile pipeline, and dev dependencies managed by uv.
    """
    resolved_name = project_name or Path.cwd().name
    ctx = ProjectContext(
        project_name=resolved_name,
        package_name=make_package_name(resolved_name),
        python_version=python,
        project_dir=(
            Path.cwd() / resolved_name if project_name else Path.cwd()
        ),
        dry_run=dry_run,
        force=force,
        no_git=no_git,
    )

    try:
        run_init(ctx)
    except UvNotFoundError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        _err_console.print(
            "Install uv from [link]"
            "https://docs.astral.sh/uv/getting-started/installation/"
            "[/link]",
        )
        raise typer.Exit(1) from exc
    except ConflictError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        _err_console.print(f"[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(1) from exc


@app.command()
def check(
    path: Annotated[
        str | None,
        typer.Argument(
            help="Project directory to audit. Defaults to current directory.",
        ),
    ] = None,
) -> None:
    """Audit a project directory for uvforge structural conformance.

    Checks for required directories, scripts, Makefile targets, and
    dev dependencies. Exits with code 1 if any check fails.
    """
    project_dir = Path(path) if path else Path.cwd()
    results = run_check(project_dir)

    table = Table(title=f"uvforge check — {project_dir}", show_header=True)
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Detail", style="dim")

    failed = 0
    for result in results:
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        table.add_row(result.label, status, result.detail)
        if not result.passed:
            failed += 1

    _console.print(table)

    if failed:
        _console.print(f"\n[bold red]{failed} check(s) failed.[/bold red]")
        raise typer.Exit(1)
    _console.print("\n[bold green]All checks passed.[/bold green]")


def main() -> None:  # pragma: no cover
    """Entry point for the uvforge CLI application."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
