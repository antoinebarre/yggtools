"""Unit tests for individual quality check functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from yggtools.quality.checks.format import check_format
from yggtools.quality.checks.lint import check_flake8, check_ruff
from yggtools.quality.checks.metrics import check_metrics
from yggtools.quality.checks.security import check_security_code, check_security_deps
from yggtools.quality.checks.tests import check_tests
from yggtools.quality.checks.typecheck import check_typecheck
from yggtools.quality.runner import CheckResult
from yggtools.uv import RunResult


def _passing(stdout: str = "", stderr: str = "") -> RunResult:
    """Build a RunResult representing a successful command.

    Args:
        stdout: Captured standard output.
        stderr: Captured standard error.

    Returns:
        RunResult with returncode 0.
    """
    return RunResult(returncode=0, stdout=stdout, stderr=stderr)


def _failing(stdout: str = "", stderr: str = "") -> RunResult:
    """Build a RunResult representing a failed command.

    Args:
        stdout: Captured standard output.
        stderr: Captured standard error.

    Returns:
        RunResult with returncode 1.
    """
    return RunResult(returncode=1, stdout=stdout, stderr=stderr)


class TestCheckFormat:
    """Tests for check_format."""

    def test_passes_when_ruff_exits_0(self, tmp_path: Path) -> None:
        """Requirement: check_format must pass when ruff format exits 0."""
        with patch("yggtools.quality.checks.format.run_uv", return_value=_passing()):
            result = check_format(tmp_path)
        assert result.passed
        assert result.name == "format"

    def test_fails_and_counts_files_to_reformat(self, tmp_path: Path) -> None:
        """Requirement: check_format detail must count 'would reformat' lines."""
        output = "would reformat src/a.py\nwould reformat src/b.py\n"
        with patch(
            "yggtools.quality.checks.format.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_format(tmp_path)
        assert not result.passed
        assert "2" in result.detail


class TestCheckRuff:
    """Tests for check_ruff."""

    def test_passes_when_ruff_exits_0(self, tmp_path: Path) -> None:
        """Requirement: check_ruff must pass when ruff check exits 0."""
        with patch("yggtools.quality.checks.lint.run_uv", return_value=_passing()):
            result = check_ruff(tmp_path)
        assert result.passed

    def test_fails_and_includes_error_count(self, tmp_path: Path) -> None:
        """Requirement: check_ruff detail must include the error count."""
        output = "src/a.py:1:1: E501 line too long\nsrc/b.py:2:1: E501 line too long\n"
        with patch(
            "yggtools.quality.checks.lint.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_ruff(tmp_path)
        assert not result.passed
        assert "2" in result.detail


class TestCheckFlake8:
    """Tests for check_flake8."""

    def test_passes_when_flake8_exits_0(self, tmp_path: Path) -> None:
        """Requirement: check_flake8 must pass when flake8 exits 0."""
        with patch("yggtools.quality.checks.lint.run_uv", return_value=_passing()):
            result = check_flake8(tmp_path)
        assert result.passed

    def test_fails_and_counts_violations(self, tmp_path: Path) -> None:
        """Requirement: check_flake8 detail must include violation count."""
        output = "src/a.py:1:1: E501\nsrc/b.py:2:1: W291\n"
        with patch(
            "yggtools.quality.checks.lint.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_flake8(tmp_path)
        assert not result.passed
        assert "2" in result.detail


class TestCheckTypecheck:
    """Tests for check_typecheck."""

    def test_passes_on_clean_output(self, tmp_path: Path) -> None:
        """Requirement: check_typecheck must pass when mypy exits 0."""
        with patch(
            "yggtools.quality.checks.typecheck.run_uv",
            return_value=_passing(stdout="Success: no issues found"),
        ):
            result = check_typecheck(tmp_path)
        assert result.passed

    def test_fails_and_counts_errors(self, tmp_path: Path) -> None:
        """Requirement: check_typecheck detail must count ': error:' lines."""
        output = "src/a.py:1: error: Incompatible\nsrc/b.py:2: error: Missing\n"
        with patch(
            "yggtools.quality.checks.typecheck.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_typecheck(tmp_path)
        assert not result.passed
        assert "2" in result.detail


class TestCheckSecurityCode:
    """Tests for check_security_code."""

    def test_passes_on_zero_issues(self, tmp_path: Path) -> None:
        """Requirement: check_security_code must pass when bandit exits 0."""
        with patch(
            "yggtools.quality.checks.security.run_uv", return_value=_passing()
        ):
            result = check_security_code(tmp_path)
        assert result.passed

    def test_fails_on_non_zero_exit(self, tmp_path: Path) -> None:
        """Requirement: check_security_code must fail when bandit exits non-0."""
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_failing(stdout=">> Issue [B101]\n"),
        ):
            result = check_security_code(tmp_path)
        assert not result.passed


class TestCheckSecurityDeps:
    """Tests for check_security_deps."""

    def test_passes_on_zero_vulnerabilities(self, tmp_path: Path) -> None:
        """Requirement: check_security_deps must pass when pip-audit exits 0."""
        with patch(
            "yggtools.quality.checks.security.run_uv", return_value=_passing()
        ):
            result = check_security_deps(tmp_path)
        assert result.passed

    def test_fails_on_vulnerability_found(self, tmp_path: Path) -> None:
        """Requirement: check_security_deps must fail when pip-audit exits 1."""
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_failing(stdout="1 vulnerability found\n"),
        ):
            result = check_security_deps(tmp_path)
        assert not result.passed


class TestCheckTests:
    """Tests for check_tests."""

    def test_passes_when_pytest_exits_0(self, tmp_path: Path) -> None:
        """Requirement: check_tests must pass when pytest exits 0."""
        with patch(
            "yggtools.quality.checks.tests.run_uv",
            return_value=_passing(stdout="5 passed in 0.5s"),
        ):
            result = check_tests(tmp_path)
        assert result.passed

    def test_fails_when_pytest_exits_1(self, tmp_path: Path) -> None:
        """Requirement: check_tests must fail when pytest exits 1."""
        with patch(
            "yggtools.quality.checks.tests.run_uv",
            return_value=_failing(stdout="2 failed, 3 passed in 1.2s"),
        ):
            result = check_tests(tmp_path)
        assert not result.passed
        assert "failed" in result.detail


class TestCheckMetrics:
    """Tests for check_metrics (pure Python, no subprocess)."""

    def test_passes_for_simple_module(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must pass for a module within thresholds."""
        src = tmp_path / "src" / "mypkg"
        src.mkdir(parents=True)
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n"
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.yggtools.code_metrics]\n"
            'paths = ["src"]\n'
            "exclude = []\n"
            "max_cyclomatic_complexity = 10\n"
            "max_module_logical_lines = 900\n"
        )
        result = check_metrics(tmp_path)
        assert result.passed

    def test_fails_when_complexity_exceeded(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must fail when CC exceeds threshold."""
        src = tmp_path / "src"
        src.mkdir()
        complex_fn = "\n".join([
            "def complex_fn(x):",
            *[f"    if x == {i}: return {i}" for i in range(12)],
            "    return 0",
        ])
        (src / "complex.py").write_text(complex_fn)
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.yggtools.code_metrics]\n"
            'paths = ["src"]\n'
            "exclude = []\n"
            "max_cyclomatic_complexity = 5\n"
            "max_module_logical_lines = 900\n"
        )
        result = check_metrics(tmp_path)
        assert not result.passed
        assert "CC=" in result.detail
