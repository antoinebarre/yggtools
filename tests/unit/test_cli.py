"""Unit tests for yggtools.cli."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

from typer.testing import CliRunner

from yggtools.cli import (
    _collect_objective_rows,
    _is_int,
    _print_objectives_table,
    _print_run_summary,
    _run_with_progress,
    app,
)
from yggtools.quality.pipeline import PipelineResult
from yggtools.quality.runner import _REGISTRY, CheckFn, CheckResult
from yggtools.repo_init.pipeline import STEPS_INIT, PipelineStep
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError

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
        rows = _collect_objective_rows(results)
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
        rows = _collect_objective_rows(results)
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
        rows = _collect_objective_rows(results)
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
        rows = _collect_objective_rows(results)
        cc_row = next(r for r in rows if r[0] == "Max cyclomatic complexity")
        assert cc_row[3] is True

    def test_security_objectives(self) -> None:
        """Requirement: security checks produce objective rows."""
        results = {
            "security-code": _dummy_result("security-code"),
            "security-deps": _dummy_result("security-deps"),
        }
        rows = _collect_objective_rows(results)
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
        rows = _collect_objective_rows(results)
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
        rows = _collect_objective_rows(results)
        labels = [r[0] for r in rows]
        assert "Test coverage" not in labels
        assert "Test suite" in labels

    def test_empty_results(self) -> None:
        """Requirement: empty results produce no rows."""
        assert _collect_objective_rows({}) == []

    def test_print_objectives_skips_when_no_rows(self) -> None:
        """Requirement: objectives table is skipped when empty."""
        empty = PipelineResult(
            results=(),
            duration_seconds=0.0,
            passed=True,
        )
        with patch("yggtools.cli._console") as console:
            _print_objectives_table(empty)
        console.print.assert_not_called()

    def test_is_int_valid(self) -> None:
        """Requirement: _is_int returns True for ints."""
        assert _is_int(1, 2, 3)
        assert _is_int("5", "10")

    def test_is_int_invalid(self) -> None:
        """Requirement: _is_int returns False for non-ints."""
        assert not _is_int("?", 5)
        assert not _is_int(None)


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
            "yggtools.cli.check_uv_available",
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
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
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
            patch("yggtools.cli.check_uv_available"),
            patch("yggtools.cli._run_with_progress"),
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
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
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
        _run_with_progress(ctx, steps=[step])
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
            "yggtools.cli.Path.cwd",
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
            "yggtools.cli.Path.cwd",
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
            "yggtools.cli.Path.cwd",
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
                "yggtools.cli.Path.cwd",
                return_value=tmp_path,
            ),
            patch(
                "yggtools.cli.check_uv_available",
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
                "yggtools.cli.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.cli.check_uv_available"),
            patch("yggtools.cli._run_with_progress"),
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
                "yggtools.cli.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
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
                "yggtools.cli.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
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
                "yggtools.cli.Path.cwd",
                return_value=tmp_path,
            ),
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
                side_effect=_capture_steps,
            ),
        ):
            _runner.invoke(app, ["init"])

        step_names = [s.name for s in received_steps]
        assert "uv init --lib" not in step_names
        assert len(received_steps) == len(STEPS_INIT)


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
        with patch("yggtools.cli._console") as console:
            _print_run_summary(
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
        with patch("yggtools.cli._console") as console:
            _print_run_summary([result], tmp_path, {})
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "…" in printed

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
        with patch("yggtools.cli._console") as console:
            _print_run_summary(
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
        with patch("yggtools.cli._console") as console:
            _print_run_summary([result], tmp_path, {})
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "plain" in printed
