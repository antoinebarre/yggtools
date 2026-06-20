"""Command-line interface for yggtools."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

import yggtools.quality.checks.format
import yggtools.quality.checks.lint
import yggtools.quality.checks.metrics
import yggtools.quality.checks.security
import yggtools.quality.checks.tests
import yggtools.quality.checks.typecheck  # noqa: F401
from yggtools.quality.report import write_check_json_reports
from yggtools.quality.runner import (
    CheckResult,
    registered_checks,
    run_all,
    run_one,
)
from yggtools.repo_init.pipeline import STEPS, STEPS_INIT, PipelineStep
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError, check_uv_available

app = typer.Typer(
    name="yggtools",
    help="Developer toolbox: scaffolding, quality pipeline, and more.",
    no_args_is_help=True,
)
_console = Console()
_err_console = Console(stderr=True)


@app.command("init-repo")
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

    Calls ``uv init --lib``, adds yggtools and quality tools as dev
    dependencies, patches ``pyproject.toml``, writes a ``Makefile``,
    creates ``tests/`` and ``work/``, and generates CI workflows.
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
        _print_dry_run_plan(ctx, include_uv_init=True)
        return

    try:
        check_uv_available()
    except UvNotFoundError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    _console.print(
        f"[bold]Initialising[/bold] [cyan]{ctx.project_name}[/cyan] "
        f"(Python {ctx.python_version})",
    )
    try:
        _run_with_progress(ctx, steps=STEPS)
    except StepError as exc:
        _err_console.print(f"\n[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        _err_console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    _console.print()
    _console.print("[bold green]Project ready.[/bold green]")
    _console.print()
    _console.print("Next steps:")
    _console.print(f"  cd {ctx.project_name}")
    _console.print("  make check    [dim]# full quality pipeline[/dim]")
    _console.print("  make test     [dim]# tests only[/dim]")
    _console.print("  make format   [dim]# auto-format source[/dim]")


@app.command("init")
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

    Designed to be run after ``uv init --lib``.  Adds yggtools and quality
    tools as dev dependencies, patches ``pyproject.toml``, writes a
    ``Makefile`` and ``CLAUDE.md``, creates ``tests/`` and ``work/``, and
    generates CI workflows.

    Exits with code 1 if ``pyproject.toml`` is absent in the current
    directory.
    """
    cwd = Path.cwd()

    if not (cwd / "pyproject.toml").exists():
        _err_console.print(
            "[bold red]Error:[/bold red] No pyproject.toml found in the "
            "current directory. Run ``uv init --lib PROJECT_NAME`` first.",
        )
        raise typer.Exit(1)

    project_name = cwd.name
    ctx = RepoContext(
        project_name=project_name,
        python_version=python,
        parent_dir=cwd.parent,
        no_git=no_git,
        dry_run=dry_run,
    )

    if dry_run:
        _print_dry_run_plan(ctx, include_uv_init=False)
        return

    try:
        check_uv_available()
    except UvNotFoundError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    _console.print(
        f"[bold]Initialising[/bold] [cyan]{ctx.project_name}[/cyan] "
        f"(Python {ctx.python_version})",
    )
    try:
        _run_with_progress(ctx, steps=STEPS_INIT)
    except StepError as exc:
        _err_console.print(f"\n[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        _err_console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    _console.print()
    _console.print("[bold green]Project ready.[/bold green]")
    _console.print()
    _console.print("Next steps:")
    _console.print("  make check    [dim]# full quality pipeline[/dim]")
    _console.print("  make test     [dim]# tests only[/dim]")


@app.command("run")
def run(
    check_name: Annotated[
        str | None,
        typer.Argument(
            help="Name of the check to run (e.g. 'format', 'tests').",
        ),
    ] = None,
    all_checks: Annotated[
        bool,
        typer.Option("--all", help="Run all registered checks."),
    ] = False,
    ci_mode: Annotated[
        bool,
        typer.Option("--ci", help="CI mode: write work/report.md."),
    ] = False,
    path: Annotated[
        str | None,
        typer.Option("--path", help="Project directory (default: cwd)."),
    ] = None,
    report_dir: Annotated[
        str | None,
        typer.Option(
            "--report-dir",
            help="Directory for per-check CI JSON contracts.",
        ),
    ] = None,
) -> None:
    """Run one or all quality checks in the current project.

    In CI mode (``--ci``), writes JSON contracts to ``work/ci/results``
    and exits with code 1 if any check fails.
    """
    project_dir = Path(path) if path else Path.cwd()

    if not all_checks and check_name is None:
        _err_console.print(
            "[bold red]Error:[/bold red] Specify a check name or use --all.",
        )
        _err_console.print(
            f"Available checks: {', '.join(registered_checks())}",
        )
        raise typer.Exit(1)

    results = _run_requested_checks(
        check_name,
        all_checks=all_checks,
        project_dir=project_dir,
    )
    json_reports = (
        _write_ci_reports(results, project_dir, report_dir) if ci_mode else {}
    )
    failed = sum(1 for result in results if not result.passed)

    _print_run_summary(results, project_dir, json_reports)

    if failed:
        _console.print(f"\n[bold red]{failed} check(s) failed.[/bold red]")
        raise typer.Exit(1)
    _console.print("\n[bold green]All checks passed.[/bold green]")


def _run_requested_checks(
    check_name: str | None,
    *,
    all_checks: bool,
    project_dir: Path,
) -> list[CheckResult]:
    """Run the requested checks."""
    if all_checks:
        return run_all(project_dir)
    return [run_one(check_name, project_dir)]  # type: ignore[arg-type]


def _print_run_summary(
    results: list[CheckResult],
    project_dir: Path,
    json_reports: dict[str, tuple[Path, str]],
) -> None:
    """Print a compact summary for local and CI runs."""
    _console.print(f"[bold]yggtools run[/bold] {project_dir.name}")
    for result in results:
        _console.print(_result_summary_line(result))
        if result.name in json_reports:
            path, digest = json_reports[result.name]
            _console.print(
                f"  json: {_relative_to_project(path, project_dir)}",
            )
            _console.print(f"  sha256: {digest}")
        if not result.passed:
            _print_failure_context(result)


def _result_summary_line(result: CheckResult) -> str:
    """Build the concise console line for one result."""
    status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
    duration = (
        f"{result.duration_seconds:.2f}s"
        if result.duration_seconds is not None
        else "-"
    )
    return (
        f"- {status} [bold]{result.name}[/bold] ({duration}) - {result.detail}"
    )


def _print_failure_context(result: CheckResult) -> None:
    """Print short failure context without flooding CI logs."""
    context = _tail(result.stderr or result.stdout, max_lines=8)
    if context:
        _console.print("  context:")
        for line in context.splitlines():
            _console.print(f"    {line}")


def _relative_to_project(path: Path, project_dir: Path) -> str:
    """Return a display path relative to the project when possible."""
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _resolve_report_dir(project_dir: Path, report_dir: str | None) -> Path:
    """Resolve the per-check report directory."""
    if report_dir is None:
        return project_dir / "work" / "ci" / "results"
    requested_report_dir = Path(report_dir)
    if requested_report_dir.is_absolute():
        return requested_report_dir
    return project_dir / requested_report_dir


def _write_ci_reports(
    results: list[CheckResult],
    project_dir: Path,
    report_dir: str | None,
) -> dict[str, tuple[Path, str]]:
    """Write per-check CI JSON contracts."""
    output_dir = _resolve_report_dir(project_dir, report_dir)
    return write_check_json_reports(results, project_dir, output_dir)


def _tail(text: str, *, max_lines: int = 20) -> str:
    """Return the last lines of captured output for console display."""
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:])


def _run_with_progress(
    ctx: RepoContext,
    steps: list[PipelineStep] | None = None,
) -> None:
    """Execute a pipeline and print a progress line per step.

    Args:
        ctx: Pipeline context passed to each step.
        steps: List of PipelineStep to execute.  Defaults to ``STEPS``.

    Raises:
        StepError: Propagated from any failing step.
    """
    active_steps = steps if steps is not None else STEPS
    for step in active_steps:
        step.fn(ctx)
        _console.print(f"  [green]✓[/green] {step.name}")


def _print_dry_run_plan(
    ctx: RepoContext,
    *,
    include_uv_init: bool = True,
) -> None:
    """Print the list of actions the init pipeline would perform.

    Args:
        ctx: Pipeline context.
        include_uv_init: When True, include the ``uv init --lib`` step in
            the printed plan (used by ``init-repo``).  When False, omit it
            (used by ``init``).
    """
    _console.print(
        "[bold yellow]Dry run — nothing will be written[/bold yellow]",
    )
    _console.print(
        f"Project: [cyan]{ctx.project_name}[/cyan] → {ctx.project_dir}",
    )
    actions: list[str] = []
    if include_uv_init:
        actions.append(
            f"uv init --lib {ctx.project_name} --python {ctx.python_version}",
        )
    actions += [
        "uv add --dev yggtools + quality tools",
        "patch pyproject.toml ([tool.ruff], [tool.mypy], …)",
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
    for action in actions:
        _console.print(f"  [dim]would:[/dim] {action}")


def main() -> None:  # pragma: no cover
    """Entry point for the yggtools CLI application."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
