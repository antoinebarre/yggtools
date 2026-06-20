"""Quality pipeline: staged orchestration of all quality checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from yggtools.quality.runner import CheckResult, registered_checks, run_one


@dataclass(frozen=True)
class Stage:
    """A named group of checks that run together.

    Attributes:
        name: Human-readable stage label.
        checks: Ordered list of registered check names.
    """

    name: str
    checks: tuple[str, ...]


STAGES: tuple[Stage, ...] = (
    Stage("Linters", ("format", "ruff", "flake8")),
    Stage("Type checking", ("typecheck",)),
    Stage("Metrics", ("metrics",)),
    Stage("Security", ("security-code", "security-deps")),
    Stage("Tests & coverage", ("tests",)),
)


@dataclass(frozen=True)
class PipelineResult:
    """Outcome of a full pipeline execution.

    Attributes:
        results: Ordered check results from all stages.
        duration_seconds: Total wall-clock time for the pipeline.
        passed: True when every check passed.
    """

    results: tuple[CheckResult, ...]
    duration_seconds: float
    passed: bool


@dataclass
class PipelineReport:
    """Artifact paths and checksums produced by one pipeline run.

    Attributes:
        check_reports: Mapping of check name to (path, sha256) pairs.
        summary_path: Path to the consolidated pipeline.json.
        summary_digest: SHA-256 digest of pipeline.json.
    """

    check_reports: dict[str, tuple[Path, str]] = field(default_factory=dict)
    summary_path: Path | None = None
    summary_digest: str = ""


def run_pipeline(project_dir: Path) -> PipelineResult:
    """Execute all pipeline stages in order.

    Every registered check runs regardless of earlier failures so the
    developer gets the full picture in one invocation.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        PipelineResult with all check outcomes and total duration.
    """
    started = perf_counter()
    known = set(registered_checks())
    results: list[CheckResult] = []
    for stage in STAGES:
        results.extend(
            run_one(name, project_dir)
            for name in stage.checks
            if name in known
        )
    elapsed = perf_counter() - started
    passed = all(r.passed for r in results)
    return PipelineResult(
        results=tuple(results),
        duration_seconds=elapsed,
        passed=passed,
    )


def write_pipeline_artifacts(
    result: PipelineResult,
    project_dir: Path,
    output_dir: Path | None = None,
) -> PipelineReport:
    """Write JSON artifacts for every check and a consolidated summary.

    Args:
        result: Pipeline execution result.
        project_dir: Project root directory.
        output_dir: Destination directory for artifacts.  Defaults to
            ``work/reports/`` under ``project_dir``.

    Returns:
        PipelineReport with paths and SHA-256 digests for all artifacts.
    """
    reports_dir = output_dir or (project_dir / "work" / "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    report = PipelineReport()
    for check_result in result.results:
        path = reports_dir / f"{check_result.name}.json"
        payload = _check_payload(check_result, project_dir)
        digest = _write_json(payload, path)
        report.check_reports[check_result.name] = (path, digest)

    summary_path = reports_dir / "pipeline.json"
    summary_payload = _summary_payload(result, project_dir, report)
    report.summary_digest = _write_json(summary_payload, summary_path)
    report.summary_path = summary_path
    return report


def _check_payload(
    result: CheckResult,
    project_dir: Path,
) -> dict[str, object]:
    """Build the JSON contract for one check result.

    Args:
        result: Single check result.
        project_dir: Project root for relative path computation.

    Returns:
        JSON-safe dictionary.
    """
    return {
        "schema": "yggtools.ci.check.v1",
        "check": result.name,
        "status": "pass" if result.passed else "fail",
        "passed": result.passed,
        "detail": result.detail,
        "duration_seconds": result.duration_seconds,
        "command": list(result.command) if result.command else None,
        "artifacts": [_relative(a, project_dir) for a in result.artifacts],
        "metadata": _json_safe(result.metadata, project_dir),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _summary_payload(
    result: PipelineResult,
    project_dir: Path,
    report: PipelineReport,
) -> dict[str, object]:
    """Build the consolidated pipeline.json payload.

    Args:
        result: Full pipeline result.
        project_dir: Project root directory.
        report: Artifact report with per-check digests.

    Returns:
        JSON-safe dictionary for pipeline.json.
    """
    passed_count = sum(1 for r in result.results if r.passed)
    failed_count = len(result.results) - passed_count
    return {
        "schema": "yggtools.pipeline.v1",
        "status": "pass" if result.passed else "fail",
        "passed": result.passed,
        "total_checks": len(result.results),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "duration_seconds": result.duration_seconds,
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": project_dir.name,
        "checks": {
            r.name: {
                "status": "pass" if r.passed else "fail",
                "detail": r.detail,
                "duration_seconds": r.duration_seconds,
            }
            for r in result.results
        },
        "artifacts": {
            name: {
                "path": _relative(path, project_dir),
                "sha256": digest,
            }
            for name, (path, digest) in report.check_reports.items()
        },
    }


def _write_json(payload: dict[str, object], path: Path) -> str:
    """Write a JSON payload and its SHA-256 sidecar file.

    Args:
        payload: JSON-serialisable dictionary.
        path: Destination path for the JSON file.

    Returns:
        SHA-256 hex digest of the written content.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, indent=2, sort_keys=True, default=str)
    content += "\n"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    path.write_text(content, encoding="utf-8")
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n",
        encoding="utf-8",
    )
    return digest


def _relative(path: Path, project_dir: Path) -> str:
    """Return path relative to project_dir when possible.

    Args:
        path: Absolute or relative path.
        project_dir: Project root directory.

    Returns:
        Relative path string, or absolute if outside project.
    """
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _json_safe(value: object, project_dir: Path) -> object:
    """Convert values to JSON-safe types.

    Args:
        value: Value to convert.
        project_dir: Project root for path relativisation.

    Returns:
        JSON-safe equivalent.
    """
    if isinstance(value, Path):
        return _relative(value, project_dir)
    if isinstance(value, tuple):
        return [_json_safe(item, project_dir) for item in value]
    if isinstance(value, list):
        return [_json_safe(item, project_dir) for item in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v, project_dir) for k, v in value.items()}
    return value
