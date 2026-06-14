"""Unit tests for yggtools.uv_runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yggtools.uv_runner import (
    CommandError,
    UvNotFoundError,
    check_uv_available,
    git_add_all,
    git_commit,
    git_init,
    run_command,
    uv_add_dev_deps,
    uv_sync,
)


def test_check_uv_available_raises_when_not_found() -> None:
    """Requirement: check_uv_available must raise UvNotFoundError if absent."""
    with (
        patch("yggtools.uv_runner.shutil.which", return_value=None),
        pytest.raises(UvNotFoundError),
    ):
        check_uv_available()


def test_check_uv_available_passes_when_found() -> None:
    """Requirement: check_uv_available must not raise when uv is in PATH."""
    with patch("yggtools.uv_runner.shutil.which", return_value="/usr/bin/uv"):
        check_uv_available()  # must not raise


def test_run_command_raises_on_nonzero(tmp_path: Path) -> None:
    """Requirement: run_command must raise CommandError on non-zero exit."""
    with pytest.raises(CommandError) as exc_info:
        run_command(["false"], cwd=tmp_path)
    assert exc_info.value.returncode != 0


def test_run_command_returns_result_on_success(tmp_path: Path) -> None:
    """Requirement: run_command must return a CompletedProcess on success."""
    result = run_command(["true"], cwd=tmp_path)
    assert result.returncode == 0


def test_command_error_stores_returncode(tmp_path: Path) -> None:
    """Requirement: CommandError must expose the subprocess returncode."""
    with pytest.raises(CommandError) as exc_info:
        run_command(["false"], cwd=tmp_path)
    assert isinstance(exc_info.value.returncode, int)


def test_uv_add_dev_deps_calls_uv(tmp_path: Path) -> None:
    """Requirement: uv_add_dev_deps must invoke uv add --group dev."""
    with patch("yggtools.uv_runner.run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        uv_add_dev_deps(tmp_path, ["ruff>=0.4"])
    called_cmd = mock_run.call_args[0][0]
    assert "uv" in called_cmd
    assert "add" in called_cmd
    assert "--group" in called_cmd
    assert "dev" in called_cmd
    assert "ruff>=0.4" in called_cmd


def test_uv_sync_calls_uv_sync(tmp_path: Path) -> None:
    """Requirement: uv_sync must invoke uv sync in the project directory."""
    with patch("yggtools.uv_runner.run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        uv_sync(tmp_path)
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd == ["uv", "sync"]


def test_git_init_calls_git_init(tmp_path: Path) -> None:
    """Requirement: git_init must invoke git init in the project directory."""
    with patch("yggtools.uv_runner.run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        git_init(tmp_path)
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd == ["git", "init"]


def test_git_add_all_calls_git_add(tmp_path: Path) -> None:
    """Requirement: git_add_all must invoke git add -A."""
    with patch("yggtools.uv_runner.run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        git_add_all(tmp_path)
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd == ["git", "add", "-A"]


def test_git_commit_calls_git_commit(tmp_path: Path) -> None:
    """Requirement: git_commit must invoke git commit with the message."""
    with patch("yggtools.uv_runner.run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        git_commit(tmp_path, "chore: init")
    called_cmd = mock_run.call_args[0][0]
    assert "git" in called_cmd
    assert "commit" in called_cmd
    assert "chore: init" in called_cmd
