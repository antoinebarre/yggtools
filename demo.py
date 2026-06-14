"""yggtools demo script.

Demonstrates the full yggtools init workflow in a temporary directory,
then runs yggtools check on the result, and shows the generated file tree.
No real uv or git calls are made — dev dependency installation is skipped
so the demo runs without a network connection.

Usage:
    uv run python demo.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.tree import Tree

from yggtools.check import run_check
from yggtools.init import run_init
from yggtools.models import ProjectContext, make_package_name

_console = Console()


def _build_tree(directory: Path, tree: Tree) -> None:
    """Recursively add directory entries to a Rich Tree widget.

    Args:
        directory: Directory to render.
        tree: Rich Tree node to populate.
    """
    for path in sorted(directory.iterdir()):
        if path.name in (".git", "__pycache__", ".venv"):
            continue
        if path.is_dir():
            branch = tree.add(f"[bold blue]{path.name}/[/bold blue]")
            _build_tree(path, branch)
        else:
            tree.add(f"[green]{path.name}[/green]")


def _show_file(project_dir: Path, relative: str) -> None:
    """Print a generated file's contents with syntax highlighting.

    Args:
        project_dir: Project root directory.
        relative: Relative path to the file within the project.
    """
    path = project_dir / relative
    if not path.exists():
        _console.print(f"[dim]{relative} — not found[/dim]")
        return
    content = path.read_text(encoding="utf-8")
    ext = path.suffix.lstrip(".") or "text"
    if path.name == "Makefile":
        ext = "makefile"
    syntax = Syntax(content, ext, theme="monokai", line_numbers=True)
    _console.print(Panel(syntax, title=f"[bold]{relative}[/bold]", expand=False))


def _run_demo_init(project_dir: Path, project_name: str) -> None:
    """Execute yggtools init with patched uv/git calls.

    Args:
        project_dir: Target project directory.
        project_name: Name of the project to create.
    """
    ctx = ProjectContext(
        project_name=project_name,
        package_name=make_package_name(project_name),
        python_version="3.12",
        project_dir=project_dir,
        no_git=True,
    )
    with (
        patch("yggtools.init.check_uv_available"),
        patch("yggtools.init.uv_add_dev_deps"),
        patch("yggtools.init.uv_sync"),
    ):
        run_init(ctx)


def _run_demo_check(project_dir: Path) -> int:
    """Run yggtools check and display the results table.

    Args:
        project_dir: Project directory to audit.

    Returns:
        Number of failed checks.
    """
    from rich.table import Table

    results = run_check(project_dir)
    table = Table(title="yggtools check results", show_header=True)
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
    return failed


def main() -> int:
    """Run the yggtools demo.

    Returns:
        Exit code: 0 on success, 1 on demo failure.
    """
    project_name = "demo-project"
    _console.print()
    _console.print(
        Panel.fit(
            "[bold cyan]yggtools demo[/bold cyan]\n"
            f"Scaffolding project: [yellow]{project_name}[/yellow]",
            border_style="cyan",
        )
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir) / project_name

        _console.print("\n[bold]Step 1 — yggtools init[/bold]")
        _run_demo_init(project_dir, project_name)
        _console.print("  [green]✓[/green] Initialisation complete")

        _console.print("\n[bold]Step 2 — Generated file tree[/bold]")
        tree = Tree(f"[bold blue]{project_name}/[/bold blue]")
        _build_tree(project_dir, tree)
        _console.print(tree)

        _console.print("\n[bold]Step 3 — Key generated files[/bold]")
        _show_file(project_dir, "pyproject.toml")
        _show_file(project_dir, "Makefile")
        _show_file(project_dir, ".python-version")

        _console.print("\n[bold]Step 4 — yggtools check[/bold]")
        failed = _run_demo_check(project_dir)

        _console.print()
        if failed == 0:
            _console.print("[bold green]Demo complete — all checks passed.[/bold green]")
            return 0

        _console.print(f"[bold red]Demo finished with {failed} check failure(s).[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
