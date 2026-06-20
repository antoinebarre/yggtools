"""Quality check: cyclomatic complexity and module line counts."""

from __future__ import annotations

import ast
import fnmatch
import tomllib
from dataclasses import dataclass
from pathlib import Path

from yggtools.quality.runner import CheckResult, register


@dataclass(frozen=True)
class _MetricsConfig:
    """Thresholds from ``[tool.yggtools.code_metrics]`` in pyproject.toml.

    Attributes:
        paths: Directories to inspect.
        exclude: Glob patterns to skip.
        max_cyclomatic_complexity: Maximum allowed complexity per block.
        max_module_logical_lines: Maximum allowed logical lines per module.
    """

    paths: tuple[Path, ...]
    exclude: tuple[str, ...]
    max_cyclomatic_complexity: int
    max_module_logical_lines: int


@dataclass(frozen=True)
class _Violation:
    """A single metrics violation.

    Attributes:
        path: File containing the violation.
        message: Human-readable description.
    """

    path: Path
    message: str


def _read_metrics_section(pyproject: Path) -> dict[str, object]:
    """Read the ``[tool.yggtools.code_metrics]`` section from pyproject.toml.

    Args:
        pyproject: Path to the pyproject.toml file.

    Returns:
        The code_metrics dict, or an empty dict if absent or malformed.
    """
    if not pyproject.exists():
        return {}
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    raw = data.get("tool", {})
    if not isinstance(raw, dict):
        return {}
    ygg = raw.get("yggtools", {})
    if not isinstance(ygg, dict):
        return {}
    cm = ygg.get("code_metrics", {})
    return cm if isinstance(cm, dict) else {}


def _load_config(project_dir: Path) -> _MetricsConfig:
    """Load metrics configuration from pyproject.toml.

    Args:
        project_dir: Project root directory.

    Returns:
        Populated _MetricsConfig with defaults when keys are absent.
    """
    section = _read_metrics_section(project_dir / "pyproject.toml")
    raw_paths = section.get("paths", ["src", "tests"])
    raw_exclude = section.get("exclude", [])
    max_cc = section.get("max_cyclomatic_complexity", 10)
    max_ll = section.get("max_module_logical_lines", 900)
    return _MetricsConfig(
        paths=tuple(
            project_dir / p
            for p in (raw_paths if isinstance(raw_paths, list) else [])
        ),
        exclude=tuple(raw_exclude if isinstance(raw_exclude, list) else []),
        max_cyclomatic_complexity=(
            int(max_cc) if isinstance(max_cc, int) else 10
        ),
        max_module_logical_lines=(
            int(max_ll) if isinstance(max_ll, int) else 900
        ),
    )


def _is_excluded(path: Path, patterns: tuple[str, ...]) -> bool:
    """Return True if path matches any exclusion glob pattern.

    Args:
        path: File path to test.
        patterns: Glob patterns to match against the path string.

    Returns:
        True if the path should be excluded.
    """
    return any(fnmatch.fnmatch(str(path), p) for p in patterns)


def _cyclomatic_complexity(node: ast.AST) -> int:
    """Compute cyclomatic complexity of an AST node.

    Counts branch points: ``if``, ``elif``, ``for``, ``while``, ``except``,
    ``with``, ``assert``, boolean operators ``and``/``or``, and ternaries.

    Args:
        node: Root AST node of a function or method.

    Returns:
        Cyclomatic complexity value (minimum 1).
    """
    branch_types = (
        ast.If,
        ast.For,
        ast.While,
        ast.ExceptHandler,
        ast.With,
        ast.Assert,
        ast.comprehension,
    )
    count = 1
    for child in ast.walk(node):
        if isinstance(child, branch_types):
            count += 1
        elif isinstance(child, ast.BoolOp):
            count += len(child.values) - 1
        elif isinstance(child, ast.IfExp):
            count += 1
    return count


def _check_file(path: Path, cfg: _MetricsConfig) -> list[_Violation]:
    """Check a single Python file for metrics violations.

    Args:
        path: Path to the Python source file.
        cfg: Metrics configuration with thresholds.

    Returns:
        List of violations found in the file.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    violations: list[_Violation] = []

    logical_lines = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt)
        and not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        )
    )
    if logical_lines > cfg.max_module_logical_lines:
        violations.append(
            _Violation(
                path=path,
                message=(
                    f"module has {logical_lines} logical lines "
                    f"(max {cfg.max_module_logical_lines})"
                ),
            ),
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cc = _cyclomatic_complexity(node)
            if cc > cfg.max_cyclomatic_complexity:
                violations.append(
                    _Violation(
                        path=path,
                        message=(
                            f"{node.name}() CC={cc} "
                            f"(max {cfg.max_cyclomatic_complexity})"
                        ),
                    ),
                )

    return violations


@register("metrics")
def check_metrics(project_dir: Path) -> CheckResult:
    """Check cyclomatic complexity and module line counts.

    Reads thresholds from ``[tool.yggtools.code_metrics]`` in
    ``pyproject.toml``.  Defaults: CC ≤ 10, logical lines ≤ 900.

    Args:
        project_dir: Root directory of the project under audit.

    Returns:
        CheckResult listing violations or confirming all metrics pass.
    """
    cfg = _load_config(project_dir)
    violations: list[_Violation] = []

    for search_path in cfg.paths:
        if not search_path.exists():
            continue
        for py_file in sorted(search_path.rglob("*.py")):
            if _is_excluded(py_file, cfg.exclude):
                continue
            violations.extend(_check_file(py_file, cfg))

    if not violations:
        return CheckResult(
            name="metrics",
            passed=True,
            detail="All metrics pass",
        )

    first = violations[0]
    return CheckResult(
        name="metrics",
        passed=False,
        detail=(
            f"{len(violations)} violation(s) — "
            f"{first.path.name}: {first.message}"
        ),
    )
