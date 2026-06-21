"""Markdown report writers for quality pipeline results."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from yggtools.quality.runner import CheckResult

type JsonObject = dict[str, object]


def _timestamp() -> str:
    """Return a stable UTC timestamp for reports."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _status(result: CheckResult) -> str:
    """Return a plain status label for a check result."""
    return "PASS" if result.passed else "FAIL"


def _escape_table_cell(value: object) -> str:
    """Escape a value for a Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def _relative(path: Path, project_dir: Path) -> str:
    """Return path relative to project_dir when possible."""
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _format_metadata(value: object) -> str:
    """Render metadata values as compact Markdown."""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, indent=2, sort_keys=True, default=str)
    return str(value)


def _json_safe(value: object, project_dir: Path) -> object:
    """Convert supported result values to JSON-safe values."""
    if isinstance(value, Path):
        return _relative(value, project_dir)
    if isinstance(value, tuple):
        return [_json_safe(item, project_dir) for item in value]
    if isinstance(value, list):
        return [_json_safe(item, project_dir) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item, project_dir)
            for key, item in value.items()
        }
    return value


def _result_payload(result: CheckResult, project_dir: Path) -> JsonObject:
    """Build the JSON contract for one CI check result."""
    return {
        "schema": "yggtools.ci.check.v1",
        "check": result.name,
        "status": "pass" if result.passed else "fail",
        "passed": result.passed,
        "detail": result.detail,
        "duration_seconds": result.duration_seconds,
        "command": list(result.command) if result.command else None,
        "artifacts": [
            _relative(artifact, project_dir) for artifact in result.artifacts
        ],
        "metadata": _json_safe(result.metadata, project_dir),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _write_json_payload(payload: JsonObject, output: Path) -> str:
    """Write a JSON payload and its SHA-256 sidecar."""
    output.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        default=str,
    )
    content += "\n"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    output.write_text(content, encoding="utf-8")
    output.with_suffix(output.suffix + ".sha256").write_text(
        f"{digest}  {output.name}\n",
        encoding="utf-8",
    )
    return digest


def write_report(
    results: list[CheckResult],
    project_dir: Path,
    output: Path,
) -> None:
    """Write a Markdown quality report to disk.

    Creates ``output`` and any required parent directories.

    Args:
        results: Ordered list of check results to include.
        project_dir: Project root directory (used as the report title).
        output: Destination path for the Markdown file.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    timestamp = _timestamp()

    lines: list[str] = [
        f"# Quality report - {project_dir.name}",
        "",
        f"Generated: {timestamp}",
        "",
        "## Results",
        "",
        "| Check | Status | Detail |",
        "|-------|--------|--------|",
    ]
    for r in results:
        status = _status(r)
        lines.append(f"| `{r.name}` | {status} | {r.detail} |")

    lines += [
        "",
        "## Summary",
        "",
        f"**{passed} passed** / **{failed} failed**",
        "",
    ]

    output.write_text("\n".join(lines), encoding="utf-8")


def write_check_report(
    result: CheckResult,
    project_dir: Path,
    output: Path,
) -> None:
    """Write a detailed Markdown report for one quality check.

    Args:
        result: Check result to render.
        project_dir: Project root directory.
        output: Destination path for the Markdown file.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        f"# CI step - {result.name}",
        "",
        f"Generated: {_timestamp()}",
        "",
    ]
    lines += _check_summary_lines(result)
    lines += _artifact_lines(result, project_dir)
    lines += _metadata_lines(result)
    lines += _captured_output_lines("stdout", result.stdout)
    lines += _captured_output_lines("stderr", result.stderr)

    output.write_text("\n".join(lines), encoding="utf-8")


def _check_summary_lines(result: CheckResult) -> list[str]:
    """Render the summary section for one check."""
    lines = [
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Status | {_status(result)} |",
        f"| Detail | {_escape_table_cell(result.detail)} |",
    ]
    if result.duration_seconds is not None:
        lines.append(f"| Duration | {result.duration_seconds:.2f}s |")
    if result.command:
        lines.append(
            f"| Command | `{_escape_table_cell(' '.join(result.command))}` |",
        )
    return lines


def _artifact_lines(result: CheckResult, project_dir: Path) -> list[str]:
    """Render artifact paths for one check."""
    if not result.artifacts:
        return []
    lines = ["", "## Artifacts", ""]
    lines.extend(
        f"- `{_relative(artifact, project_dir)}`"
        for artifact in result.artifacts
    )
    return lines


def _metadata_lines(result: CheckResult) -> list[str]:
    """Render structured metadata for one check."""
    if not result.metadata:
        return []
    lines = ["", "## Details", ""]
    for key, value in result.metadata.items():
        lines += _metadata_value_lines(key, value)
    return lines


def _metadata_value_lines(key: str, value: object) -> list[str]:
    """Render one metadata value."""
    is_structured = isinstance(value, (dict, list, tuple))
    return [
        f"### {key}",
        "",
        "```json" if is_structured else "",
        _format_metadata(value),
        "```" if is_structured else "",
        "",
    ]


def _captured_output_lines(name: str, content: str) -> list[str]:
    """Render captured stdout or stderr."""
    if not content:
        return []
    return [
        f"## {name}",
        "",
        "```text",
        content.rstrip(),
        "```",
        "",
    ]


def write_check_reports(
    results: list[CheckResult],
    project_dir: Path,
    output_dir: Path,
) -> list[Path]:
    """Write one detailed Markdown report per check.

    Args:
        results: Ordered check results to render.
        project_dir: Project root directory.
        output_dir: Destination directory.

    Returns:
        Paths to generated reports.
    """
    paths: list[Path] = []
    for result in results:
        output = output_dir / f"{result.name}.md"
        write_check_report(result, project_dir, output)
        paths.append(output)
    return paths


def write_check_json_reports(
    results: list[CheckResult],
    project_dir: Path,
    output_dir: Path,
) -> dict[str, tuple[Path, str]]:
    """Write one JSON contract file per check.

    Args:
        results: Ordered check results to render.
        project_dir: Project root directory.
        output_dir: Destination directory.

    Returns:
        Mapping of check name to the JSON path and SHA-256 digest.
    """
    reports: dict[str, tuple[Path, str]] = {}
    for result in results:
        output = output_dir / f"{result.name}.json"
        digest = _write_json_payload(
            _result_payload(result, project_dir),
            output,
        )
        reports[result.name] = (output, digest)
    return reports
