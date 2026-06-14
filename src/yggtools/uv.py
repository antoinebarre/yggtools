"""Adapter for uv and git subprocess calls."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEV_DEPS: list[str] = [
    "bandit>=1.8",
    "flake8>=7",
    "flake8-bugbear>=24",
    "flake8-docstrings>=1.7",
    "flake8-pyproject>=1.2",
    "mypy>=1.10",
    "pep8-naming>=0.14",
    "pip-audit>=2.8",
    "pytest>=8",
    "pytest-cov>=6",
    "ruff>=0.4",
    "yggtools",
]


class UvNotFoundError(RuntimeError):
    """Raised when the uv binary is not available in PATH."""


class CommandError(RuntimeError):
    """Raised when an external command exits with a non-zero status.

    Attributes:
        returncode: The process exit code.
        stderr: Captured standard error output.
    """

    def __init__(self, message: str, returncode: int, stderr: str) -> None:
        """Initialise a CommandError.

        Args:
            message: Human-readable description.
            returncode: Exit code from the failed process.
            stderr: Stderr text captured from the process.
        """
        super().__init__(message)
        self.returncode = returncode
        self.stderr = stderr


@dataclass(frozen=True)
class RunResult:
    """Result of a subprocess call.

    Attributes:
        returncode: Process exit code.
        stdout: Captured standard output.
        stderr: Captured standard error.
    """

    returncode: int
    stdout: str
    stderr: str


def check_uv_available() -> None:
    """Assert that uv is available in PATH.

    Raises:
        UvNotFoundError: If uv is not found.
    """
    if shutil.which("uv") is None:
        msg = (
            "uv is not installed or not in PATH. "
            "Install from https://docs.astral.sh/uv/getting-started/installation/"
        )
        raise UvNotFoundError(msg)


def run_uv(
    args: list[str],
    *,
    cwd: Path,
    capture: bool = False,
    check: bool = False,
) -> RunResult:
    """Run a uv command in the given directory.

    Args:
        args: Arguments passed to uv (e.g. ``["run", "pytest"]``).
        cwd: Working directory for the subprocess.
        capture: When True, capture stdout and stderr instead of inheriting.
        check: When True, raise CommandError on non-zero exit.

    Returns:
        RunResult with returncode, stdout, and stderr.

    Raises:
        CommandError: If ``check`` is True and the command fails.
    """
    proc = subprocess.run(  # noqa: S603
        ["uv", *args],
        cwd=cwd,
        capture_output=capture,
        text=True,
    )
    result = RunResult(
        returncode=proc.returncode,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
    )
    if check and proc.returncode != 0:
        msg = f"uv {' '.join(args)} failed (exit {proc.returncode})"
        raise CommandError(msg, proc.returncode, proc.stderr or "")
    return result


def uv_init_lib(project_dir: Path, project_name: str, python_version: str) -> None:
    """Initialise a new library project using ``uv init --lib``.

    Args:
        project_dir: Parent directory in which the project will be created.
        project_name: Name passed to ``uv init``.
        python_version: Target Python version string (e.g. ``"3.12"``).

    Raises:
        CommandError: If ``uv init`` exits with a non-zero status.
    """
    run_uv(
        ["init", "--lib", project_name, "--python", python_version],
        cwd=project_dir,
        check=True,
    )


def uv_add_dev(project_dir: Path, deps: list[str]) -> None:
    """Add development dependencies to an existing uv project.

    Args:
        project_dir: Root directory of the target project.
        deps: List of dependency specifiers (e.g. ``["pytest>=8", "ruff>=0.4"]``).

    Raises:
        CommandError: If ``uv add --dev`` exits with a non-zero status.
    """
    run_uv(["add", "--dev", *deps], cwd=project_dir, check=True)


def uv_sync(project_dir: Path) -> None:
    """Sync the project virtual environment with ``uv sync``.

    Args:
        project_dir: Root directory of the target project.

    Raises:
        CommandError: If ``uv sync`` exits with a non-zero status.
    """
    run_uv(["sync"], cwd=project_dir, check=True)


def git_commit(project_dir: Path, message: str) -> None:
    """Create a git commit in the project directory.

    Args:
        project_dir: Root directory of the git repository.
        message: Commit message.

    Raises:
        CommandError: If ``git commit`` exits with a non-zero status.
    """
    subprocess.run(  # noqa: S603
        ["git", "add", "-A"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(  # noqa: S603
        ["git", "commit", "-m", message],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )
