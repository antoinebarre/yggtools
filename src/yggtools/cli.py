"""Command-line interface for yggtools."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import yggtools.quality.checks.format
import yggtools.quality.checks.lint
import yggtools.quality.checks.metrics
import yggtools.quality.checks.security
import yggtools.quality.checks.tests
import yggtools.quality.checks.typecheck  # noqa: F401
from yggtools.quality.pipeline import (
    STAGES,
    PipelineReport,
    PipelineResult,
    _check_payload,
    _write_json,
    write_pipeline_artifacts,
)
from yggtools.quality.runner import (
    CheckResult,
    registered_checks,
    run_one,
)
from yggtools.repo_init.pipeline import STEPS, STEPS_INIT, PipelineStep
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError, check_uv_available

app = typer.Typer(
    name="yggtools",
    help="Developer toolbox: scaffolding, quality pipeline.",
    no_args_is_help=True,
)
_console = Console()
_err_console = Console(stderr=True)


# ── pipeline command ─────────────────────────────────────────────────────


@app.command("pipeline")
def pipeline_cmd(
    path: Annotated[
        str | None,
        typer.Option("--path", help="Project directory (default: cwd)."),
    ] = None,
    report_dir: Annotated[
        str | None,
        typer.Option(
            "--report-dir",
            help="Directory for artifacts (default: work/reports/).",
        ),
    ] = None,
) -> None:
    """Run the full quality pipeline and produce artifacts.

    Executes all quality stages in order (linters, type checking,
    metrics, security, tests), writes JSON artifacts with SHA-256
    digests, and prints a Rich dashboard.
    """
    project_dir = Path(path) if path else Path.cwd()
    output_dir = _resolve_report_dir(project_dir, report_dir)

    _console.print()
    _console.print(
        f"[bold]yggtools pipeline[/bold] — [cyan]{project_dir.name}[/cyan]",
    )
    _console.print()

    result = _run_pipeline_with_progress(project_dir)
    report = write_pipeline_artifacts(result, project_dir, output_dir)

    _print_pipeline_dashboard(result, project_dir)
    _print_artifact_table(report, project_dir)
    _print_failure_details(result)

    _console.print()
    if result.passed:
        _console.print("[bold green]All checks passed.[/bold green]")
    else:
        failed = sum(1 for r in result.results if not r.passed)
        _console.print(
            f"[bold red]{failed} check(s) failed.[/bold red]",
        )
        raise typer.Exit(1)


def _run_pipeline_with_progress(project_dir: Path) -> PipelineResult:
    """Run the pipeline while printing per-check progress lines.

    Args:
        project_dir: Project root directory.

    Returns:
        Complete pipeline result.
    """
    started = perf_counter()
    results: list[CheckResult] = []
    for stage in STAGES:
        _console.print(f"  [dim]{stage.name}[/dim]")
        for check_name in stage.checks:
            if check_name in registered_checks():
                result = run_one(check_name, project_dir)
                results.append(result)
                icon = "[green]✓[/green]" if result.passed else "[red]✗[/red]"
                _console.print(f"    {icon} {result.name}")
    elapsed = perf_counter() - started
    passed = all(r.passed for r in results)
    return PipelineResult(
        results=tuple(results),
        duration_seconds=elapsed,
        passed=passed,
    )


def _print_pipeline_dashboard(
    result: PipelineResult,
    project_dir: Path,
) -> None:
    """Print the summary Rich table after pipeline execution.

    Args:
        result: Pipeline execution result.
        project_dir: Project root directory.
    """
    table = Table(
        show_header=True,
        header_style="bold",
        show_lines=False,
    )
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Detail")

    for check_result in result.results:
        status = (
            "[green]PASS[/green]" if check_result.passed else "[red]FAIL[/red]"
        )
        duration = (
            f"{check_result.duration_seconds:.2f}s"
            if check_result.duration_seconds is not None
            else "-"
        )
        table.add_row(
            check_result.name,
            status,
            duration,
            check_result.detail,
        )

    passed = sum(1 for r in result.results if r.passed)
    total = len(result.results)
    footer = (
        f"{passed}/{total} passed"
        f"{'  ' * 20}"
        f"Total {result.duration_seconds:.2f}s"
    )

    _console.print()
    _console.print(
        Panel(
            table,
            title=f"[bold]yggtools pipeline — {project_dir.name}[/bold]",
            subtitle=footer,
            border_style="green" if result.passed else "red",
        ),
    )


def _print_artifact_table(
    report: PipelineReport,
    project_dir: Path,
) -> None:
    """Print the artifacts Rich table with paths and SHA-256 digests.

    Args:
        report: Pipeline artifact report.
        project_dir: Project root directory.
    """
    table = Table(
        show_header=True,
        header_style="bold",
        show_lines=False,
    )
    table.add_column("File")
    table.add_column("SHA-256")

    for artifact_path, digest in report.check_reports.values():
        table.add_row(
            _relative_to_project(artifact_path, project_dir),
            digest[:16] + "…",
        )
    if report.summary_path:
        table.add_row(
            _relative_to_project(report.summary_path, project_dir),
            report.summary_digest[:16] + "…",
        )

    reports_dir = (
        _relative_to_project(report.summary_path.parent, project_dir)
        if report.summary_path
        else "work/reports/"
    )
    _console.print()
    _console.print(
        Panel(
            table,
            title=f"[bold]Artifacts — {reports_dir}[/bold]",
            border_style="dim",
        ),
    )


def _print_failure_details(result: PipelineResult) -> None:
    """Print detailed failure context for each failed check.

    Args:
        result: Pipeline execution result.
    """
    failed = [r for r in result.results if not r.passed]
    if not failed:
        return

    _console.print()
    _console.print("[bold red]Failure details[/bold red]")
    for check_result in failed:
        _console.print(f"\n  [bold]{check_result.name}[/bold]")
        if check_result.command:
            _console.print(
                f"  command: {' '.join(check_result.command)}",
            )
        context = _tail(check_result.stderr or check_result.stdout)
        if context:
            for line in context.splitlines():
                _console.print(f"    {line}")


# ── run command (single check) ───────────────────────────────────────────


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
        typer.Option("--ci", help="Deprecated, kept for compatibility."),
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

    Always writes JSON artifacts with SHA-256 digests.  The ``--ci``
    flag is accepted for backwards compatibility but has no effect.
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
    output_dir = _resolve_report_dir(project_dir, report_dir)
    json_reports = _write_check_reports(results, project_dir, output_dir)
    failed = sum(1 for r in results if not r.passed)

    _print_run_summary(results, project_dir, json_reports)

    if failed:
        _console.print(f"\n[bold red]{failed} check(s) failed.[/bold red]")
        raise typer.Exit(1)
    _console.print("\n[bold green]All checks passed.[/bold green]")


# ── init-repo / init commands ────────────────────────────────────────────


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


# ── helpers ──────────────────────────────────────────────────────────────


def _run_requested_checks(
    check_name: str | None,
    *,
    all_checks: bool,
    project_dir: Path,
) -> list[CheckResult]:
    """Run the requested checks.

    Args:
        check_name: Single check name, or None when all_checks is True.
        all_checks: When True, run all registered checks.
        project_dir: Project root directory.

    Returns:
        List of check results.
    """
    if all_checks:
        return [run_one(n, project_dir) for n in registered_checks()]
    return [run_one(check_name, project_dir)]  # type: ignore[arg-type]


def _write_check_reports(
    results: list[CheckResult],
    project_dir: Path,
    output_dir: Path,
) -> dict[str, tuple[Path, str]]:
    """Write per-check JSON artifacts.

    Args:
        results: Check results to serialise.
        project_dir: Project root directory.
        output_dir: Destination directory.

    Returns:
        Mapping of check name to (path, sha256) pairs.
    """
    reports: dict[str, tuple[Path, str]] = {}
    for result in results:
        artifact_path = output_dir / f"{result.name}.json"
        payload = _check_payload(result, project_dir)
        digest = _write_json(payload, artifact_path)
        reports[result.name] = (artifact_path, digest)
    return reports


def _print_run_summary(
    results: list[CheckResult],
    project_dir: Path,
    json_reports: dict[str, tuple[Path, str]],
) -> None:
    """Print a compact summary for the run command.

    Args:
        results: Ordered check results.
        project_dir: Project root directory.
        json_reports: Artifact paths and digests.
    """
    _console.print(f"[bold]yggtools run[/bold] {project_dir.name}")
    for result in results:
        _console.print(_result_summary_line(result))
        _print_result_context(result)
        if result.name in json_reports:
            path, digest = json_reports[result.name]
            _console.print(
                f"  json: {_relative_to_project(path, project_dir)}",
            )
            _console.print(f"  sha256: {digest}")
        if not result.passed:
            _print_run_failure_context(result)


def _result_summary_line(result: CheckResult) -> str:
    """Build the concise console line for one result.

    Args:
        result: Single check result.

    Returns:
        Formatted summary string with Rich markup.
    """
    status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
    duration = (
        f"{result.duration_seconds:.2f}s"
        if result.duration_seconds is not None
        else "-"
    )
    return (
        f"- {status} [bold]{result.name}[/bold] ({duration}) - {result.detail}"
    )


def _print_run_failure_context(result: CheckResult) -> None:
    """Print short failure context without flooding CI logs.

    Args:
        result: Failed check result.
    """
    context = _tail(result.stderr or result.stdout, max_lines=8)
    if context:
        _console.print("  context:")
        for line in context.splitlines():
            _console.print(f"    {line}")


def _print_result_context(result: CheckResult) -> None:
    """Print useful structured context without dumping raw data.

    Args:
        result: Single check result.
    """
    if result.command:
        _console.print(f"  command: {' '.join(result.command)}")
    summary = result.metadata.get("summary")
    if isinstance(summary, dict):
        _console.print(f"  summary: {_format_summary(summary)}")
    top = result.metadata.get("top_complex_functions")
    if isinstance(top, list) and top:
        _console.print(f"  top: {_format_top_item(top[0])}")


def _format_summary(summary: dict[object, object]) -> str:
    """Format known summary keys for console display.

    Args:
        summary: Metrics summary dictionary.

    Returns:
        Comma-separated key=value string.
    """
    keys = (
        "python_files_parsed",
        "total_logical_lines",
        "total_functions",
        "total_classes",
        "max_cyclomatic_complexity",
        "violations",
    )
    labels = {
        "python_files_parsed": "files",
        "total_logical_lines": "LL",
        "total_functions": "fn",
        "total_classes": "classes",
        "max_cyclomatic_complexity": "max CC",
        "violations": "violations",
    }
    parts = [f"{labels[key]}={summary[key]}" for key in keys if key in summary]
    return ", ".join(parts)


def _format_top_item(item: object) -> str:
    """Format the first ranked metadata item for console display.

    Args:
        item: Top-ranked function metadata.

    Returns:
        Formatted string with CC, path, line, and name.
    """
    if not isinstance(item, dict):
        return str(item)
    path = item.get("path", "?")
    name = item.get("name", "?")
    cc = item.get("cyclomatic_complexity", "?")
    line = item.get("line", "?")
    short_path = _short_text(str(path), 28)
    short_name = _short_text(str(name), 36)
    return f"CC={cc} {short_path}:{line} {short_name}"


def _short_text(value: str, limit: int) -> str:
    """Shorten a console field while keeping it recognizable.

    Args:
        value: Text to shorten.
        limit: Maximum character length.

    Returns:
        Shortened string with trailing ellipsis if truncated.
    """
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def _relative_to_project(path: Path, project_dir: Path) -> str:
    """Return a display path relative to the project when possible.

    Args:
        path: Absolute or relative path.
        project_dir: Project root directory.

    Returns:
        Relative path string.
    """
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _resolve_report_dir(project_dir: Path, report_dir: str | None) -> Path:
    """Resolve the artifact output directory.

    Args:
        project_dir: Project root directory.
        report_dir: Optional user-specified directory.

    Returns:
        Resolved absolute path for artifact output.
    """
    if report_dir is None:
        return project_dir / "work" / "reports"
    requested = Path(report_dir)
    if requested.is_absolute():
        return requested
    return project_dir / requested


def _tail(text: str, *, max_lines: int = 20) -> str:
    """Return the last lines of captured output for console display.

    Args:
        text: Raw captured output.
        max_lines: Maximum lines to return.

    Returns:
        Trimmed text with blank lines removed.
    """
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
