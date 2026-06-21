"""Quality objective rows for command-line reporting."""

from __future__ import annotations

import re

from yggtools.quality.runner import CheckResult

ObjectiveRow = tuple[str, str, str, bool]


def collect_objective_rows(
    results: dict[str, CheckResult],
) -> list[ObjectiveRow]:
    """Build rows for the objectives table from check results.

    Args:
        results: Check results keyed by name.

    Returns:
        List of (label, value, target, passed) tuples.
    """
    rows: list[ObjectiveRow] = []
    _add_lint_objectives(results, rows)
    _add_typecheck_objective(results, rows)
    _add_metrics_objectives(results, rows)
    _add_security_objectives(results, rows)
    _add_coverage_objective(results, rows)
    return rows


def _add_lint_objectives(
    results: dict[str, CheckResult],
    rows: list[ObjectiveRow],
) -> None:
    """Add lint-related objective rows.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    for name, label in [
        ("format", "Formatting"),
        ("ruff", "Ruff errors"),
        ("flake8", "Flake8 violations"),
        ("version-consistency", "Version consistency"),
    ]:
        if name in results:
            result = results[name]
            rows.append((label, result.detail, "0", result.passed))


def _add_typecheck_objective(
    results: dict[str, CheckResult],
    rows: list[ObjectiveRow],
) -> None:
    """Add the type checking objective row.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "typecheck" in results:
        result = results["typecheck"]
        count = result.metadata.get("error_count", 0)
        rows.append(("Type errors", str(count), "0", result.passed))


def _add_metrics_objectives(
    results: dict[str, CheckResult],
    rows: list[ObjectiveRow],
) -> None:
    """Add metrics objective rows for CC and module size.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "metrics" not in results:
        return
    result = results["metrics"]
    summary = result.metadata.get("summary")
    thresholds = result.metadata.get("thresholds")
    if isinstance(summary, dict) and isinstance(thresholds, dict):
        _add_cyclomatic_complexity_objective(
            summary,
            thresholds,
            result,
            rows,
        )
        violations = summary.get("violations", 0)
        rows.append(
            ("Metrics violations", str(violations), "0", violations == 0),
        )


def _add_cyclomatic_complexity_objective(
    summary: dict[object, object],
    thresholds: dict[object, object],
    result: CheckResult,
    rows: list[ObjectiveRow],
) -> None:
    """Add the cyclomatic complexity objective row.

    Args:
        summary: Metrics summary payload.
        thresholds: Metrics threshold payload.
        result: Metrics check result.
        rows: Accumulator list for objective rows.
    """
    max_cc = summary.get("max_cyclomatic_complexity", "?")
    cc_limit = thresholds.get("max_cyclomatic_complexity", "?")
    rows.append(
        (
            "Max cyclomatic complexity",
            str(max_cc),
            f"<= {cc_limit}",
            int(str(max_cc)) <= int(str(cc_limit))
            if is_int(max_cc, cc_limit)
            else result.passed,
        )
    )


def _add_security_objectives(
    results: dict[str, CheckResult],
    rows: list[ObjectiveRow],
) -> None:
    """Add security objective rows.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "security-code" in results:
        result = results["security-code"]
        rows.append(("Security issues", result.detail, "0", result.passed))
    if "security-deps" in results:
        result = results["security-deps"]
        rows.append(("Dependency vulns", result.detail, "0", result.passed))


def _add_coverage_objective(
    results: dict[str, CheckResult],
    rows: list[ObjectiveRow],
) -> None:
    """Add the test coverage objective row.

    Args:
        results: Check results keyed by name.
        rows: Accumulator list for objective rows.
    """
    if "tests" not in results:
        return
    result = results["tests"]
    cov_match = re.search(r"coverage\s+([\d.]+%)", result.detail)
    if cov_match:
        rows.append(
            ("Test coverage", cov_match.group(1), "100%", result.passed),
        )
    rows.append(("Test suite", result.detail, "all pass", result.passed))


def is_int(*values: object) -> bool:
    """Return True if all values can be converted to int.

    Args:
        *values: Values to check.

    Returns:
        True when every value is int-convertible.
    """
    try:
        for value in values:
            int(str(value))
    except (ValueError, TypeError):
        return False
    return True
