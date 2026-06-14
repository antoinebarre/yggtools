"""Tests for the embedded check_docstrings.py script."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "src"
    / "yggtools"
    / "templates"
    / "scripts"
    / "check_docstrings.py"
)


def _run_script(cwd: Path) -> subprocess.CompletedProcess[str]:
    """Execute check_docstrings.py in the given working directory.

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


def _write_py(directory: Path, filename: str, content: str) -> Path:
    """Write a Python file in a src/ subdirectory of directory.

    Args:
        directory: Project root.
        filename: Python filename.
        content: Source code content.

    Returns:
        Path to the written file.
    """
    src = directory / "src" / "pkg"
    src.mkdir(parents=True, exist_ok=True)
    path = src / filename
    path.write_text(content, encoding="utf-8")
    return path


def test_passes_when_no_python_files(tmp_path: Path) -> None:
    """Requirement: check_docstrings must pass with no Python files."""
    result = _run_script(tmp_path)
    assert result.returncode == 0


def test_passes_on_public_function_without_docstring(tmp_path: Path) -> None:
    """Requirement: check_docstrings must not flag public functions."""
    _write_py(tmp_path, "mod.py", "def public_fn(): pass\n")
    result = _run_script(tmp_path)
    assert result.returncode == 0


def test_fails_on_private_function_without_docstring(tmp_path: Path) -> None:
    """Requirement: check_docstrings must flag private functions."""
    _write_py(tmp_path, "mod.py", "def _private(): pass\n")
    result = _run_script(tmp_path)
    assert result.returncode == 1
    assert "_private" in result.stdout


def test_passes_on_private_function_with_docstring(tmp_path: Path) -> None:
    """Requirement: check_docstrings passes when private fn has docstring."""
    _write_py(
        tmp_path,
        "mod.py",
        'def _private():\n    """Do something."""\n    pass\n',
    )
    result = _run_script(tmp_path)
    assert result.returncode == 0


def test_fails_on_test_function_without_requirement(tmp_path: Path) -> None:
    """Requirement: check_docstrings must flag tests missing 'Requirement:'."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_foo.py").write_text(
        'def test_something():\n    """Does something."""\n    pass\n',
    )
    result = _run_script(tmp_path)
    assert result.returncode == 1
    assert "test_something" in result.stdout


def test_passes_on_test_function_with_requirement(tmp_path: Path) -> None:
    """Requirement: check_docstrings passes when test has 'Requirement:'."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_foo.py").write_text(
        'def test_something():\n    """Requirement: must work."""\n    pass\n',
    )
    result = _run_script(tmp_path)
    assert result.returncode == 0


def test_output_format_includes_path_and_line(tmp_path: Path) -> None:
    """Requirement: check_docstrings must output violations with path:line."""
    _write_py(tmp_path, "mod.py", "def _private(): pass\n")
    result = _run_script(tmp_path)
    assert ":" in result.stdout
    assert "_private" in result.stdout
