"""Unit tests for yggtools.cli."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from yggtools.cli import app
from yggtools.init import ConflictError
from yggtools.models import CheckResult
from yggtools.uv_runner import UvNotFoundError

_runner = CliRunner()


def test_init_dry_run_exits_zero() -> None:
    """Requirement: yggtools init --dry-run must exit 0 without files."""
    with patch("yggtools.cli.run_init"):
        result = _runner.invoke(app, ["init", "mylib", "--dry-run"])
    assert result.exit_code == 0


def test_init_passes_project_name_to_run_init() -> None:
    """Requirement: yggtools init must forward the project name to run_init."""
    with patch("yggtools.cli.run_init") as mock_init:
        _runner.invoke(app, ["init", "coolproject"])
    assert mock_init.called
    ctx = mock_init.call_args[0][0]
    assert ctx.project_name == "coolproject"


def test_init_defaults_python_version() -> None:
    """Requirement: yggtools init must default to Python 3.12."""
    with patch("yggtools.cli.run_init") as mock_init:
        _runner.invoke(app, ["init", "mylib"])
    ctx = mock_init.call_args[0][0]
    assert ctx.python_version == "3.12"


def test_init_respects_custom_python() -> None:
    """Requirement: yggtools init --python must set python_version."""
    with patch("yggtools.cli.run_init") as mock_init:
        _runner.invoke(app, ["init", "mylib", "--python", "3.13"])
    ctx = mock_init.call_args[0][0]
    assert ctx.python_version == "3.13"


def test_init_no_git_flag() -> None:
    """Requirement: yggtools init --no-git must set no_git=True on context."""
    with patch("yggtools.cli.run_init") as mock_init:
        _runner.invoke(app, ["init", "mylib", "--no-git"])
    ctx = mock_init.call_args[0][0]
    assert ctx.no_git is True


def test_init_force_flag() -> None:
    """Requirement: yggtools init --force must set force=True on context."""
    with patch("yggtools.cli.run_init") as mock_init:
        _runner.invoke(app, ["init", "mylib", "--force"])
    ctx = mock_init.call_args[0][0]
    assert ctx.force is True


def test_init_exits_1_on_uv_not_found() -> None:
    """Requirement: yggtools init must exit 1 when uv is not found."""
    with patch("yggtools.cli.run_init", side_effect=UvNotFoundError("no uv")):
        result = _runner.invoke(app, ["init", "mylib"])
    assert result.exit_code == 1


def test_init_exits_1_on_conflict_error() -> None:
    """Requirement: yggtools init must exit 1 on ConflictError."""
    with patch("yggtools.cli.run_init", side_effect=ConflictError("conflict")):
        result = _runner.invoke(app, ["init", "mylib"])
    assert result.exit_code == 1


def test_init_exits_1_on_unexpected_error() -> None:
    """Requirement: yggtools init must exit 1 on any unexpected exception."""
    with patch("yggtools.cli.run_init", side_effect=RuntimeError("boom")):
        result = _runner.invoke(app, ["init", "mylib"])
    assert result.exit_code == 1


def test_check_exits_0_on_all_pass(tmp_path: Path) -> None:
    """Requirement: yggtools check must exit 0 when all checks pass."""
    all_pass = [CheckResult(label="src/", passed=True)]
    with patch("yggtools.cli.run_check", return_value=all_pass):
        result = _runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 0


def test_check_exits_1_on_failure(tmp_path: Path) -> None:
    """Requirement: yggtools check must exit 1 on any check failure."""
    one_fail = [CheckResult(label="src/", passed=False, detail="missing")]
    with patch("yggtools.cli.run_check", return_value=one_fail):
        result = _runner.invoke(app, ["check", str(tmp_path)])
    assert result.exit_code == 1
