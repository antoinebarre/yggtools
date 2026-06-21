"""yggtools release workflow demo.

Demonstrates the version bump workflow in a temporary project without
network access.  The demo creates a minimal uv-style package, runs the
real ``yggtools increase-version`` CLI command with ``uv lock`` mocked,
then verifies the result with the ``version-consistency`` lint.

Usage:
    uv run python demo.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent / "src"))

from yggtools.cli import app
from yggtools.quality.checks.version import check_version_consistency

_console = Console()
_runner = CliRunner()


def _write_demo_project(project_dir: Path) -> None:
    """Create a minimal package with synchronized version artifacts.

    Args:
        project_dir: Directory to populate.
    """
    package_dir = project_dir / "src" / "demo_project"
    package_dir.mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text(
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n\n'
        "[project]\n"
        'name = "demo-project"\n'
        'version = "1.2.3"\n',
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text(
        '"""Demo package."""\n\n__version__ = "1.2.3"\n',
        encoding="utf-8",
    )
    (project_dir / "uv.lock").write_text(
        '[[package]]\nname = "demo-project"\nversion = "1.2.3"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )


def _show_file(project_dir: Path, relative: str) -> None:
    """Print a file with syntax highlighting.

    Args:
        project_dir: Project root.
        relative: File path relative to project root.
    """
    path = project_dir / relative
    syntax = Syntax(
        path.read_text(encoding="utf-8"),
        path.suffix.lstrip(".") or "text",
        theme="monokai",
        line_numbers=True,
    )
    _console.print(Panel(syntax, title=f"[bold]{relative}[/bold]"))


def _print_version_table(project_dir: Path) -> None:
    """Print version consistency lint metadata.

    Args:
        project_dir: Project root.
    """
    result = check_version_consistency(project_dir)
    table = Table(title="version-consistency", show_header=True)
    table.add_column("Artifact", style="bold")
    table.add_column("Path")
    table.add_column("Version", justify="right")

    artifacts = result.metadata["artifacts"]
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if isinstance(artifact, dict):
                table.add_row(
                    str(artifact["name"]),
                    str(artifact["path"]),
                    str(artifact["version"]),
                )
    _console.print(table)
    status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
    _console.print(f"{status} {result.detail}")


def main() -> int:
    """Run the release workflow demo.

    Returns:
        Exit code.
    """
    _console.print(
        Panel.fit(
            "[bold cyan]yggtools release demo[/bold cyan]\n"
            "Bump a package with Semantic Versioning level 1.",
            border_style="cyan",
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / "demo-project"
        project_dir.mkdir()
        _write_demo_project(project_dir)

        _console.print("\n[bold]Before[/bold]")
        _print_version_table(project_dir)

        _console.print("\n[bold]Command[/bold]")
        _console.print("uv run yggtools increase-version 1")
        with patch("yggtools.versioning.run_uv"):
            result = _runner.invoke(
                app,
                ["increase-version", "1", "--path", str(project_dir)],
            )
        _console.print(result.output.rstrip())
        if result.exit_code != 0:
            return result.exit_code

        _console.print("\n[bold]After[/bold]")
        _print_version_table(project_dir)

        _console.print("\n[bold]Updated artifacts[/bold]")
        _show_file(project_dir, "pyproject.toml")
        _show_file(project_dir, "src/demo_project/__init__.py")
        _show_file(project_dir, "uv.lock")

    _console.print("\n[bold green]Demo complete.[/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
