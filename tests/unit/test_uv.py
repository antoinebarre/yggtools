"""Unit tests for yggtools.uv adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from yggtools.uv import (
    CommandError,
    RunResult,
    UvNotFoundError,
    check_uv_available,
    git_commit,
    run_uv,
    uv_add_dev,
    uv_init_lib,
    uv_sync,
)


class TestCheckUvAvailable:
    """Tests for check_uv_available."""

    def test_raises_when_uv_not_in_path(self) -> None:
        """Requirement: check_uv_available must raise UvNotFoundError."""
        with patch("yggtools.uv.shutil.which", return_value=None):
            with pytest.raises(UvNotFoundError):
                check_uv_available()

    def test_does_not_raise_when_uv_found(self) -> None:
        """Requirement: check_uv_available must not raise when uv is found."""
        with patch("yggtools.uv.shutil.which", return_value="/usr/bin/uv"):
            check_uv_available()


class TestRunUv:
    """Tests for run_uv."""

    def test_returns_run_result_on_success(self, tmp_path: Path) -> None:
        """Requirement: run_uv must return RunResult with returncode 0."""
        mock_proc = MagicMock(returncode=0, stdout="ok\n", stderr="")
        with patch("yggtools.uv.subprocess.run", return_value=mock_proc):
            result = run_uv(["run", "pytest"], cwd=tmp_path, capture=True)
        assert isinstance(result, RunResult)
        assert result.returncode == 0
        assert result.stdout == "ok\n"

    def test_raises_command_error_when_check_true(
        self, tmp_path: Path
    ) -> None:
        """Requirement: run_uv must raise CommandError when check=True fails."""
        mock_proc = MagicMock(returncode=1, stdout="", stderr="boom")
        with patch("yggtools.uv.subprocess.run", return_value=mock_proc):
            with pytest.raises(CommandError) as exc_info:
                run_uv(["run", "bad"], cwd=tmp_path, check=True)
        assert exc_info.value.returncode == 1
        assert exc_info.value.stderr == "boom"

    def test_no_raise_when_check_false_and_nonzero(
        self, tmp_path: Path
    ) -> None:
        """Requirement: run_uv must not raise when check=False and exit!=0."""
        mock_proc = MagicMock(returncode=1, stdout="", stderr="err")
        with patch("yggtools.uv.subprocess.run", return_value=mock_proc):
            result = run_uv(["run", "bad"], cwd=tmp_path, check=False)
        assert result.returncode == 1


class TestUvInitLib:
    """Tests for uv_init_lib."""

    def test_calls_run_uv_with_lib_flag(self, tmp_path: Path) -> None:
        """Requirement: uv_init_lib must call uv init --lib."""
        with patch("yggtools.uv.run_uv") as mock:
            mock.return_value = RunResult(0, "", "")
            uv_init_lib(tmp_path, "my-lib", "3.12")
        args = mock.call_args[0][0]
        assert "init" in args
        assert "--lib" in args
        assert "my-lib" in args
        assert "3.12" in args


class TestUvAddDev:
    """Tests for uv_add_dev."""

    def test_calls_run_uv_with_dev_flag(self, tmp_path: Path) -> None:
        """Requirement: uv_add_dev must call uv add --dev."""
        with patch("yggtools.uv.run_uv") as mock:
            mock.return_value = RunResult(0, "", "")
            uv_add_dev(tmp_path, ["pytest>=8", "ruff>=0.4"])
        args = mock.call_args[0][0]
        assert "add" in args
        assert "--dev" in args
        assert "pytest>=8" in args


class TestUvSync:
    """Tests for uv_sync."""

    def test_calls_run_uv_sync(self, tmp_path: Path) -> None:
        """Requirement: uv_sync must call uv sync."""
        with patch("yggtools.uv.run_uv") as mock:
            mock.return_value = RunResult(0, "", "")
            uv_sync(tmp_path)
        args = mock.call_args[0][0]
        assert "sync" in args


class TestGitCommit:
    """Tests for git_commit."""

    def test_runs_git_add_and_commit(self, tmp_path: Path) -> None:
        """Requirement: git_commit must run git add -A then git commit -m."""
        with patch("yggtools.uv.subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            git_commit(tmp_path, "chore: init")
        calls = mock.call_args_list
        assert any("add" in str(c) for c in calls)
        assert any("commit" in str(c) for c in calls)
