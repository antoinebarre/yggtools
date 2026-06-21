"""Unit tests for yggtools.quality.pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from yggtools.quality.pipeline import (
    STAGES,
    PipelineResult,
    _check_payload,
    _json_safe,
    _relative,
    _result_status,
    _write_json,
    run_pipeline,
    write_pipeline_artifacts,
)
from yggtools.quality.runner import (
    _REGISTRY,
    CheckFn,
    CheckResult,
    registered_checks,
)


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


class TestStages:
    """Tests for pipeline stage definitions."""

    def test_stages_are_non_empty(self) -> None:
        """Requirement: STAGES must contain at least one stage."""
        assert len(STAGES) > 0

    def test_stages_have_unique_names(self) -> None:
        """Requirement: each stage name must be unique."""
        names = [s.name for s in STAGES]
        assert len(names) == len(set(names))

    def test_all_stage_checks_are_valid_names(self) -> None:
        """Requirement: stage checks must reference registered names."""
        known = set(registered_checks())
        for stage in STAGES:
            for check in stage.checks:
                assert check in known, f"{check} not registered"

    def test_stages_cover_all_registered_checks(self) -> None:
        """Requirement: every registered check appears in a stage."""
        stage_checks = {c for stage in STAGES for c in stage.checks}
        for name in registered_checks():
            assert name in stage_checks, f"{name} missing from stages"


class TestRunPipeline:
    """Tests for run_pipeline."""

    def test_returns_all_results(self, tmp_path: Path) -> None:
        """Requirement: run_pipeline must return one result per check."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        _REGISTRY["ruff"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("ruff"),
        )
        try:
            result = run_pipeline(tmp_path)
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        names = {r.name for r in result.results}
        assert "format" in names
        assert "ruff" in names

    def test_passed_is_true_when_all_pass(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: pipeline must pass when all checks pass."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        try:
            result = run_pipeline(tmp_path)
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.passed

    def test_passed_is_false_when_any_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: pipeline must fail when any check fails."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format", passed=False),
        )
        try:
            result = run_pipeline(tmp_path)
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert not result.passed

    def test_measures_duration(self, tmp_path: Path) -> None:
        """Requirement: pipeline must measure total duration."""
        original = dict(_REGISTRY)
        _REGISTRY.clear()
        _REGISTRY["format"] = cast(
            "CheckFn",
            lambda _p: _dummy_result("format"),
        )
        try:
            result = run_pipeline(tmp_path)
        finally:
            _REGISTRY.clear()
            _REGISTRY.update(original)
        assert result.duration_seconds >= 0


class TestWritePipelineArtifacts:
    """Tests for write_pipeline_artifacts."""

    def test_writes_per_check_json(self, tmp_path: Path) -> None:
        """Requirement: artifacts must include one JSON per check."""
        result = PipelineResult(
            results=(_dummy_result("format"),),
            duration_seconds=0.5,
            passed=True,
        )
        report = write_pipeline_artifacts(
            result,
            tmp_path,
            tmp_path / "reports",
        )
        path, digest = report.check_reports["format"]
        assert path.exists()
        assert len(digest) == 64

    def test_writes_sha256_sidecars(self, tmp_path: Path) -> None:
        """Requirement: each JSON must have a .sha256 sidecar."""
        result = PipelineResult(
            results=(_dummy_result("format"),),
            duration_seconds=0.5,
            passed=True,
        )
        report = write_pipeline_artifacts(
            result,
            tmp_path,
            tmp_path / "reports",
        )
        path, _digest = report.check_reports["format"]
        sidecar = path.with_suffix(".json.sha256")
        assert sidecar.exists()

    def test_writes_pipeline_json(self, tmp_path: Path) -> None:
        """Requirement: artifacts must include pipeline.json summary."""
        result = PipelineResult(
            results=(_dummy_result("format"),),
            duration_seconds=0.5,
            passed=True,
        )
        report = write_pipeline_artifacts(
            result,
            tmp_path,
            tmp_path / "reports",
        )
        assert report.summary_path is not None
        assert report.summary_path.exists()
        payload = json.loads(report.summary_path.read_text())
        assert payload["schema"] == "yggtools.pipeline.v1"
        assert payload["passed"] is True

    def test_pipeline_json_includes_artifact_digests(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: pipeline.json must list per-check SHA-256."""
        result = PipelineResult(
            results=(_dummy_result("format"),),
            duration_seconds=0.5,
            passed=True,
        )
        report = write_pipeline_artifacts(
            result,
            tmp_path,
            tmp_path / "reports",
        )
        assert report.summary_path is not None
        payload = json.loads(report.summary_path.read_text())
        assert "format" in payload["artifacts"]
        assert "sha256" in payload["artifacts"]["format"]

    def test_defaults_to_work_reports_dir(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: default output dir is work/reports/."""
        result = PipelineResult(
            results=(_dummy_result("format"),),
            duration_seconds=0.5,
            passed=True,
        )
        report = write_pipeline_artifacts(result, tmp_path)
        assert report.summary_path is not None
        assert "work/reports" in str(report.summary_path)


class TestCheckPayload:
    """Tests for _check_payload."""

    def test_includes_schema_and_status(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: payload must include schema and status."""
        payload = _check_payload(_dummy_result(), tmp_path)
        assert payload["schema"] == "yggtools.ci.check.v1"
        assert payload["status"] == "pass"

    def test_includes_stdout_and_stderr(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: payload must preserve full output."""
        result = CheckResult(
            name="x",
            passed=True,
            detail="ok",
            stdout="out",
            stderr="err",
        )
        payload = _check_payload(result, tmp_path)
        assert payload["stdout"] == "out"
        assert payload["stderr"] == "err"

    def test_warning_payload_uses_warning_status(self, tmp_path: Path) -> None:
        """Requirement: non-blocking warnings must publish warning JSON."""
        result = CheckResult(
            name="todos",
            passed=True,
            detail="1 todo(s)",
            metadata={
                "severity": "warning",
                "warning_count": 1,
                "findings": [{"path": "src/a.py", "line": 1}],
            },
        )
        payload = _check_payload(result, tmp_path)
        assert payload["status"] == "warning"
        assert payload["passed"] is True

    def test_zero_warning_payload_uses_pass_status(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: empty warning checks remain plain passes."""
        result = CheckResult(
            name="todos",
            passed=True,
            detail="0 todo(s)",
            metadata={"severity": "warning", "warning_count": 0},
        )
        assert _result_status(result) == "pass"


class TestHelpers:
    """Tests for pipeline helper functions."""

    def test_relative_inside_project(self, tmp_path: Path) -> None:
        """Requirement: _relative returns relative for child paths."""
        child = tmp_path / "src" / "a.py"
        assert _relative(child, tmp_path) == "src/a.py"

    def test_relative_outside_project(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _relative returns absolute for external paths."""
        external = Path("/outside/a.py")
        assert _relative(external, tmp_path) == str(external)

    def test_json_safe_converts_paths(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _json_safe must convert Path to relative str."""
        result = _json_safe(tmp_path / "src", tmp_path)
        assert result == "src"

    def test_json_safe_converts_tuples(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _json_safe must convert tuples to lists."""
        result = _json_safe((1, 2), tmp_path)
        assert result == [1, 2]

    def test_json_safe_converts_lists(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _json_safe must recurse into lists."""
        result = _json_safe([tmp_path / "a"], tmp_path)
        assert result == ["a"]

    def test_write_json_creates_file_and_sidecar(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: _write_json must create .json and .sha256."""
        path = tmp_path / "test.json"
        digest = _write_json({"key": "value"}, path)
        assert path.exists()
        assert path.with_suffix(".json.sha256").exists()
        assert len(digest) == 64
