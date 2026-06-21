"""Unit tests for yggtools.cli."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from rich.console import Console
from typer.testing import CliRunner

from yggtools.cli import app
from yggtools.quality.display import (
    print_artifact_table,
    print_objectives_table,
    print_result_context,
    print_run_summary,
    print_warning_details,
    result_icon,
    result_status_label,
    warning_finding_lines,
)
from yggtools.quality.objectives import collect_objective_rows, is_int
from yggtools.quality.pipeline import PipelineReport, PipelineResult
from yggtools.quality.runner import _REGISTRY, CheckFn, CheckResult
from yggtools.repo_init.commands import (
    read_python_version,
    reset_steps,
    run_with_progress,
)
from yggtools.repo_init.pipeline import (
    STEPS_INIT,
    STEPS_RESET_AI,
    STEPS_RESET_CI,
    PipelineStep,
)
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError
from yggtools.versioning import VersionError

_runner = CliRunner()


def _dummy_result(
    name: str = "dummy",
    *,
    passed: bool = True,
) -> CheckResult:
    """Build a minimal CheckResult for testing.

    Args:
        name: Check name.
        passed: Whether the check passed.

    Returns:
        CheckResult stub.
    """
    return CheckResult(
        name=name,
        passed=passed,
        detail="ok" if passed else "bad",
        duration_seconds=0.1,
    )


class TestPipelineCommand:
    """Tests for the pipeline command."""

    def test_exits_0_when_all_pass(self, tmp_path: Path) -> None:
        """Requirement: pipeline must exit 0 when all checks pass."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        try:
            result = _runner.invoke(
                app,
                ["pipeline", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 0
        assert "PASS" in result.output

    def test_exits_1_when_any_fails(self, tmp_path: Path) -> None:
        """Requirement: pipeline must exit 1 when any check fails."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format", passed=False),
        )
        try:
            result = _runner.invoke(
                app,
                ["pipeline", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_writes_artifacts(self, tmp_path: Path) -> None:
        """Requirement: pipeline must write JSON artifacts."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        try:
            _runner.invoke(
                app,
                ["pipeline", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        reports = tmp_path / "work" / "reports"
        assert (reports / "format.json").exists()
        assert (reports / "pipeline.json").exists()

    def test_artifact_table_prints_full_checksums(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: artifact table must show full SHA-256 digests."""
        check_digest = "a" * 64
        summary_digest = "b" * 64
        report = PipelineReport(
            check_reports={
                "format": (
                    tmp_path / "work" / "reports" / "format.json",
                    check_digest,
                ),
            },
            summary_path=tmp_path / "work" / "reports" / "pipeline.json",
            summary_digest=summary_digest,
        )
        console = Console(record=True, width=160)
        with patch("yggtools.quality.display._console", console):
            print_artifact_table(report, tmp_path)
        printed = console.export_text()
        assert check_digest in printed
        assert summary_digest in printed
        assert "..." not in printed

    def test_custom_report_dir(self, tmp_path: Path) -> None:
        """Requirement: --report-dir overrides artifact location."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        try:
            _runner.invoke(
                app,
                [
                    "pipeline",
                    "--path",
                    str(tmp_path),
                    "--report-dir",
                    "custom",
                ],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert (tmp_path / "custom" / "format.json").exists()

    def test_failure_details_show_command_and_context(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: failure details must show command and stderr."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: CheckResult(
                name="format",
                passed=False,
                detail="bad",
                command=("uv", "run", "ruff"),
                stderr="error line 1\nerror line 2",
                duration_seconds=0.1,
            ),
        )
        try:
            result = _runner.invoke(
                app,
                ["pipeline", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 1
        assert "uv run ruff" in result.output
        assert "error line" in result.output

    def test_output_shows_progress_and_dashboard(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: pipeline output must show stage and check."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        try:
            result = _runner.invoke(
                app,
                ["pipeline", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert "Linters" in result.output
        assert "format" in result.output

    def test_pipeline_shows_objectives_table(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: pipeline must show objectives table."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        _REGISTRY["tests"] = cast(
            "CheckFn",
            lambda _p: CheckResult(
                name="tests",
                passed=True,
                detail="10 passed · coverage 100.00%",
                duration_seconds=0.1,
            ),
        )
        _REGISTRY["metrics"] = cast(
            "CheckFn",
            lambda _p: CheckResult(
                name="metrics",
                passed=True,
                detail="pass",
                duration_seconds=0.1,
                metadata={
                    "summary": {
                        "max_cyclomatic_complexity": 5,
                        "violations": 0,
                    },
                    "thresholds": {
                        "max_cyclomatic_complexity": 10,
                    },
                },
            ),
        )
        try:
            result = _runner.invoke(
                app,
                ["pipeline", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert "Objectives" in result.output
        assert "100.00%" in result.output


class TestObjectives:
    """Tests for _collect_objective_rows and helpers."""

    def test_lint_objectives(self) -> None:
        """Requirement: lint checks produce objective rows."""
        results = {
            "format": _dummy_result("format"),
            "ruff": _dummy_result("ruff"),
            "flake8": _dummy_result("flake8"),
        }
        rows = collect_objective_rows(results)
        labels = [r[0] for r in rows]
        assert "Formatting" in labels
        assert "Ruff errors" in labels
        assert "Flake8 violations" in labels

    def test_typecheck_objective(self) -> None:
        """Requirement: typecheck produces error count row."""
        results = {
            "typecheck": CheckResult(
                name="typecheck",
                passed=False,
                detail="3 error(s)",
                metadata={"error_count": 3},
            ),
        }
        rows = collect_objective_rows(results)
        assert any(r[0] == "Type errors" and r[1] == "3" for r in rows)

    def test_metrics_objectives(self) -> None:
        """Requirement: metrics produces CC and violations rows."""
        results = {
            "metrics": CheckResult(
                name="metrics",
                passed=True,
                detail="pass",
                metadata={
                    "summary": {
                        "max_cyclomatic_complexity": 7,
                        "violations": 0,
                    },
                    "thresholds": {
                        "max_cyclomatic_complexity": 10,
                    },
                },
            ),
        }
        rows = collect_objective_rows(results)
        labels = [r[0] for r in rows]
        assert "Max cyclomatic complexity" in labels
        assert "Metrics violations" in labels

    def test_metrics_non_int_cc_uses_passed(self) -> None:
        """Requirement: non-int CC falls back to check passed."""
        results = {
            "metrics": CheckResult(
                name="metrics",
                passed=True,
                detail="pass",
                metadata={
                    "summary": {
                        "max_cyclomatic_complexity": "?",
                        "violations": 0,
                    },
                    "thresholds": {
                        "max_cyclomatic_complexity": "?",
                    },
                },
            ),
        }
        rows = collect_objective_rows(results)
        cc_row = next(r for r in rows if r[0] == "Max cyclomatic complexity")
        assert cc_row[3] is True

    def test_security_objectives(self) -> None:
        """Requirement: security checks produce objective rows."""
        results = {
            "security-code": _dummy_result("security-code"),
            "security-deps": _dummy_result("security-deps"),
        }
        rows = collect_objective_rows(results)
        labels = [r[0] for r in rows]
        assert "Security issues" in labels
        assert "Dependency vulns" in labels

    def test_coverage_objective(self) -> None:
        """Requirement: test coverage appears in objectives."""
        results = {
            "tests": CheckResult(
                name="tests",
                passed=True,
                detail="10 passed · coverage 100.00%",
            ),
        }
        rows = collect_objective_rows(results)
        labels = [r[0] for r in rows]
        assert "Test coverage" in labels
        assert "Test suite" in labels
        cov_row = next(r for r in rows if r[0] == "Test coverage")
        assert cov_row[1] == "100.00%"

    def test_coverage_objective_no_coverage_line(self) -> None:
        """Requirement: objectives work without coverage info."""
        results = {
            "tests": CheckResult(
                name="tests",
                passed=True,
                detail="10 passed",
            ),
        }
        rows = collect_objective_rows(results)
        labels = [r[0] for r in rows]
        assert "Test coverage" not in labels
        assert "Test suite" in labels

    def test_empty_results(self) -> None:
        """Requirement: empty results produce no rows."""
        assert collect_objective_rows({}) == []

    def test_print_objectives_skips_when_no_rows(self) -> None:
        """Requirement: objectives table is skipped when empty."""
        empty = PipelineResult(
            results=(),
            duration_seconds=0.0,
            passed=True,
        )
        with patch("yggtools.quality.display._console") as console:
            print_objectives_table(empty)
        console.print.assert_not_called()

    def test_is_int_valid(self) -> None:
        """Requirement: _is_int returns True for ints."""
        assert is_int(1, 2, 3)
        assert is_int("5", "10")

    def test_is_int_invalid(self) -> None:
        """Requirement: _is_int returns False for non-ints."""
        assert not is_int("?", 5)
        assert not is_int(None)


class TestInitRepo:
    """Tests for the init-repo command."""

    def test_dry_run_exits_0_without_writing(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: init-repo --dry-run must exit 0."""
        result = _runner.invoke(
            app,
            ["init-repo", "my-lib", "--dry-run"],
        )
        assert result.exit_code == 0
        assert not (tmp_path / "my-lib").exists()

    def test_exits_1_when_uv_not_found(self) -> None:
        """Requirement: init-repo must exit 1 when uv is absent."""
        with patch(
            "yggtools.repo_init.commands.check_uv_available",
            side_effect=UvNotFoundError("no uv"),
        ):
            result = _runner.invoke(
                app,
                ["init-repo", "my-lib"],
            )
        assert result.exit_code == 1

    def test_exits_1_on_step_error(self) -> None:
        """Requirement: init-repo must exit 1 on step failure."""
        with (
            patch("yggtools.repo_init.commands.check_uv_available"),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=StepError("step failed"),
            ),
        ):
            result = _runner.invoke(
                app,
                ["init-repo", "my-lib"],
            )
        assert result.exit_code == 1

    def test_exits_0_on_success(self) -> None:
        """Requirement: init-repo must exit 0 on success."""
        with (
            patch("yggtools.repo_init.commands.check_uv_available"),
            patch("yggtools.repo_init.commands.run_with_progress"),
        ):
            result = _runner.invoke(
                app,
                ["init-repo", "my-lib"],
            )
        assert result.exit_code == 0

    def test_dry_run_output_lists_planned_actions(self) -> None:
        """Requirement: dry-run output must list planned actions."""
        result = _runner.invoke(
            app,
            ["init-repo", "my-lib", "--dry-run"],
        )
        assert "uv init" in result.output
        assert result.exit_code == 0

    def test_exits_1_on_unexpected_exception(self) -> None:
        """Requirement: init-repo must exit 1 on unexpected error."""
        with (
            patch("yggtools.repo_init.commands.check_uv_available"),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = _runner.invoke(
                app,
                ["init-repo", "my-lib"],
            )
        assert result.exit_code == 1

    def test_run_with_progress_executes_step_fn(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _run_with_progress must call each step fn."""
        called: list[str] = []
        ctx = RepoContext(
            project_name="my-lib",
            python_version="3.12",
            parent_dir=tmp_path,
        )
        step = PipelineStep(
            name="stub",
            fn=lambda _c: called.append("stub"),
        )
        run_with_progress(ctx, steps=[step])
        assert called == ["stub"]

    def test_no_git_flag_suppresses_ci_in_dry_run(self) -> None:
        """Requirement: --no-git must omit CI workflow actions."""
        result = _runner.invoke(
            app,
            ["init-repo", "my-lib", "--dry-run", "--no-git"],
        )
        assert "ci.yml" not in result.output


class TestInit:
    """Tests for the init command (in-place scaffold)."""

    def test_exits_1_when_no_pyproject(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: init must exit 1 without pyproject.toml."""
        with patch(
            "yggtools.repo_init.commands.Path.cwd",
            return_value=tmp_path,
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_dry_run_exits_0(self, tmp_path: Path) -> None:
        """Requirement: init --dry-run must exit 0."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with patch(
            "yggtools.repo_init.commands.Path.cwd",
            return_value=tmp_path,
        ):
            result = _runner.invoke(app, ["init", "--dry-run"])
        assert result.exit_code == 0

    def test_dry_run_does_not_mention_uv_init(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: init --dry-run must not mention uv init."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with patch(
            "yggtools.repo_init.commands.Path.cwd",
            return_value=tmp_path,
        ):
            result = _runner.invoke(app, ["init", "--dry-run"])
        assert "uv init" not in result.output

    def test_exits_1_when_uv_not_found(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: init must exit 1 when uv is absent."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch(
                "yggtools.repo_init.commands.check_uv_available",
                side_effect=UvNotFoundError("no uv"),
            ),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_exits_0_on_success(self, tmp_path: Path) -> None:
        """Requirement: init must exit 0 on success."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.repo_init.commands.check_uv_available"),
            patch("yggtools.repo_init.commands.run_with_progress"),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 0

    def test_exits_1_on_step_error(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: init must exit 1 on step failure."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.repo_init.commands.check_uv_available"),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=StepError("step failed"),
            ),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_exits_1_on_unexpected_exception(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: init must exit 1 on unexpected error."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.repo_init.commands.check_uv_available"),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_uses_steps_init_not_steps_full(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: init must use STEPS_INIT (no uv init)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        received_steps: list[PipelineStep] = []

        def _capture_steps(
            ctx: RepoContext,
            steps: list[PipelineStep] | None = None,
        ) -> None:
            """Capture the steps argument.

            Args:
                ctx: Pipeline context (ignored).
                steps: Steps list passed by the caller.
            """
            if steps is not None:
                received_steps.extend(steps)

        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.repo_init.commands.check_uv_available"),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=_capture_steps,
            ),
        ):
            _runner.invoke(app, ["init"])

        step_names = [s.name for s in received_steps]
        assert "uv init --lib" not in step_names
        assert len(received_steps) == len(STEPS_INIT)


class TestReset:
    """Tests for the reset command."""

    def test_exits_1_when_no_pyproject(self, tmp_path: Path) -> None:
        """Requirement: reset must exit 1 outside a uv project."""
        with patch(
            "yggtools.repo_init.commands.Path.cwd",
            return_value=tmp_path,
        ):
            result = _runner.invoke(app, ["reset"])
        assert result.exit_code == 1

    def test_dry_run_lists_selected_steps(self, tmp_path: Path) -> None:
        """Requirement: reset --dry-run must list planned rewrites."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with patch(
            "yggtools.repo_init.commands.Path.cwd",
            return_value=tmp_path,
        ):
            result = _runner.invoke(
                app, ["reset", "--only", "ai", "--dry-run"]
            )
        assert result.exit_code == 0
        assert "write AGENTS.md" in result.output
        assert "write CI workflows" not in result.output

    def test_invalid_only_exits_1(self, tmp_path: Path) -> None:
        """Requirement: reset must reject unknown --only values."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with patch(
            "yggtools.repo_init.commands.Path.cwd",
            return_value=tmp_path,
        ):
            result = _runner.invoke(app, ["reset", "--only", "bad"])
        assert result.exit_code == 1

    def test_uses_selected_reset_steps(self, tmp_path: Path) -> None:
        """Requirement: reset --only ci must run only CI reset steps."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        received_steps: list[PipelineStep] = []

        def _capture_steps(
            ctx: RepoContext,
            steps: list[PipelineStep] | None = None,
        ) -> None:
            """Capture reset steps passed to the runner.

            Args:
                ctx: Pipeline context (ignored).
                steps: Steps list passed by the caller.
            """
            if steps is not None:
                received_steps.extend(steps)

        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=_capture_steps,
            ),
        ):
            result = _runner.invoke(app, ["reset", "--only", "ci"])

        assert result.exit_code == 0
        assert received_steps == STEPS_RESET_CI

    def test_exits_1_on_step_error(self, tmp_path: Path) -> None:
        """Requirement: reset must exit 1 on step failure."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=StepError("step failed"),
            ),
        ):
            result = _runner.invoke(app, ["reset"])
        assert result.exit_code == 1

    def test_exits_1_on_unexpected_exception(self, tmp_path: Path) -> None:
        """Requirement: reset must exit 1 on unexpected error."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch(
                "yggtools.repo_init.commands.Path.cwd",
                return_value=tmp_path,
            ),
            patch(
                "yggtools.repo_init.commands.run_with_progress",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = _runner.invoke(app, ["reset"])
        assert result.exit_code == 1

    def test_reset_steps_helper_selects_ai_group(self) -> None:
        """Requirement: _reset_steps must select the AI group."""
        assert reset_steps("ai") == STEPS_RESET_AI

    def test_read_python_version_uses_file(self, tmp_path: Path) -> None:
        """Requirement: .python-version configures generated CI."""
        (tmp_path / ".python-version").write_text(
            "3.13\n",
            encoding="utf-8",
        )
        assert read_python_version(tmp_path) == "3.13"

    def test_read_python_version_defaults_when_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: missing .python-version falls back to default."""
        assert read_python_version(tmp_path) == "3.12"


class TestIncreaseVersion:
    """Tests for increase-version command."""

    def test_exits_0_and_prints_update(self, tmp_path: Path) -> None:
        """Requirement: increase-version reports successful bump."""
        with patch(
            "yggtools.version_commands.increase_project_version",
            return_value=SimpleNamespace(
                project_name="my-lib",
                old_version="1.2.3",
                new_version="1.2.4",
                files=(tmp_path / "pyproject.toml",),
            ),
        ):
            result = _runner.invoke(
                app,
                ["increase-version", "1", "--path", str(tmp_path)],
            )
        assert result.exit_code == 0
        assert "1.2.3" in result.output
        assert "1.2.4" in result.output

    def test_exits_1_on_version_error(self, tmp_path: Path) -> None:
        """Requirement: version errors are shown cleanly."""
        with patch(
            "yggtools.version_commands.increase_project_version",
            side_effect=VersionError("bad version"),
        ):
            result = _runner.invoke(
                app,
                ["increase-version", "1", "--path", str(tmp_path)],
            )
        assert result.exit_code == 1
        assert "bad version" in result.output


class TestVersionCommand:
    """Tests for version command."""

    def test_lists_versions_and_exits_0_when_consistent(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: version command lists synchronized artifacts."""
        _write_version_project(tmp_path, version="1.2.3")
        result = _runner.invoke(app, ["version", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "pyproject.project.version" in result.output
        assert "package.__version__" in result.output
        assert "uv.lock.package.version" in result.output
        assert "1.2.3" in result.output
        assert "Version consistent" in result.output

    def test_exits_1_when_versions_differ(self, tmp_path: Path) -> None:
        """Requirement: version command fails on mismatched artifacts."""
        _write_version_project(tmp_path, version="1.2.3")
        (tmp_path / "src" / "my_lib" / "__init__.py").write_text(
            '__version__ = "1.2.4"\n',
            encoding="utf-8",
        )
        result = _runner.invoke(app, ["version", "--path", str(tmp_path)])
        assert result.exit_code == 1
        assert "1.2.3" in result.output
        assert "1.2.4" in result.output
        assert "Version mismatch detected" in result.output

    def test_exits_1_when_required_artifact_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: version command fails when a version is missing."""
        _write_version_project(tmp_path, version="1.2.3")
        (tmp_path / "uv.lock").unlink()
        result = _runner.invoke(app, ["version", "--path", str(tmp_path)])
        assert result.exit_code == 1
        assert "uv.lock.package.version" in result.output
        assert "Version mismatch detected" in result.output


class TestRun:
    """Tests for the run command."""

    def test_exits_1_without_check_or_all_flag(self) -> None:
        """Requirement: run without arguments must exit 1."""
        result = _runner.invoke(app, ["run"])
        assert result.exit_code == 1

    def test_exits_1_on_unknown_check(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: run with unknown check must exit 1."""
        result = _runner.invoke(
            app,
            ["run", "__nonexistent__", "--path", str(tmp_path)],
        )
        assert result.exit_code == 1

    def test_run_all_exits_0_when_all_pass(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: run --all must exit 0 when all pass."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("dummy"),
        )
        try:
            result = _runner.invoke(
                app,
                ["run", "--all", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 0

    def test_run_all_exits_1_when_any_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: run --all must exit 1 when any fails."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("dummy", passed=False),
        )
        try:
            result = _runner.invoke(
                app,
                ["run", "--all", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 1

    def test_always_writes_json_artifacts(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: run must always write JSON artifacts."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("dummy"),
        )
        try:
            _runner.invoke(
                app,
                ["run", "dummy", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        reports = tmp_path / "work" / "reports"
        assert (reports / "dummy.json").exists()
        assert (reports / "dummy.json.sha256").exists()

    def test_ci_flag_accepted_as_noop(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: --ci flag must be accepted without error."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("dummy"),
        )
        try:
            result = _runner.invoke(
                app,
                [
                    "run",
                    "dummy",
                    "--ci",
                    "--path",
                    str(tmp_path),
                ],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 0

    def test_report_dir_relative(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: relative --report-dir must be under project."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("dummy"),
        )
        try:
            _runner.invoke(
                app,
                [
                    "run",
                    "dummy",
                    "--report-dir",
                    "custom-reports",
                    "--path",
                    str(tmp_path),
                ],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert (tmp_path / "custom-reports" / "dummy.json").exists()

    def test_report_dir_absolute(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: absolute --report-dir must be used as-is."""
        output_dir = tmp_path / "absolute-reports"
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("dummy"),
        )
        try:
            _runner.invoke(
                app,
                [
                    "run",
                    "dummy",
                    "--report-dir",
                    str(output_dir),
                    "--path",
                    str(tmp_path),
                ],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert (output_dir / "dummy.json").exists()

    def test_print_run_summary_includes_json_checksum(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: summary must include JSON path and checksum."""
        result = CheckResult(
            name="dummy",
            passed=True,
            detail="ok",
            command=("uv", "run", "dummy"),
            metadata={
                "summary": {
                    "python_files_parsed": 2,
                    "total_logical_lines": 10,
                    "total_functions": 3,
                    "total_classes": 1,
                    "max_cyclomatic_complexity": 4,
                    "violations": 0,
                },
                "top_complex_functions": [
                    {
                        "path": "src/a.py",
                        "line": 12,
                        "name": "work",
                        "cyclomatic_complexity": 4,
                    },
                ],
            },
        )
        with patch("yggtools.quality.display._console") as console:
            print_run_summary(
                [result],
                tmp_path,
                {
                    "dummy": (
                        tmp_path / "work" / "reports" / "dummy.json",
                        "abc123",
                    ),
                },
            )
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "PASS" in printed
        assert "uv run dummy" in printed
        assert "files=2" in printed
        assert "CC=4 src/a.py:12 work" in printed
        assert "work/reports/dummy.json" in printed
        assert "abc123" in printed

    def test_print_run_summary_shortens_long_top_item(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: long top fields must be shortened."""
        result = CheckResult(
            name="dummy",
            passed=True,
            detail="ok",
            metadata={
                "top_complex_functions": [
                    {
                        "path": "src/very/deep/path/to/a/module.py",
                        "line": 12,
                        "name": ("very_long_function_name_that_should_wrap"),
                        "cyclomatic_complexity": 4,
                    },
                ],
            },
        )
        with patch("yggtools.quality.display._console") as console:
            print_run_summary([result], tmp_path, {})
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "..." in printed

    def test_print_run_summary_includes_failure_context(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: failed checks must print short context."""
        result = CheckResult(
            name="dummy",
            passed=False,
            detail="bad",
            stderr="first\nsecond",
        )
        with patch("yggtools.quality.display._console") as console:
            print_run_summary(
                [result],
                tmp_path,
                {
                    "dummy": (
                        Path("/outside/dummy.json"),
                        "abc123",
                    ),
                },
            )
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "FAIL" in printed
        assert "/outside/dummy.json" in printed
        assert "second" in printed

    def test_print_run_summary_handles_plain_top_item(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: summary handles simple top values."""
        result = CheckResult(
            name="dummy",
            passed=True,
            detail="ok",
            metadata={
                "top_complex_functions": ["plain"],
            },
        )
        with patch("yggtools.quality.display._console") as console:
            print_run_summary([result], tmp_path, {})
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "plain" in printed

    def test_warning_result_renders_warn_status(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: warning checks must render as non-blocking WARN."""
        result = CheckResult(
            name="todos",
            passed=True,
            detail="1 todo(s)",
            metadata={
                "severity": "warning",
                "warning_count": 1,
                "findings": [
                    {
                        "path": "src/yggtools/a.py",
                        "line": 4,
                        "marker": "todo",
                        "text": "# TODO: later",
                    },
                ],
            },
        )
        with patch("yggtools.quality.display._console") as console:
            print_run_summary([result], tmp_path, {})
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "WARN" in printed
        assert "src/yggtools/a.py:4 todo # TODO: later" in printed
        assert result_icon(result) == "[yellow]![/yellow]"
        assert result_status_label(result) == "[yellow]WARN[/yellow]"

    def test_print_warning_details_lists_findings(self) -> None:
        """Requirement: pipeline output must list warning findings."""
        result = CheckResult(
            name="lint-suppressions",
            passed=True,
            detail="1 suppression(s)",
            metadata={
                "severity": "warning",
                "warning_count": 1,
                "findings": [
                    {
                        "path": "src/yggtools/a.py",
                        "line": 3,
                        "marker": "noqa",
                        "text": "value = 1  # noqa",
                    },
                ],
            },
        )
        report = PipelineResult(
            results=(result,),
            duration_seconds=0.0,
            passed=True,
        )
        with patch("yggtools.quality.display._console") as console:
            print_warning_details(report)
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "Warnings" in printed
        assert "src/yggtools/a.py:3 noqa value = 1  # noqa" in printed

    def test_warning_helpers_handle_plain_metadata(self) -> None:
        """Requirement: warning formatting must tolerate plain values."""
        result = CheckResult(
            name="todos",
            passed=True,
            detail="1 todo(s)",
            metadata={
                "severity": "warning",
                "warning_count": 1,
                "findings": ["plain"],
            },
        )
        assert warning_finding_lines(result) == ["plain"]
        with patch("yggtools.quality.display._console") as console:
            print_result_context(result)
        console.print.assert_called_with("  warning: plain")

    def test_warning_helpers_skip_invalid_finding_list(self) -> None:
        """Requirement: invalid warning finding metadata must be ignored."""
        result = CheckResult(
            name="todos",
            passed=True,
            detail="1 todo(s)",
            metadata={
                "severity": "warning",
                "warning_count": 1,
                "findings": "plain",
            },
        )
        assert warning_finding_lines(result) == []


def _write_version_project(tmp_path: Path, *, version: str) -> None:
    """Write a minimal project with synchronized version artifacts.

    Args:
        tmp_path: Temporary project root.
        version: Version string to write.
    """
    (tmp_path / "src" / "my_lib").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "my-lib"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "my_lib" / "__init__.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        f'[[package]]\nname = "my-lib"\nversion = "{version}"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )
