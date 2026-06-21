"""Console rendering for version-related commands."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from yggtools.cli_support import relative_to_project
from yggtools.quality.checks.version import VersionArtifact

_console = Console()


def print_version_artifacts_table(
    artifacts: list[VersionArtifact],
    project_dir: Path,
) -> None:
    """Print a table of discovered package version artifacts.

    Args:
        artifacts: Version artifacts to display.
        project_dir: Project root directory.
    """
    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("Artifact", style="bold")
    table.add_column("Path")
    table.add_column("Version", justify="right")
    table.add_column("Required", justify="center")

    for artifact in artifacts:
        version = artifact.version if artifact.version is not None else "-"
        required = "yes" if artifact.required else "no"
        table.add_row(
            artifact.name,
            relative_to_project(artifact.path, project_dir),
            version,
            required,
        )

    _console.print(Panel(table, title="[bold]Package versions[/bold]"))
