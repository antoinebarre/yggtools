"""Tests for the embedded code_metrics.py script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "src"
    / "uvforge"
    / "templates"
    / "scripts"
    / "code_metrics.py"
)

_PYPROJECT_TEMPLATE = """\
[tool.uvforge.code_metrics]
paths = ["{path}"]
exclude = []
max_cyclomatic_complexity = {max_cc}
max_module_logical_lines = {max_lines}
"""


def _run_script(cwd: Path) -> subprocess.CompletedProcess[str]:
    """Execute code_metrics.py in the given working directory.

    Args:
        cwd: Working directory for the script execution.

    Returns:
        Completed process with stdout/stderr captured.
    """
    return subprocess.run(
        [sys.executable, str(_SCRIPT)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _setup_project(
    tmp_path: Path,
    src_code: str,
    max_cc: int = 10,
    max_lines: int = 900,
) -> None:
    """Create a minimal project with one source file and a pyproject.toml.

    Args:
        tmp_path: Temporary directory.
        src_code: Python source code to put in the analysed file.
        max_cc: Maximum cyclomatic complexity threshold.
        max_lines: Maximum logical lines threshold.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "module.py").write_text(src_code, encoding="utf-8")
    pyproject = _PYPROJECT_TEMPLATE.format(
        path="src",
        max_cc=max_cc,
        max_lines=max_lines,
    )
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")


def test_passes_on_simple_function(tmp_path: Path) -> None:
    """Requirement: code_metrics must pass for complexity-1 functions."""
    _setup_project(
        tmp_path,
        'def simple():\n    """Do nothing."""\n    pass\n',
    )
    result = _run_script(tmp_path)
    assert result.returncode == 0


def test_fails_when_complexity_exceeds_threshold(tmp_path: Path) -> None:
    """Requirement: code_metrics must fail when complexity exceeds max."""
    branches = "\n".join(f"    if x == {i}:\n        pass" for i in range(5))
    code = f'def complex_fn(x):\n    """Many branches."""\n{branches}\n'
    _setup_project(tmp_path, code, max_cc=2)
    result = _run_script(tmp_path)
    assert result.returncode == 1
    assert "FAILED" in result.stdout


def test_passes_when_complexity_at_threshold(tmp_path: Path) -> None:
    """Requirement: code_metrics must pass when complexity equals threshold."""
    code = 'def fn():\n    """No branches."""\n    return 1\n'
    _setup_project(tmp_path, code, max_cc=1)
    result = _run_script(tmp_path)
    assert result.returncode == 0


def test_fails_when_logical_lines_exceed_threshold(tmp_path: Path) -> None:
    """Requirement: code_metrics must fail when logical lines exceed max."""
    lines = "\n".join(f"x_{i} = {i}" for i in range(20))
    _setup_project(tmp_path, lines + "\n", max_lines=5)
    result = _run_script(tmp_path)
    assert result.returncode == 1


def test_output_contains_metric_table(tmp_path: Path) -> None:
    """Requirement: code_metrics output must include a metric results table."""
    _setup_project(tmp_path, 'def fn():\n    """Simple."""\n    pass\n')
    result = _run_script(tmp_path)
    assert "Metric" in result.stdout
    assert "Expected" in result.stdout


def test_status_line_reports_passed_on_success(tmp_path: Path) -> None:
    """Requirement: code_metrics must print 'passed' on success."""
    _setup_project(tmp_path, 'def fn():\n    """Simple."""\n    pass\n')
    result = _run_script(tmp_path)
    assert "passed" in result.stdout
