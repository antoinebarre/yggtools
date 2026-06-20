"""Unit tests for yggtools.cli."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

from typer.testing import CliRunner

from yggtools.cli import _print_ci_details, _run_with_progress, app
from yggtools.quality.runner import _REGISTRY, CheckFn, CheckResult
from yggtools.repo_init.pipeline import STEPS_INIT, PipelineStep
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError

_runner = CliRunner()


class TestInitRepo:
    """Tests for the init-repo command."""

    def test_dry_run_exits_0_without_writing(self, tmp_path: Path) -> None:
        """Requirement: init-repo --dry-run must exit 0 without writing."""
        result = _runner.invoke(
            app,
            ["init-repo", "my-lib", "--dry-run"],
        )
        assert result.exit_code == 0
        assert not (tmp_path / "my-lib").exists()

    def test_exits_1_when_uv_not_found(self) -> None:
        """Requirement: init-repo must exit 1 when uv is not available."""
        with patch(
            "yggtools.cli.check_uv_available",
            side_effect=UvNotFoundError("no uv"),
        ):
            result = _runner.invoke(app, ["init-repo", "my-lib"])
        assert result.exit_code == 1

    def test_exits_1_on_step_error(self) -> None:
        """Requirement: init-repo must exit 1 when a pipeline step fails."""
        with (
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
                side_effect=StepError("step failed"),
            ),
        ):
            result = _runner.invoke(app, ["init-repo", "my-lib"])
        assert result.exit_code == 1

    def test_exits_0_on_success(self) -> None:
        """Requirement: init-repo must exit 0 when all steps succeed."""
        with (
            patch("yggtools.cli.check_uv_available"),
            patch("yggtools.cli._run_with_progress"),
        ):
            result = _runner.invoke(app, ["init-repo", "my-lib"])
        assert result.exit_code == 0

    def test_dry_run_output_lists_planned_actions(self) -> None:
        """Requirement: dry-run output must list planned actions."""
        result = _runner.invoke(app, ["init-repo", "my-lib", "--dry-run"])
        assert "uv init" in result.output
        assert result.exit_code == 0

    def test_exits_1_on_unexpected_exception(self) -> None:
        """Requirement: init-repo must exit 1 on any unexpected exception."""
        with (
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = _runner.invoke(app, ["init-repo", "my-lib"])
        assert result.exit_code == 1

    def test_run_with_progress_executes_step_fn(self, tmp_path: Path) -> None:
        """Requirement: _run_with_progress must call each step's fn."""
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
        """Requirement: --no-git dry-run must omit CI workflow actions."""
        result = _runner.invoke(
            app,
            ["init-repo", "my-lib", "--dry-run", "--no-git"],
        )
        assert "ci.yml" not in result.output


class TestInit:
    """Tests for the init command (in-place scaffold)."""

    def test_exits_1_when_no_pyproject(self, tmp_path: Path) -> None:
        """Requirement: init must exit 1 when pyproject.toml is absent."""
        with patch("yggtools.cli.Path.cwd", return_value=tmp_path):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_dry_run_exits_0(self, tmp_path: Path) -> None:
        """Requirement: init --dry-run must exit 0 without writing."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with patch("yggtools.cli.Path.cwd", return_value=tmp_path):
            result = _runner.invoke(app, ["init", "--dry-run"])
        assert result.exit_code == 0

    def test_dry_run_does_not_mention_uv_init(self, tmp_path: Path) -> None:
        """Requirement: init --dry-run must not mention uv init --lib."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with patch("yggtools.cli.Path.cwd", return_value=tmp_path):
            result = _runner.invoke(app, ["init", "--dry-run"])
        assert "uv init" not in result.output

    def test_exits_1_when_uv_not_found(self, tmp_path: Path) -> None:
        """Requirement: init must exit 1 when uv is not available."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch("yggtools.cli.Path.cwd", return_value=tmp_path),
            patch(
                "yggtools.cli.check_uv_available",
                side_effect=UvNotFoundError("no uv"),
            ),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_exits_0_on_success(self, tmp_path: Path) -> None:
        """Requirement: init must exit 0 when all steps succeed."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch("yggtools.cli.Path.cwd", return_value=tmp_path),
            patch("yggtools.cli.check_uv_available"),
            patch("yggtools.cli._run_with_progress"),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 0

    def test_exits_1_on_step_error(self, tmp_path: Path) -> None:
        """Requirement: init must exit 1 when a pipeline step fails."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch("yggtools.cli.Path.cwd", return_value=tmp_path),
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
                side_effect=StepError("step failed"),
            ),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_exits_1_on_unexpected_exception(self, tmp_path: Path) -> None:
        """Requirement: init must exit 1 on any unexpected exception."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        with (
            patch("yggtools.cli.Path.cwd", return_value=tmp_path),
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli._run_with_progress",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = _runner.invoke(app, ["init"])
        assert result.exit_code == 1

    def test_uses_steps_init_not_steps_full(self, tmp_path: Path) -> None:
        """Requirement: init must pass STEPS_INIT (no uv init step)."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\n',
            encoding="utf-8",
        )
        received_steps: list[PipelineStep] = []

        def _capture_steps(
            ctx: RepoContext,
            steps: list[PipelineStep] | None = None,
        ) -> None:
            """Capture the steps argument passed to _run_with_progress.

            Args:
                ctx: Pipeline context (ignored).
                steps: Steps list passed by the caller.
            """
            if steps is not None:
                received_steps.extend(steps)

        with (
            patch("yggtools.cli.Path.cwd", return_value=tmp_path),
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
        """Requirement: run without arguments must exit 1 with usage error."""
        result = _runner.invoke(app, ["run"])
        assert result.exit_code == 1

    def test_exits_1_on_unknown_check(self, tmp_path: Path) -> None:
        """Requirement: run with unknown check name must exit 1."""
        result = _runner.invoke(
            app,
            ["run", "__nonexistent__", "--path", str(tmp_path)],
        )
        assert result.exit_code == 1

    def test_run_all_exits_0_when_all_pass(self, tmp_path: Path) -> None:
        """Requirement: run --all must exit 0 when all checks pass."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: CheckResult(name="dummy", passed=True, detail="ok"),
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

    def test_run_all_exits_1_when_any_fails(self, tmp_path: Path) -> None:
        """Requirement: run --all must exit 1 when any check fails."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: CheckResult(name="dummy", passed=False, detail="bad"),
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

    def test_ci_mode_writes_report(self, tmp_path: Path) -> None:
        """Requirement: run --ci must write work/report.md."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: CheckResult(name="dummy", passed=True, detail="ok"),
        )
        try:
            _runner.invoke(
                app,
                ["run", "--all", "--ci", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert (tmp_path / "work" / "report.md").exists()

    def test_ci_mode_writes_per_check_report(self, tmp_path: Path) -> None:
        """Requirement: run --ci must write one markdown report per check."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: CheckResult(name="dummy", passed=True, detail="ok"),
        )
        try:
            _runner.invoke(
                app,
                ["run", "dummy", "--ci", "--path", str(tmp_path)],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert (tmp_path / "work" / "ci" / "reports" / "dummy.md").exists()

    def test_ci_report_dir_is_relative_to_project(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: relative --report-dir must be under project path."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: CheckResult(name="dummy", passed=True, detail="ok"),
        )
        try:
            _runner.invoke(
                app,
                [
                    "run",
                    "dummy",
                    "--ci",
                    "--report-dir",
                    "custom-reports",
                    "--path",
                    str(tmp_path),
                ],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert (tmp_path / "custom-reports" / "dummy.md").exists()

    def test_ci_report_dir_accepts_absolute_path(self, tmp_path: Path) -> None:
        """Requirement: absolute --report-dir must be used unchanged."""
        output_dir = tmp_path / "absolute-reports"
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = cast(
            "CheckFn",
            lambda _p: CheckResult(name="dummy", passed=True, detail="ok"),
        )
        try:
            _runner.invoke(
                app,
                [
                    "run",
                    "dummy",
                    "--ci",
                    "--report-dir",
                    str(output_dir),
                    "--path",
                    str(tmp_path),
                ],
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert (output_dir / "dummy.md").exists()

    def test_print_ci_details_includes_rich_result_fields(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: CI detail output must include captured fields."""
        result = CheckResult(
            name="dummy",
            passed=True,
            detail="ok",
            command=("uv", "run", "dummy"),
            stdout="line 1\nline 2",
            stderr="warning",
            artifacts=(tmp_path / "artifact.md",),
        )
        with patch("yggtools.cli._console") as console:
            _print_ci_details([result])
        printed = "\n".join(
            str(call.args[0])
            for call in console.print.call_args_list
            if call.args
        )
        assert "uv run dummy" in printed
        assert "artifact.md" in printed
        assert "line 2" in printed
        assert "warning" in printed
