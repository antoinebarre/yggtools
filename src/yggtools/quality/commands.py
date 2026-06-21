"""Typer commands for the yggtools quality workflows."""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
from rich.console import Console

from yggtools.cli_support import resolve_report_dir
from yggtools.quality import display
from yggtools.quality.checks import format as format_checks
from yggtools.quality.checks import lint as lint_checks
from yggtools.quality.checks import metrics as metrics_checks
from yggtools.quality.checks import security as security_checks
from yggtools.quality.checks import tests as tests_checks
from yggtools.quality.checks import typecheck as typecheck_checks
from yggtools.quality.checks import version as version_checks
from yggtools.quality.checks import warnings as warning_checks
from yggtools.quality.pipeline import (
    STAGES,
    PipelineResult,
    _check_payload,
    _write_json,
    write_pipeline_artifacts,
)
from yggtools.quality.runner import CheckResult, registered_checks, run_one

_console = Console()
_err_console = Console(stderr=True)
_REGISTERED_CHECK_MODULES = (
    format_checks,
    lint_checks,
    metrics_checks,
    security_checks,
    tests_checks,
    typecheck_checks,
    version_checks,
    warning_checks,
)


def register(app: typer.Typer) -> None:
    """Register quality commands on the root Typer application.

    Args:
        app: Root Typer application.
    """
    app.command("pipeline")(pipeline_cmd)
    app.command("run")(run)


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

    Executes all quality stages in order, writes JSON artifacts with SHA-256
    digests, and prints a Rich dashboard.
    """
    project_dir = Path(path) if path else Path.cwd()
    output_dir = resolve_report_dir(project_dir, report_dir)

    _console.print()
    _console.print(
        f"[bold]yggtools pipeline[/bold] - [cyan]{project_dir.name}[/cyan]",
    )
    _console.print()

    result = run_pipeline_with_progress(project_dir)
    report = write_pipeline_artifacts(result, project_dir, output_dir)

    display.print_pipeline_dashboard(result, project_dir)
    display.print_objectives_table(result)
    display.print_artifact_table(report, project_dir)
    display.print_warning_details(result)
    display.print_failure_details(result)

    _console.print()
    if result.passed:
        _console.print("[bold green]All checks passed.[/bold green]")
    else:
        failed = sum(1 for item in result.results if not item.passed)
        _console.print(f"[bold red]{failed} check(s) failed.[/bold red]")
        raise typer.Exit(1)


def run_pipeline_with_progress(project_dir: Path) -> PipelineResult:
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
                icon = display.result_icon(result)
                _console.print(f"    {icon} {result.name}")
    elapsed = perf_counter() - started
    passed = all(item.passed for item in results)
    return PipelineResult(
        results=tuple(results),
        duration_seconds=elapsed,
        passed=passed,
    )


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

    Always writes JSON artifacts with SHA-256 digests. The ``--ci`` flag is
    accepted for backwards compatibility but has no effect.

    Args:
        check_name: Optional check name to run.
        all_checks: Whether to run every registered check.
        ci_mode: Compatibility flag retained as a no-op.
        path: Optional project directory.
        report_dir: Optional report output directory.
    """
    del ci_mode
    project_dir = Path(path) if path else Path.cwd()

    if not all_checks and check_name is None:
        _err_console.print(
            "[bold red]Error:[/bold red] Specify a check name or use --all.",
        )
        checks = ", ".join(registered_checks())
        _err_console.print(f"Available checks: {checks}")
        raise typer.Exit(1)

    results = run_requested_checks(
        check_name,
        all_checks=all_checks,
        project_dir=project_dir,
    )
    output_dir = resolve_report_dir(project_dir, report_dir)
    json_reports = write_check_reports(results, project_dir, output_dir)
    failed = sum(1 for item in results if not item.passed)

    display.print_run_summary(results, project_dir, json_reports)

    if failed:
        _console.print(f"\n[bold red]{failed} check(s) failed.[/bold red]")
        raise typer.Exit(1)
    _console.print("\n[bold green]All checks passed.[/bold green]")


def run_requested_checks(
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
        return [run_one(name, project_dir) for name in registered_checks()]
    requested_name = check_name or ""
    return [run_one(requested_name, project_dir)]


def write_check_reports(
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
