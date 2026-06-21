"""Rich console rendering for quality commands."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from yggtools.cli_support import relative_to_project, short_text, tail
from yggtools.quality.objectives import collect_objective_rows
from yggtools.quality.pipeline import PipelineReport, PipelineResult
from yggtools.quality.runner import CheckResult

_console = Console()


def print_pipeline_dashboard(
    result: PipelineResult,
    project_dir: Path,
) -> None:
    """Print the summary Rich table after pipeline execution.

    Args:
        result: Pipeline execution result.
        project_dir: Project root directory.
    """
    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("Check", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Duration", justify="right")
    table.add_column("Detail")

    for check_result in result.results:
        _add_dashboard_row(table, check_result)

    passed = sum(1 for item in result.results if item.passed)
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
            title=f"[bold]yggtools pipeline - {project_dir.name}[/bold]",
            subtitle=footer,
            border_style="green" if result.passed else "red",
        ),
    )


def _add_dashboard_row(table: Table, result: CheckResult) -> None:
    """Add one check row to the pipeline dashboard.

    Args:
        table: Rich table to mutate.
        result: Check result to display.
    """
    status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
    duration = (
        f"{result.duration_seconds:.2f}s"
        if result.duration_seconds is not None
        else "-"
    )
    table.add_row(result.name, status, duration, result.detail)


def print_objectives_table(result: PipelineResult) -> None:
    """Print a summary table of quality objectives and their status.

    Args:
        result: Pipeline execution result.
    """
    results_by_name = {item.name: item for item in result.results}
    rows = collect_objective_rows(results_by_name)
    if not rows:
        return

    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("Objective")
    table.add_column("Value", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Status", justify="center")

    for label, value, target, passed in rows:
        status = "[green]OK[/green]" if passed else "[red]KO[/red]"
        table.add_row(label, value, target, status)

    _console.print()
    _console.print(
        Panel(table, title="[bold]Objectives[/bold]", border_style="dim"),
    )


def print_artifact_table(report: PipelineReport, project_dir: Path) -> None:
    """Print the artifacts Rich table with paths and SHA-256 digests.

    Args:
        report: Pipeline artifact report.
        project_dir: Project root directory.
    """
    table = Table(show_header=True, header_style="bold", show_lines=False)
    table.add_column("File")
    table.add_column("SHA-256")

    for artifact_path, digest in report.check_reports.values():
        table.add_row(relative_to_project(artifact_path, project_dir), digest)
    if report.summary_path:
        table.add_row(
            relative_to_project(report.summary_path, project_dir),
            report.summary_digest,
        )

    reports_dir = (
        relative_to_project(report.summary_path.parent, project_dir)
        if report.summary_path
        else "work/reports/"
    )
    _console.print()
    _console.print(
        Panel(
            table,
            title=f"[bold]Artifacts - {reports_dir}[/bold]",
            border_style="dim",
        ),
    )


def print_failure_details(result: PipelineResult) -> None:
    """Print detailed failure context for each failed check.

    Args:
        result: Pipeline execution result.
    """
    failed = [item for item in result.results if not item.passed]
    if not failed:
        return

    _console.print()
    _console.print("[bold red]Failure details[/bold red]")
    for check_result in failed:
        _console.print(f"\n  [bold]{check_result.name}[/bold]")
        if check_result.command:
            _console.print(f"  command: {' '.join(check_result.command)}")
        context = tail(check_result.stderr or check_result.stdout)
        if context:
            for line in context.splitlines():
                _console.print(f"    {line}")


def print_run_summary(
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
        _console.print(result_summary_line(result))
        print_result_context(result)
        if result.name in json_reports:
            path, digest = json_reports[result.name]
            _console.print(f"  json: {relative_to_project(path, project_dir)}")
            _console.print(f"  sha256: {digest}")
        if not result.passed:
            print_run_failure_context(result)


def result_summary_line(result: CheckResult) -> str:
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


def print_run_failure_context(result: CheckResult) -> None:
    """Print short failure context without flooding CI logs.

    Args:
        result: Failed check result.
    """
    context = tail(result.stderr or result.stdout, max_lines=8)
    if context:
        _console.print("  context:")
        for line in context.splitlines():
            _console.print(f"    {line}")


def print_result_context(result: CheckResult) -> None:
    """Print useful structured context without dumping raw data.

    Args:
        result: Single check result.
    """
    if result.command:
        _console.print(f"  command: {' '.join(result.command)}")
    summary = result.metadata.get("summary")
    if isinstance(summary, dict):
        _console.print(f"  summary: {format_summary(summary)}")
    top = result.metadata.get("top_complex_functions")
    if isinstance(top, list) and top:
        _console.print(f"  top: {format_top_item(top[0])}")


def format_summary(summary: dict[object, object]) -> str:
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


def format_top_item(item: object) -> str:
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
    short_path = short_text(str(path), 28)
    short_name = short_text(str(name), 36)
    return f"CC={cc} {short_path}:{line} {short_name}"
