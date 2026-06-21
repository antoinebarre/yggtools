"""Unit tests for individual quality check functions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from yggtools.quality.checks.format import _parse_findings, check_format
from yggtools.quality.checks.lint import (
    _parse_lint_findings,
    check_flake8,
    check_ruff,
)
from yggtools.quality.checks.metrics import (
    _read_metrics_section,
    _relative_to,
    check_metrics,
)
from yggtools.quality.checks.security import (
    _parse_bandit_findings,
    _parse_pip_audit_findings,
    check_security_code,
    check_security_deps,
)
from yggtools.quality.checks.tests import (
    _parse_summary,
    _parse_test_findings,
    check_tests,
)
from yggtools.quality.checks.typecheck import (
    _parse_mypy_findings,
    check_typecheck,
)
from yggtools.quality.checks.version import (
    _collect_version_artifacts,
    _package_dir,
    _read_init_version,
    _read_lock_version,
    _read_pyproject_identity,
    check_version_consistency,
)
from yggtools.quality.checks.version import (
    _relative_to as _relative_version_path,
)
from yggtools.quality.checks.warnings import (
    _relative_to as _relative_warning_path,
)
from yggtools.quality.checks.warnings import (
    check_lint_suppressions,
    check_todos,
    collect_lint_suppressions,
    collect_todos,
)
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


# ── format ───────────────────────────────────────────────────────────────


class TestParseFormatFindings:
    """Tests for _parse_findings."""

    def test_extracts_reformat_paths(self) -> None:
        """Requirement: must extract paths from reformat lines."""
        output = (
            "Would reformat: src/a.py\n"
            "Would reformat: src/b.py\n"
            "2 files would be reformatted\n"
        )
        findings = _parse_findings(output)
        assert len(findings) == 2
        assert findings[0]["path"] == "src/a.py"
        assert findings[1]["path"] == "src/b.py"

    def test_returns_empty_on_no_matches(self) -> None:
        """Requirement: must return empty list on clean output."""
        assert _parse_findings("All files formatted\n") == []


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

    def test_fails_with_findings(self, tmp_path: Path) -> None:
        """Requirement: check_format must include structured findings."""
        output = "Would reformat: src/a.py\nWould reformat: src/b.py\n"
        with patch(
            "yggtools.quality.checks.format.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_format(tmp_path)
        assert not result.passed
        assert "2" in result.detail
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 2
        assert findings[0]["path"] == "src/a.py"


# ── ruff / flake8 ────────────────────────────────────────────────────────


class TestParseLintFindings:
    """Tests for _parse_lint_findings."""

    def test_parses_standard_lint_line(self) -> None:
        """Requirement: must parse path:line:col: CODE message."""
        output = "src/a.py:1:1: E501 line too long\n"
        findings = _parse_lint_findings(output)
        assert len(findings) == 1
        assert findings[0]["path"] == "src/a.py"
        assert findings[0]["line"] == 1
        assert findings[0]["column"] == 1
        assert findings[0]["code"] == "E501"
        assert findings[0]["message"] == "line too long"

    def test_ignores_summary_lines(self) -> None:
        """Requirement: must skip non-matching lines."""
        output = "Found 3 errors.\n"
        assert _parse_lint_findings(output) == []

    def test_parses_multiple_findings(self) -> None:
        """Requirement: must parse multiple lint findings."""
        output = (
            "src/a.py:1:1: E501 line too long\n"
            "src/b.py:2:5: W291 trailing whitespace\n"
        )
        findings = _parse_lint_findings(output)
        assert len(findings) == 2


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

    def test_fails_with_findings(self, tmp_path: Path) -> None:
        """Requirement: check_ruff must include structured findings."""
        output = (
            "src/a.py:1:1: E501 line too long\n"
            "src/b.py:2:1: E501 line too long\n"
        )
        with patch(
            "yggtools.quality.checks.lint.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_ruff(tmp_path)
        assert not result.passed
        assert "2" in result.detail
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 2

    def test_handles_no_parseable_findings(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: check_ruff must handle unparseable output."""
        with patch(
            "yggtools.quality.checks.lint.run_uv",
            return_value=_failing(stdout="error\n"),
        ):
            result = check_ruff(tmp_path)
        assert not result.passed
        assert result.metadata["findings"] == []


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

    def test_fails_with_findings(self, tmp_path: Path) -> None:
        """Requirement: check_flake8 must include structured findings."""
        output = "src/a.py:1:1: E501 line\nsrc/b.py:2:1: W291 ws\n"
        with patch(
            "yggtools.quality.checks.lint.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_flake8(tmp_path)
        assert not result.passed
        assert "2" in result.detail
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 2


# ── warning audits ───────────────────────────────────────────────────────


class TestWarningAudits:
    """Tests for non-blocking warning audit checks."""

    def test_collects_lint_suppressions(self, tmp_path: Path) -> None:
        """Requirement: lint suppressions must be listed as warnings."""
        package = tmp_path / "src" / "yggtools"
        package.mkdir(parents=True)
        (package / "sample.py").write_text(
            "value = 1  # noqa: E501\nother = 2  # type: ignore[arg-type]\n",
            encoding="utf-8",
        )
        findings = collect_lint_suppressions(tmp_path)
        assert len(findings) == 2
        assert findings[0]["marker"] == "noqa"
        assert findings[1]["marker"] == "type-ignore"

    def test_missing_package_has_no_suppressions(self, tmp_path: Path) -> None:
        """Requirement: missing packages must yield no suppressions."""
        assert collect_lint_suppressions(tmp_path) == []

    def test_lint_suppression_check_is_non_blocking(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: lint suppression warnings must not fail checks."""
        package = tmp_path / "src" / "yggtools"
        package.mkdir(parents=True)
        (package / "sample.py").write_text(
            "value = 1  # noqa\n",
            encoding="utf-8",
        )
        result = check_lint_suppressions(tmp_path)
        assert result.passed
        assert result.metadata["severity"] == "warning"
        assert result.metadata["warning_count"] == 1

    def test_collects_package_todos(self, tmp_path: Path) -> None:
        """Requirement: package TODO markers must be listed as warnings."""
        package = tmp_path / "src" / "yggtools"
        package.mkdir(parents=True)
        (package / "sample.py").write_text(
            "# TODO(@antoinebarre): finish it.\n",
            encoding="utf-8",
        )
        findings = collect_todos(tmp_path)
        assert len(findings) == 1
        assert findings[0]["marker"] == "todo"
        assert "finish it" in str(findings[0]["text"])

    def test_warning_relative_path_allows_external_paths(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: external warning paths must remain absolute."""
        external = Path("/outside/a.py")
        assert _relative_warning_path(external, tmp_path) == str(external)

    def test_todo_check_is_non_blocking(self, tmp_path: Path) -> None:
        """Requirement: TODO warnings must not fail checks."""
        package = tmp_path / "src" / "yggtools"
        package.mkdir(parents=True)
        (package / "sample.py").write_text(
            "# FIXME: later\n",
            encoding="utf-8",
        )
        result = check_todos(tmp_path)
        assert result.passed
        assert result.metadata["severity"] == "warning"
        assert result.metadata["warning_count"] == 1


# ── version consistency ─────────────────────────────────────────────────


class TestVersionConsistency:
    """Tests for package version consistency checks."""

    def test_reads_pyproject_identity(self, tmp_path: Path) -> None:
        """Requirement: pyproject name and version must be extracted."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "my-lib"\nversion = "1.2.3"\n',
            encoding="utf-8",
        )
        assert _read_pyproject_identity(pyproject) == ("my-lib", "1.2.3")

    def test_missing_pyproject_has_no_identity(self, tmp_path: Path) -> None:
        """Requirement: missing pyproject yields no name or version."""
        assert _read_pyproject_identity(tmp_path / "pyproject.toml") == (
            "",
            None,
        )

    def test_invalid_project_section_has_no_identity(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: non-table project section is ignored."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('project = "bad"\n', encoding="utf-8")
        assert _read_pyproject_identity(pyproject) == ("", None)

    def test_non_string_pyproject_values_are_ignored(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: non-string project identity fields are ignored."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\nname = 1\nversion = 2\n",
            encoding="utf-8",
        )
        assert _read_pyproject_identity(pyproject) == ("", None)

    def test_reads_init_version(self, tmp_path: Path) -> None:
        """Requirement: __version__ must be extracted from __init__.py."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text('__version__ = "1.2.3"\n', encoding="utf-8")
        assert _read_init_version(init_file) == "1.2.3"

    def test_missing_init_version_returns_none(self, tmp_path: Path) -> None:
        """Requirement: absent __init__.py has no version."""
        assert _read_init_version(tmp_path / "__init__.py") is None

    def test_init_without_version_returns_none(self, tmp_path: Path) -> None:
        """Requirement: __init__.py without __version__ has no version."""
        init_file = tmp_path / "__init__.py"
        init_file.write_text('NAME = "my-lib"\n', encoding="utf-8")
        assert _read_init_version(init_file) is None

    def test_reads_lock_version_by_project_name(self, tmp_path: Path) -> None:
        """Requirement: uv.lock project package version is extracted."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(
            '[[package]]\nname = "my-lib"\nversion = "1.2.3"\n'
            'source = { editable = "." }\n',
            encoding="utf-8",
        )
        assert _read_lock_version(lock_file, "my-lib") == "1.2.3"

    def test_missing_lock_version_returns_none(self, tmp_path: Path) -> None:
        """Requirement: missing uv.lock has no version."""
        assert _read_lock_version(tmp_path / "uv.lock", "my-lib") is None

    def test_empty_project_name_has_no_lock_version(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: lock lookup needs a project name."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text("", encoding="utf-8")
        assert _read_lock_version(lock_file, "") is None

    def test_non_list_lock_packages_are_ignored(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: malformed lock package section is ignored."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text('package = "bad"\n', encoding="utf-8")
        assert _read_lock_version(lock_file, "my-lib") is None

    def test_non_table_lock_package_is_ignored(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: malformed package entries are ignored."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text('package = ["bad"]\n', encoding="utf-8")
        assert _read_lock_version(lock_file, "my-lib") is None

    def test_lock_package_name_mismatch_returns_none(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: lock lookup ignores other packages."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(
            '[[package]]\nname = "other"\nversion = "1.2.3"\n',
            encoding="utf-8",
        )
        assert _read_lock_version(lock_file, "my-lib") is None

    def test_lock_lookup_ignores_yggtools_dependency_version(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: dependency versions do not affect project version."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(
            '[[package]]\nname = "my-lib"\nversion = "0.3.0"\n\n'
            '[[package]]\nname = "yggtools"\nversion = "1.1.0"\n',
            encoding="utf-8",
        )
        assert _read_lock_version(lock_file, "my-lib") == "0.3.0"

    def test_lock_package_without_editable_source_is_used(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: package name identifies the current project."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(
            '[[package]]\nname = "my-lib"\nversion = "1.2.3"\n',
            encoding="utf-8",
        )
        assert _read_lock_version(lock_file, "my-lib") == "1.2.3"

    def test_non_string_lock_version_returns_none(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: non-string lock version is ignored."""
        lock_file = tmp_path / "uv.lock"
        lock_file.write_text(
            '[[package]]\nname = "my-lib"\nversion = 1\n'
            'source = { editable = "." }\n',
            encoding="utf-8",
        )
        assert _read_lock_version(lock_file, "my-lib") is None

    def test_package_dir_normalizes_hyphen(self) -> None:
        """Requirement: distribution names map to import package dirs."""
        assert _package_dir("my-lib") == "my_lib"

    def test_relative_to_falls_back_to_absolute(self, tmp_path: Path) -> None:
        """Requirement: display path outside project falls back as-is."""
        external = Path("/outside/file.txt")
        assert _relative_version_path(tmp_path, external) == str(external)

    def test_collects_known_artifacts(self, tmp_path: Path) -> None:
        """Requirement: all known version artifacts must be collected."""
        _write_version_project(tmp_path, version="1.2.3")
        artifacts = _collect_version_artifacts(tmp_path)
        assert [artifact.name for artifact in artifacts] == [
            "pyproject.project.version",
            "package.__version__",
            "uv.lock.package.version",
        ]

    def test_passes_when_versions_match(self, tmp_path: Path) -> None:
        """Requirement: check passes when all versions are equal."""
        _write_version_project(tmp_path, version="1.2.3")
        result = check_version_consistency(tmp_path)
        assert result.passed
        assert "1.2.3" in result.detail

    def test_passes_when_dependency_versions_differ(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: dependency package versions are ignored."""
        _write_version_project(tmp_path, version="0.3.0")
        (tmp_path / "uv.lock").write_text(
            '[[package]]\nname = "my-lib"\nversion = "0.3.0"\n\n'
            '[[package]]\nname = "yggtools"\nversion = "1.1.0"\n',
            encoding="utf-8",
        )
        result = check_version_consistency(tmp_path)
        assert result.passed
        assert result.metadata["versions"] == ["0.3.0"]

    def test_fails_when_versions_differ(self, tmp_path: Path) -> None:
        """Requirement: check fails on conflicting artifact versions."""
        _write_version_project(tmp_path, version="1.2.3")
        (tmp_path / "src" / "my_lib" / "__init__.py").write_text(
            '__version__ = "1.2.4"\n',
            encoding="utf-8",
        )
        result = check_version_consistency(tmp_path)
        assert not result.passed
        assert result.metadata["versions"] == ["1.2.3", "1.2.4"]

    def test_fails_when_required_artifact_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: check fails when a required version is missing."""
        _write_version_project(tmp_path, version="1.2.3")
        (tmp_path / "uv.lock").unlink()
        result = check_version_consistency(tmp_path)
        assert not result.passed
        missing = result.metadata["missing"]
        assert isinstance(missing, list)
        assert "uv.lock.package.version" in missing


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


# ── typecheck ────────────────────────────────────────────────────────────


class TestParseMypyFindings:
    """Tests for _parse_mypy_findings."""

    def test_parses_error_line(self) -> None:
        """Requirement: must parse mypy error lines."""
        output = "src/a.py:1: error: Incompatible types\n"
        findings = _parse_mypy_findings(output)
        assert len(findings) == 1
        assert findings[0]["path"] == "src/a.py"
        assert findings[0]["line"] == 1
        assert findings[0]["message"] == "Incompatible types"

    def test_ignores_notes(self) -> None:
        """Requirement: must skip non-error lines."""
        output = "src/a.py:1: note: see docs\n"
        assert _parse_mypy_findings(output) == []


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

    def test_fails_with_findings(self, tmp_path: Path) -> None:
        """Requirement: check_typecheck must include findings."""
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
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 2
        assert findings[0]["path"] == "src/a.py"


# ── security ─────────────────────────────────────────────────────────────


class TestParseBanditFindings:
    """Tests for _parse_bandit_findings."""

    def test_parses_issue_with_location(self) -> None:
        """Requirement: must parse issue and location lines."""
        output = (
            ">> Issue: [B101:assert_used] Use of assert\n"
            "   Location: src/a.py:10:0\n"
        )
        findings = _parse_bandit_findings(output)
        assert len(findings) == 1
        assert findings[0]["code"] == "B101:assert_used"
        assert findings[0]["path"] == "src/a.py"
        assert findings[0]["line"] == 10

    def test_parses_issue_without_location(self) -> None:
        """Requirement: must handle issue without location line."""
        output = ">> Issue: [B101:assert_used] Use of assert\n"
        findings = _parse_bandit_findings(output)
        assert len(findings) == 1
        assert "path" not in findings[0]

    def test_returns_empty_on_no_issues(self) -> None:
        """Requirement: must return empty list when clean."""
        assert _parse_bandit_findings("No issues.\n") == []


class TestParsePipAuditFindings:
    """Tests for _parse_pip_audit_findings."""

    def test_parses_vulnerability_line(self) -> None:
        """Requirement: must extract vulnerability lines."""
        output = "pkg 1.0 has a known vulnerability CVE-2024\n"
        findings = _parse_pip_audit_findings(output)
        assert len(findings) == 1

    def test_ignores_separator_lines(self) -> None:
        """Requirement: must skip separator lines."""
        output = "---vulnerability---\n"
        findings = _parse_pip_audit_findings(output)
        assert len(findings) == 0

    def test_returns_empty_on_clean(self) -> None:
        """Requirement: must return empty list when clean."""
        assert _parse_pip_audit_findings("No issues\n") == []


class TestCheckSecurityCode:
    """Tests for check_security_code."""

    def test_passes_on_zero_issues(self, tmp_path: Path) -> None:
        """Requirement: check_security_code must pass on zero exit."""
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_passing(),
        ):
            result = check_security_code(tmp_path)
        assert result.passed

    def test_fails_with_findings(self, tmp_path: Path) -> None:
        """Requirement: check_security_code must include findings."""
        output = (
            ">> Issue: [B101:assert_used] Use of assert\n"
            "   Location: src/a.py:10:0\n"
        )
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_security_code(tmp_path)
        assert not result.passed
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 1
        assert findings[0]["code"] == "B101:assert_used"


class TestCheckSecurityDeps:
    """Tests for check_security_deps."""

    def test_passes_on_zero_vulnerabilities(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: check_security_deps must pass on zero exit."""
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_passing(),
        ):
            result = check_security_deps(tmp_path)
        assert result.passed

    def test_fails_with_findings(self, tmp_path: Path) -> None:
        """Requirement: check_security_deps must include findings."""
        output = "pkg 1.0 has a known vulnerability CVE-2024\n"
        with patch(
            "yggtools.quality.checks.security.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_security_deps(tmp_path)
        assert not result.passed
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 1


# ── tests ────────────────────────────────────────────────────────────────


class TestParseTestFindings:
    """Tests for _parse_test_findings."""

    def test_parses_failed_test_lines(self) -> None:
        """Requirement: must extract FAILED test references."""
        output = "FAILED tests/test_a.py::test_one - assert\n"
        findings = _parse_test_findings(output)
        assert len(findings) == 1
        assert findings[0]["path"] == "tests/test_a.py"
        assert "test_one" in str(findings[0]["message"])

    def test_returns_empty_on_no_failures(self) -> None:
        """Requirement: must return empty list when no failures."""
        output = "5 passed in 0.5s\n"
        assert _parse_test_findings(output) == []


class TestParseSummary:
    """Tests for _parse_summary."""

    def test_combines_counts_and_coverage(self) -> None:
        """Requirement: summary must join counts and coverage with dot."""
        output = "====== 103 passed in 0.64s ======\nTotal coverage: 100.00%\n"
        assert (
            _parse_summary(output) == "103 passed in 0.64s · coverage 100.00%"
        )

    def test_strips_equals_from_result_line(self) -> None:
        """Requirement: _parse_summary must remove = separators."""
        output = "===== 5 passed in 0.1s ====="
        assert "=" not in _parse_summary(output)

    def test_counts_only_when_no_coverage(self) -> None:
        """Requirement: summary shows counts when no coverage line."""
        output = "3 passed in 0.2s"
        assert _parse_summary(output) == "3 passed in 0.2s"

    def test_coverage_only_when_no_counts(self) -> None:
        """Requirement: summary shows coverage when no counts line."""
        output = "Total coverage: 87.00%"
        assert _parse_summary(output) == "coverage 87.00%"

    def test_returns_last_line_as_fallback(self) -> None:
        """Requirement: _parse_summary falls back to last line."""
        output = "some unexpected output\nlast line"
        assert _parse_summary(output) == "last line"

    def test_returns_empty_string_on_empty_output(self) -> None:
        """Requirement: returns empty string on empty input."""
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

    def test_detail_combines_counts_and_coverage(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: detail must include counts and coverage."""
        stdout = "====== 103 passed in 0.64s ======\nTotal coverage: 100.00%\n"
        with patch(
            "yggtools.quality.checks.tests.run_uv",
            return_value=_passing(stdout=stdout),
        ):
            result = check_tests(tmp_path)
        assert "103 passed" in result.detail
        assert "100.00%" in result.detail
        assert "=" not in result.detail

    def test_fails_with_findings(self, tmp_path: Path) -> None:
        """Requirement: check_tests must include findings on failure."""
        output = (
            "FAILED tests/test_a.py::test_one - AssertionError\n"
            "2 failed, 3 passed in 1.2s\n"
        )
        with patch(
            "yggtools.quality.checks.tests.run_uv",
            return_value=_failing(stdout=output),
        ):
            result = check_tests(tmp_path)
        assert not result.passed
        assert "failed" in result.detail
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) == 1
        assert findings[0]["path"] == "tests/test_a.py"


# ── metrics ──────────────────────────────────────────────────────────────


class TestCheckMetrics:
    """Tests for check_metrics (pure Python, no subprocess)."""

    def _simple_metrics_result(self, tmp_path: Path) -> CheckResult:
        """Return metrics result for a minimal module.

        Args:
            tmp_path: Temporary project root.

        Returns:
            CheckResult from check_metrics.
        """
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
        """Requirement: check_metrics must pass when thresholds met."""
        result = self._simple_metrics_result(tmp_path)
        assert result.passed
        summary = result.metadata["summary"]
        assert isinstance(summary, dict)
        assert summary["python_files_parsed"] == 1
        assert summary["total_functions"] == 1
        assert summary["max_cyclomatic_complexity"] == 1

    def test_reports_function_metrics(self, tmp_path: Path) -> None:
        """Requirement: metrics must include function measurements."""
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

    def test_fails_with_findings_on_complexity(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: metrics findings must list CC violations."""
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
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) >= 1
        assert "CC=" in findings[0]["message"]

    def test_counts_bool_op_branches(self, tmp_path: Path) -> None:
        """Requirement: must count bool operators as branches."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "boolop.py").write_text(
            "def fn(a, b, c, d, e, f, g, h):\n"
            "    return a and b and c and d"
            " and e and f and g and h\n",
        )
        self._write_pyproject(tmp_path, max_cc=5)
        result = check_metrics(tmp_path)
        assert not result.passed

    def test_counts_ternary_as_branch(self, tmp_path: Path) -> None:
        """Requirement: must count ternary as a branch."""
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

    def test_fails_with_findings_on_line_count(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: metrics findings must list line violations."""
        src = tmp_path / "src"
        src.mkdir()
        lines = "\n".join(f"x{i} = {i}" for i in range(20))
        (src / "big.py").write_text(lines + "\n")
        self._write_pyproject(tmp_path, max_lines=5)
        result = check_metrics(tmp_path)
        assert not result.passed
        assert "logical lines" in result.detail
        findings = result.metadata["findings"]
        assert isinstance(findings, list)
        assert len(findings) >= 1
        assert "logical lines" in findings[0]["message"]

    def test_skips_files_with_syntax_errors(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: must skip files that cannot be parsed."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "broken.py").write_text("def (:\n")
        self._write_pyproject(tmp_path)
        result = check_metrics(tmp_path)
        assert result.passed

    def test_skips_excluded_files(self, tmp_path: Path) -> None:
        """Requirement: must skip excluded files."""
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
        """Requirement: must skip nonexistent paths."""
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
        payload = json.loads(
            manifest_json.read_text(encoding="utf-8"),
        )
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
        assert manifest_sha.read_text(encoding="utf-8").startswith(
            digest,
        )
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
        """Requirement: path helper must handle external paths."""
        external = Path("/outside/project.py")
        assert _relative_to(external, tmp_path) == str(external)

    def test_read_metrics_section_returns_empty_when_tool_not_dict(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: returns {} when tool is int."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("tool = 42\n")
        assert _read_metrics_section(pyproject) == {}

    def test_read_metrics_section_returns_empty_when_yggtools_not_dict(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: returns {} when yggtools is int."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool]\nyggtools = 99\n")
        assert _read_metrics_section(pyproject) == {}

    def test_read_metrics_section_returns_empty_when_metrics_not_dict(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: returns {} when code_metrics is int."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.yggtools]\ncode_metrics = 0\n")
        assert _read_metrics_section(pyproject) == {}
