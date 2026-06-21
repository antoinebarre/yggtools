"""Command-line interface for yggtools."""

from __future__ import annotations

import re
from pathlib import Path
from time import perf_counter
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from yggtools.quality.checks import format as format_checks
from yggtools.quality.checks import lint as lint_checks
from yggtools.quality.checks import metrics as metrics_checks
from yggtools.quality.checks import security as security_checks
from yggtools.quality.checks import tests as tests_checks
from yggtools.quality.checks import typecheck as typecheck_checks
from yggtools.quality.checks import version as version_checks
from yggtools.quality.checks.version import (
    VersionArtifact,
    _collect_version_artifacts,
)
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
from yggtools.repo_init.pipeline import (
    STEPS,
    STEPS_INIT,
    STEPS_RESET,
    STEPS_RESET_AI,
    STEPS_RESET_CI,
    STEPS_RESET_SCRIPTS,
    PipelineStep,
)
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError, check_uv_available
from yggtools.versioning import VersionError, increase_project_version

app = typer.Typer(
    name="yggtools",
    help="Developer toolbox: scaffolding, quality pipeline.",
    no_args_is_help=True,
)
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
)


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
    _print_objectives_table(result)
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


def _print_objectives_table(result: PipelineResult) -> None:
    """Print a summary table of quality objectives and their status.

    Extracts key metrics from check results: lint error counts,
    type errors, complexity thresholds, coverage, and security
    findings.

    Args:
        result: Pipeline execution result.
    """
    results_by_name = {r.name: r for r in result.results}
    rows = _collect_objective_rows(results_by_name)
    if not rows:
        return

    table = Table(
        show_header=True,
        header_style="bold",
        show_lines=False,
    )
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


def _collect_objective_rows(
    results: dict[str, CheckResult],
) -> list[tuple[str, str, str, bool]]:
    """Build rows for the objectives table from check results.

    Args:
        results: Check results keyed by name.

    Returns:
        List of (label, value, target, passed) tuples.
    """
    rows: list[tuple[str, str, str, bool]] = []
    _add_lint_objectives(results, rows)
    _add_typecheck_objective(results, rows)
    _add_metrics_objectives(results, rows)
    _add_security_objectives(results, rows)
    _add_coverage_objective(results, rows)
    return rows


def _add_lint_objectives(
    results: dict[str, CheckResult],
    rows: list[tuple[str, str, str, bool]],
) -> None:
    """Add lint-related objective rows.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    for name, label in [
        ("format", "Formatting"),
        ("ruff", "Ruff errors"),
        ("flake8", "Flake8 violations"),
        ("version-consistency", "Version consistency"),
    ]:
        if name in results:
            r = results[name]
            rows.append((label, r.detail, "0", r.passed))


def _add_typecheck_objective(
    results: dict[str, CheckResult],
    rows: list[tuple[str, str, str, bool]],
) -> None:
    """Add the type checking objective row.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "typecheck" in results:
        r = results["typecheck"]
        count = r.metadata.get("error_count", 0)
        rows.append(("Type errors", str(count), "0", r.passed))


def _add_metrics_objectives(
    results: dict[str, CheckResult],
    rows: list[tuple[str, str, str, bool]],
) -> None:
    """Add metrics objective rows for CC and module size.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "metrics" not in results:
        return
    r = results["metrics"]
    summary = r.metadata.get("summary")
    thresholds = r.metadata.get("thresholds")
    if isinstance(summary, dict) and isinstance(thresholds, dict):
        max_cc = summary.get("max_cyclomatic_complexity", "?")
        cc_limit = thresholds.get("max_cyclomatic_complexity", "?")
        rows.append(
            (
                "Max cyclomatic complexity",
                str(max_cc),
                f"≤ {cc_limit}",
                int(str(max_cc)) <= int(str(cc_limit))
                if _is_int(max_cc, cc_limit)
                else r.passed,
            )
        )
        violations = summary.get("violations", 0)
        rows.append(
            (
                "Metrics violations",
                str(violations),
                "0",
                violations == 0,
            )
        )


def _add_security_objectives(
    results: dict[str, CheckResult],
    rows: list[tuple[str, str, str, bool]],
) -> None:
    """Add security objective rows.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "security-code" in results:
        r = results["security-code"]
        rows.append(("Security issues", r.detail, "0", r.passed))
    if "security-deps" in results:
        r = results["security-deps"]
        rows.append(("Dependency vulns", r.detail, "0", r.passed))


def _add_coverage_objective(
    results: dict[str, CheckResult],
    rows: list[tuple[str, str, str, bool]],
) -> None:
    """Add the test coverage objective row.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "tests" not in results:
        return
    r = results["tests"]
    cov_match = re.search(r"coverage\s+([\d.]+%)", r.detail)
    if cov_match:
        rows.append(
            (
                "Test coverage",
                cov_match.group(1),
                "100%",
                r.passed,
            )
        )
    rows.append(("Test suite", r.detail, "all pass", r.passed))


def _is_int(*values: object) -> bool:
    """Return True if all values can be converted to int.

    Args:
        *values: Values to check.

    Returns:
        True when every value is int-convertible.
    """
    try:
        for v in values:
            int(str(v))
    except (ValueError, TypeError):
        return False
    return True


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
            digest,
        )
    if report.summary_path:
        table.add_row(
            _relative_to_project(report.summary_path, project_dir),
            report.summary_digest,
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

    Designed to be run after ``uv init`` or ``uv init --lib``.  Ensures a
    ``src/<package>/`` layout exists, adds yggtools and quality tools as
    dev dependencies, patches ``pyproject.toml``, writes a ``Makefile`` and
    ``CLAUDE.md``, creates ``tests/`` and ``work/``, and generates CI
    workflows.

    Exits with code 1 if ``pyproject.toml`` is absent in the current
    directory.
    """
    cwd = Path.cwd()

    if not (cwd / "pyproject.toml").exists():
        _err_console.print(
            "[bold red]Error:[/bold red] No pyproject.toml found in the "
            "current directory. Run ``uv init PROJECT_NAME`` first.",
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


@app.command("reset")
def reset_cmd(
    only: Annotated[
        str | None,
        typer.Option(
            "--only",
            help="Subset to reset: all, ai, ci, or scripts.",
        ),
    ] = None,
    python: Annotated[
        str | None,
        typer.Option(
            "--python",
            help=(
                "Target Python version for CI "
                "(default: .python-version or 3.12)."
            ),
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Show what would be reset without writing anything.",
        ),
    ] = False,
) -> None:
    """Restore yggtools-generated files in the current repository.

    Rewrites only the generated AI instructions, CI workflows, and Makefile.
    It does not touch dependencies, ``pyproject.toml``, source files, tests,
    or git history.
    """
    cwd = Path.cwd()
    if not (cwd / "pyproject.toml").exists():
        _err_console.print(
            "[bold red]Error:[/bold red] No pyproject.toml found in the "
            "current directory.",
        )
        raise typer.Exit(1)

    steps = _reset_steps(only)
    if steps is None:
        _err_console.print(
            "[bold red]Error:[/bold red] --only must be one of: "
            "all, ai, ci, scripts.",
        )
        raise typer.Exit(1)

    python_version = python or _read_python_version(cwd)
    ctx = RepoContext(
        project_name=cwd.name,
        python_version=python_version,
        parent_dir=cwd.parent,
        dry_run=dry_run,
    )

    if dry_run:
        _print_reset_dry_run_plan(ctx, steps)
        return

    _console.print(
        "[bold]Resetting yggtools files[/bold] — "
        f"[cyan]{ctx.project_name}[/cyan]"
    )
    try:
        _run_with_progress(ctx, steps=steps)
    except StepError as exc:
        _err_console.print(f"\n[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc
    except Exception as exc:
        _err_console.print(f"\n[bold red]Unexpected error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    _console.print()
    _console.print("[bold green]Generated files restored.[/bold green]")


# ── increase-version command ─────────────────────────────────────────────


@app.command("increase-version")
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
    """Increase package version across all managed artifacts."""
    project_dir = Path(path) if path else Path.cwd()
    try:
        update = increase_project_version(project_dir, level)
    except VersionError as exc:
        _err_console.print(f"[bold red]Error:[/bold red] {exc}")
        raise typer.Exit(1) from exc

    _console.print(
        "[bold green]Version increased[/bold green] "
        f"[cyan]{update.project_name}[/cyan]: "
        f"{update.old_version} → {update.new_version}",
    )
    for file_path in update.files:
        relative_path = _relative_to_project(file_path, project_dir)
        _console.print(f"  [green]✓[/green] {relative_path}")
    _console.print("  [green]✓[/green] uv lock")


# ── version command ──────────────────────────────────────────────────────


@app.command("version")
def version_cmd(
    path: Annotated[
        str | None,
        typer.Option("--path", help="Project directory (default: cwd)."),
    ] = None,
) -> None:
    """List package versions found in managed artifacts."""
    project_dir = Path(path) if path else Path.cwd()
    artifacts = _collect_version_artifacts(project_dir)
    missing = [a for a in artifacts if a.required and a.version is None]
    versions = {a.version for a in artifacts if a.version is not None}
    passed = not missing and len(versions) <= 1

    _print_version_artifacts_table(artifacts, project_dir)
    if passed:
        version = next(iter(versions), "unknown")
        _console.print(
            f"\n[bold green]Version consistent:[/bold green] {version}"
        )
        return

    _console.print("\n[bold red]Version mismatch detected.[/bold red]")
    raise typer.Exit(1)


# ── helpers ──────────────────────────────────────────────────────────────


def _print_version_artifacts_table(
    artifacts: list[VersionArtifact],
    project_dir: Path,
) -> None:
    """Print a table of discovered package version artifacts.

    Args:
        artifacts: Version artifacts to display.
        project_dir: Project root directory.
    """
    table = Table(
        show_header=True,
        header_style="bold",
        show_lines=False,
    )
    table.add_column("Artifact", style="bold")
    table.add_column("Path")
    table.add_column("Version", justify="right")
    table.add_column("Required", justify="center")

    for artifact in artifacts:
        version = artifact.version if artifact.version is not None else "-"
        required = "yes" if artifact.required else "no"
        table.add_row(
            artifact.name,
            _relative_to_project(artifact.path, project_dir),
            version,
            required,
        )

    _console.print(Panel(table, title="[bold]Package versions[/bold]"))


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
        "ensure src/<package>/__init__.py with __version__",
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


def _reset_steps(only: str | None) -> list[PipelineStep] | None:
    """Return reset steps for the requested subset.

    Args:
        only: Optional subset name from the CLI.

    Returns:
        The matching reset steps, or None for an invalid subset.
    """
    normalized = (only or "all").lower()
    groups = {
        "all": STEPS_RESET,
        "ai": STEPS_RESET_AI,
        "ci": STEPS_RESET_CI,
        "scripts": STEPS_RESET_SCRIPTS,
    }
    return groups.get(normalized)


def _read_python_version(project_dir: Path) -> str:
    """Read the project's Python version for generated CI files.

    Args:
        project_dir: Project root directory.

    Returns:
        The .python-version content, or the yggtools default.
    """
    python_version = project_dir / ".python-version"
    if not python_version.exists():
        return "3.12"
    content = python_version.read_text(encoding="utf-8").strip()
    return content or "3.12"


def _print_reset_dry_run_plan(
    ctx: RepoContext,
    steps: list[PipelineStep],
) -> None:
    """Print the list of reset actions without writing files.

    Args:
        ctx: Pipeline context.
        steps: Reset steps selected by the CLI.
    """
    _console.print(
        "[bold yellow]Dry run — nothing will be written[/bold yellow]",
    )
    _console.print(
        f"Project: [cyan]{ctx.project_name}[/cyan] → {ctx.project_dir}",
    )
    for step in steps:
        _console.print(f"  [dim]would:[/dim] {step.name}")


def main() -> None:  # pragma: no cover
    """Entry point for the yggtools CLI application."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
