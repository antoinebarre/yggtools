"""Unit tests for individual quality check functions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from yggtools.quality.checks.format import check_format
from yggtools.quality.checks.lint import check_flake8, check_ruff
from yggtools.quality.checks.metrics import (
    _read_metrics_section,
    _relative_to,
    check_metrics,
)
from yggtools.quality.checks.security import (
    check_security_code,
    check_security_deps,
)
from yggtools.quality.checks.tests import _parse_summary, check_tests
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
        with patch(
            "yggtools.quality.checks.format.run_uv",
            return_value=_passing(),
        ):
            result = check_format(tmp_path)
        assert result.passed
        assert result.name == "format"

    def test_fails_and_counts_files_to_reformat(self, tmp_path: Path) -> None:
        """Requirement: check_format detail must count reformat lines."""
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
        with patch(
            "yggtools.quality.checks.lint.run_uv",
            return_value=_passing(),
        ):
            result = check_ruff(tmp_path)
        assert result.passed

    def test_fails_and_includes_error_count(self, tmp_path: Path) -> None:
        """Requirement: check_ruff detail must include the error count."""
        output = "src/a.py:1:1: E501 line too long\nsrc/b.py:2:1: E501\n"
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
        with patch(
            "yggtools.quality.checks.lint.run_uv",
            return_value=_passing(),
        ):
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
        output = (
            "src/a.py:1: error: Incompatible\nsrc/b.py:2: error: Missing\n"
        )
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
            "yggtools.quality.checks.security.run_uv",
            return_value=_passing(),
        ):
            result = check_security_code(tmp_path)
        assert result.passed

    def test_fails_on_non_zero_exit(self, tmp_path: Path) -> None:
        """Requirement: check_security_code must fail on non-zero exit."""
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_failing(stdout=">> Issue [B101]\n"),
        ):
            result = check_security_code(tmp_path)
        assert not result.passed


class TestCheckSecurityDeps:
    """Tests for check_security_deps."""

    def test_passes_on_zero_vulnerabilities(self, tmp_path: Path) -> None:
        """Requirement: check_security_deps must pass on zero exit."""
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_passing(),
        ):
            result = check_security_deps(tmp_path)
        assert result.passed

    def test_fails_on_vulnerability_found(self, tmp_path: Path) -> None:
        """Requirement: check_security_deps must fail on non-zero exit."""
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_failing(stdout="1 vulnerability found\n"),
        ):
            result = check_security_deps(tmp_path)
        assert not result.passed


class TestParseSummary:
    """Tests for _parse_summary."""

    def test_combines_counts_and_coverage(self) -> None:
        """Requirement: summary must join counts and coverage with ·."""
        output = "====== 103 passed in 0.64s ======\nTotal coverage: 100.00%\n"
        assert (
            _parse_summary(output) == "103 passed in 0.64s · coverage 100.00%"
        )

    def test_strips_equals_from_result_line(self) -> None:
        """Requirement: _parse_summary must remove = separators."""
        output = "===== 5 passed in 0.1s ====="
        assert "=" not in _parse_summary(output)

    def test_counts_only_when_no_coverage(self) -> None:
        """Requirement: summary shows counts alone when no coverage line."""
        output = "3 passed in 0.2s"
        assert _parse_summary(output) == "3 passed in 0.2s"

    def test_coverage_only_when_no_counts(self) -> None:
        """Requirement: summary shows coverage alone when no counts line."""
        output = "Total coverage: 87.00%"
        assert _parse_summary(output) == "coverage 87.00%"

    def test_returns_last_line_as_fallback(self) -> None:
        """Requirement: _parse_summary falls back to last line."""
        output = "some unexpected output\nlast line"
        assert _parse_summary(output) == "last line"

    def test_returns_empty_string_on_empty_output(self) -> None:
        """Requirement: _parse_summary returns empty string on empty input."""
        assert _parse_summary("") == ""


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

    def test_detail_combines_counts_and_coverage(self, tmp_path: Path) -> None:
        """Requirement: detail must include counts and coverage percentage."""
        stdout = "====== 103 passed in 0.64s ======\nTotal coverage: 100.00%\n"
        with patch(
            "yggtools.quality.checks.tests.run_uv",
            return_value=_passing(stdout=stdout),
        ):
            result = check_tests(tmp_path)
        assert "103 passed" in result.detail
        assert "100.00%" in result.detail
        assert "=" not in result.detail

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

    def _simple_metrics_result(self, tmp_path: Path) -> CheckResult:
        """Return metrics result for a minimal module."""
        src = tmp_path / "src" / "mypkg"
        src.mkdir(parents=True)
        (src / "simple.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
        )
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.yggtools.code_metrics]\n"
            'paths = ["src"]\n'
            "exclude = []\n"
            "max_cyclomatic_complexity = 10\n"
            "max_module_logical_lines = 900\n",
        )
        return check_metrics(tmp_path)

    def test_passes_for_simple_module(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must pass when thresholds are met."""
        result = self._simple_metrics_result(tmp_path)
        assert result.passed
        summary = result.metadata["summary"]
        assert isinstance(summary, dict)
        assert summary["python_files_parsed"] == 1
        assert summary["total_functions"] == 1
        assert summary["max_cyclomatic_complexity"] == 1

    def test_reports_function_metrics(self, tmp_path: Path) -> None:
        """Requirement: metrics report must include function measurements."""
        result = self._simple_metrics_result(tmp_path)
        functions = result.metadata["functions"]
        assert isinstance(functions, list)
        assert functions[0]["name"] == "add"
        assert functions[0]["cyclomatic_complexity"] == 1
        assert "Metrics summary" in result.stdout
        assert "src/mypkg/simple.py" in result.stdout

    def _write_pyproject(
        self,
        tmp_path: Path,
        *,
        max_cc: int = 10,
        max_lines: int = 900,
    ) -> None:
        """Write a minimal pyproject with yggtools metrics config.

        Args:
            tmp_path: Project root directory.
            max_cc: Maximum cyclomatic complexity threshold.
            max_lines: Maximum logical lines threshold.
        """
        (tmp_path / "pyproject.toml").write_text(
            "[tool.yggtools.code_metrics]\n"
            'paths = ["src"]\n'
            "exclude = []\n"
            f"max_cyclomatic_complexity = {max_cc}\n"
            f"max_module_logical_lines = {max_lines}\n",
        )

    def test_fails_when_complexity_exceeded(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must fail when CC exceeds threshold."""
        src = tmp_path / "src"
        src.mkdir()
        complex_fn = "\n".join(
            [
                "def complex_fn(x):",
                *[f"    if x == {i}: return {i}" for i in range(12)],
                "    return 0",
            ],
        )
        (src / "complex.py").write_text(complex_fn)
        self._write_pyproject(tmp_path, max_cc=5)
        result = check_metrics(tmp_path)
        assert not result.passed
        assert "CC=" in result.detail

    def test_counts_bool_op_branches(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must count bool operators as branches."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "boolop.py").write_text(
            "def fn(a, b, c, d, e, f, g, h):\n"
            "    return a and b and c and d and e and f and g and h\n",
        )
        self._write_pyproject(tmp_path, max_cc=5)
        result = check_metrics(tmp_path)
        assert not result.passed

    def test_counts_ternary_as_branch(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must count ternary as a branch."""
        src = tmp_path / "src"
        src.mkdir()
        ternary_fn = (
            "def fn(x):\n"
            "    return "
            + " if x else ".join([str(i) for i in range(8)])
            + "\n"
        )
        (src / "ternary.py").write_text(ternary_fn)
        self._write_pyproject(tmp_path, max_cc=5)
        result = check_metrics(tmp_path)
        assert not result.passed

    def test_fails_when_line_count_exceeded(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must fail when line count exceeds max."""
        src = tmp_path / "src"
        src.mkdir()
        lines = "\n".join(f"x{i} = {i}" for i in range(20))
        (src / "big.py").write_text(lines + "\n")
        self._write_pyproject(tmp_path, max_lines=5)
        result = check_metrics(tmp_path)
        assert not result.passed
        assert "logical lines" in result.detail

    def test_skips_files_with_syntax_errors(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must skip files that cannot be parsed."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "broken.py").write_text("def (:\n")
        self._write_pyproject(tmp_path)
        result = check_metrics(tmp_path)
        assert result.passed

    def test_skips_excluded_files(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must skip excluded files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "excluded.py").write_text(
            "\n".join(f"x{i} = {i}" for i in range(20)) + "\n",
        )
        (tmp_path / "pyproject.toml").write_text(
            "[tool.yggtools.code_metrics]\n"
            'paths = ["src"]\n'
            'exclude = ["*/excluded.py"]\n'
            "max_cyclomatic_complexity = 10\n"
            "max_module_logical_lines = 5\n",
        )
        result = check_metrics(tmp_path)
        assert result.passed

    def test_skips_nonexistent_paths(self, tmp_path: Path) -> None:
        """Requirement: check_metrics must skip nonexistent paths."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.yggtools.code_metrics]\n"
            'paths = ["nonexistent"]\n'
            "exclude = []\n"
            "max_cyclomatic_complexity = 10\n"
            "max_module_logical_lines = 900\n",
        )
        result = check_metrics(tmp_path)
        assert result.passed

    def test_writes_checksum_manifest_for_configured_files(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: metrics must checksum all configured files."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "module.py").write_text("x = 1\n", encoding="utf-8")
        (src / "data.txt").write_text("trace me\n", encoding="utf-8")
        cache = src / "__pycache__"
        cache.mkdir()
        (cache / "module.cpython-312.pyc").write_bytes(b"cache")
        self._write_pyproject(tmp_path)

        result = check_metrics(tmp_path)

        manifest = tmp_path / "work" / "ci" / "artifacts" / "metrics"
        manifest_json = manifest / "files-manifest.json"
        manifest_sha = manifest / "files-manifest.sha256"
        payload = json.loads(manifest_json.read_text(encoding="utf-8"))
        paths = {record["path"] for record in payload}
        assert result.passed
        assert paths == {"src/data.txt", "src/module.py"}
        files = result.metadata["files"]
        assert isinstance(files, list)
        assert files[0]["logical_lines"] == 1
        assert all(record["sha256"] for record in payload)
        digest = hashlib.sha256(
            manifest_json.read_text(encoding="utf-8").encode("utf-8"),
        ).hexdigest()
        assert manifest_sha.read_text(encoding="utf-8").startswith(digest)
        assert manifest_json in result.artifacts

    def test_read_metrics_section_returns_empty_when_file_absent(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _read_metrics_section returns {} when absent."""
        assert _read_metrics_section(tmp_path / "nonexistent.toml") == {}

    def test_relative_to_returns_absolute_external_path(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: metrics path helper must handle external paths."""
        external = Path("/outside/project.py")
        assert _relative_to(external, tmp_path) == str(external)

    def test_read_metrics_section_returns_empty_when_tool_not_dict(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _read_metrics_section returns {} when tool is int."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("tool = 42\n")
        assert _read_metrics_section(pyproject) == {}

    def test_read_metrics_section_returns_empty_when_yggtools_not_dict(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _read_metrics_section returns {} when yggtools int."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool]\nyggtools = 99\n")
        assert _read_metrics_section(pyproject) == {}

    def test_read_metrics_section_returns_empty_when_code_metrics_not_dict(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _read_metrics_section returns {} when metrics int."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.yggtools]\ncode_metrics = 0\n")
        assert _read_metrics_section(pyproject) == {}
