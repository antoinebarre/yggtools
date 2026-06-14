"""Unit tests for yggtools.cli."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from yggtools.cli import app
from yggtools.repo_init.steps import RepoContext, StepError
from yggtools.uv import UvNotFoundError

_runner = CliRunner()


class TestInitRepo:
    """Tests for the init-repo command."""

    def test_dry_run_exits_0_without_writing(self, tmp_path: Path) -> None:
        """Requirement: init-repo --dry-run must exit 0 without writing files."""
        result = _runner.invoke(
            app,
            ["init-repo", "my-lib", "--dry-run"],
        )
        assert result.exit_code == 0
        assert not (tmp_path / "my-lib").exists()

    def test_exits_1_when_uv_not_found(self, tmp_path: Path) -> None:
        """Requirement: init-repo must exit 1 when uv is not available."""
        with patch(
            "yggtools.cli.check_uv_available",
            side_effect=UvNotFoundError("no uv"),
        ):
            result = _runner.invoke(app, ["init-repo", "my-lib"])
        assert result.exit_code == 1

    def test_exits_1_on_step_error(self, tmp_path: Path) -> None:
        """Requirement: init-repo must exit 1 when a pipeline step fails."""
        with (
            patch("yggtools.cli.check_uv_available"),
            patch(
                "yggtools.cli.run_pipeline",
                side_effect=StepError("step failed"),
            ),
        ):
            result = _runner.invoke(app, ["init-repo", "my-lib"])
        assert result.exit_code == 1

    def test_exits_0_on_success(self, tmp_path: Path) -> None:
        """Requirement: init-repo must exit 0 when all steps succeed."""
        with (
            patch("yggtools.cli.check_uv_available"),
            patch("yggtools.cli.run_pipeline"),
        ):
            result = _runner.invoke(app, ["init-repo", "my-lib"])
        assert result.exit_code == 0

    def test_dry_run_output_lists_planned_actions(self) -> None:
        """Requirement: dry-run output must list planned actions."""
        result = _runner.invoke(app, ["init-repo", "my-lib", "--dry-run"])
        assert "uv init" in result.output
        assert result.exit_code == 0

    def test_no_git_flag_suppresses_ci_in_dry_run(self) -> None:
        """Requirement: --no-git dry-run output must omit CI workflow actions."""
        result = _runner.invoke(
            app, ["init-repo", "my-lib", "--dry-run", "--no-git"]
        )
        assert "ci.yml" not in result.output


class TestRun:
    """Tests for the run command."""

    def _import_checks(self) -> None:
        """Import all check modules to populate the registry."""
        import yggtools.quality.checks.format  # noqa: F401
        import yggtools.quality.checks.lint  # noqa: F401
        import yggtools.quality.checks.metrics  # noqa: F401
        import yggtools.quality.checks.security  # noqa: F401
        import yggtools.quality.checks.tests  # noqa: F401
        import yggtools.quality.checks.typecheck  # noqa: F401

    def test_exits_1_without_check_or_all_flag(self) -> None:
        """Requirement: run without arguments must exit 1 with usage error."""
        result = _runner.invoke(app, ["run"])
        assert result.exit_code == 1

    def test_exits_1_on_unknown_check(self, tmp_path: Path) -> None:
        """Requirement: run with unknown check name must exit 1."""
        self._import_checks()
        result = _runner.invoke(
            app, ["run", "__nonexistent__", "--path", str(tmp_path)]
        )
        assert result.exit_code == 1

    def test_run_all_exits_0_when_all_pass(self, tmp_path: Path) -> None:
        """Requirement: run --all must exit 0 when all checks pass."""
        from yggtools.quality.runner import CheckResult, _REGISTRY
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = lambda p: CheckResult(
            name="dummy", passed=True, detail="ok"
        )
        try:
            result = _runner.invoke(
                app, ["run", "--all", "--path", str(tmp_path)]
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 0

    def test_run_all_exits_1_when_any_fails(self, tmp_path: Path) -> None:
        """Requirement: run --all must exit 1 when any check fails."""
        from yggtools.quality.runner import CheckResult, _REGISTRY
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = lambda p: CheckResult(
            name="dummy", passed=False, detail="bad"
        )
        try:
            result = _runner.invoke(
                app, ["run", "--all", "--path", str(tmp_path)]
            )
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.exit_code == 1

    def test_ci_mode_writes_report(self, tmp_path: Path) -> None:
        """Requirement: run --ci must write work/report.md."""
        from yggtools.quality.runner import CheckResult, _REGISTRY
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["dummy"] = lambda p: CheckResult(
            name="dummy", passed=True, detail="ok"
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
