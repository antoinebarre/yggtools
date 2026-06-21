"""Typer commands for package version workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from yggtools.cli_support import relative_to_project
from yggtools.quality.checks.version import _collect_version_artifacts
from yggtools.version_display import print_version_artifacts_table
from yggtools.versioning import VersionError, increase_project_version

_console = Console()
_err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    """Register version commands on the root Typer application.

    Args:
        app: Root Typer application.
    """
    app.command("increase-version")(increase_version_cmd)
    app.command("version")(version_cmd)


def increase_version_cmd(
    level: Annotated[
        int,
        typer.Argument(help="SemVer level: 1=patch, 2=minor, 3=major."),
    ],
    path: Annotated[
        str | None,
        typer.Option("--path", help="Project directory (default: cwd)."),
    ] = None,
) -> None:
    """Increase package version across all managed artifacts.

    Args:
        level: SemVer level to apply.
        path: Optional project directory.
    """
    project_dir = Path(path) if path else Path.cwd()
    try:
        update = increase_project_version(project_dir, level)
    except VersionError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    _console.print(
        "[bold green]Version increased[/bold green] "
        f"[cyan]{update.project_name}[/cyan]: "
        f"{update.old_version} -> {update.new_version}",
    )
    for file_path in update.files:
        relative_path = relative_to_project(file_path, project_dir)
        _console.print(f"  [green]✓[/green] {relative_path}")
    _console.print("  [green]✓[/green] uv lock")


def version_cmd(
    path: Annotated[
        str | None,
        typer.Option("--path", help="Project directory (default: cwd)."),
    ] = None,
) -> None:
    """List package versions found in managed artifacts.

    Args:
        path: Optional project directory.
    """
    project_dir = Path(path) if path else Path.cwd()
    artifacts = _collect_version_artifacts(project_dir)
    missing = [
        artifact
        for artifact in artifacts
        if artifact.required and artifact.version is None
    ]
    versions = {
        artifact.version
        for artifact in artifacts
        if artifact.version is not None
    }
    passed = not missing and len(versions) <= 1

    print_version_artifacts_table(artifacts, project_dir)
    if passed:
        version = next(iter(versions), "unknown")
        _console.print(
            f"\n[bold green]Version consistent:[/bold green] {version}",
        )
        return

    _console.print("\n[bold red]Version mismatch detected.[/bold red]")
    raise typer.Exit(1)
