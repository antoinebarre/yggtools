"""Subprocess wrappers for uv and git commands."""

from __future__ import annotations

import shutil
import subprocess  # nosec B404
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
    "twine>=6",
]


class UvNotFoundError(RuntimeError):
    """Raised when the uv binary is not available in PATH."""


class CommandError(RuntimeError):
    """Raised when an external command exits with a non-zero code.

    Attributes:
        returncode: The process exit code.
        stderr: Captured standard error output.
    """

    def __init__(self, message: str, returncode: int, stderr: str) -> None:
        """Initialise a CommandError.

        Args:
            message: Human-readable error description.
            returncode: Exit code from the failed process.
            stderr: Captured stderr text.
        """
        super().__init__(message, returncode, stderr)
        self.returncode = returncode
        self.stderr = stderr


def check_uv_available() -> None:
    """Verify that the uv binary is accessible in the current PATH.

    Raises:
        UvNotFoundError: If uv cannot be found.
    """
    if shutil.which("uv") is None:
        msg = (
            "uv not found in PATH. "
            "Install it from "
            "https://docs.astral.sh/uv/getting-started/installation/"
        )
        raise UvNotFoundError(msg)


def uv_add_dev_deps(project_dir: Path, deps: list[str]) -> None:
    """Add packages to the dev dependency group via uv.

    Args:
        project_dir: Root directory of the target project.
        deps: List of dependency specifiers, e.g. ``["ruff>=0.4"]``.

    Raises:
        CommandError: If uv exits with a non-zero code.
    """
    run_command(["uv", "add", "--group", "dev", *deps], cwd=project_dir)


def uv_sync(project_dir: Path) -> None:
    """Synchronise the project virtual environment via uv sync.

    Args:
        project_dir: Root directory of the target project.

    Raises:
        CommandError: If uv exits with a non-zero code.
    """
    run_command(["uv", "sync"], cwd=project_dir)


def git_init(project_dir: Path) -> None:
    """Initialise a git repository in the project directory.

    Args:
        project_dir: Directory to initialise.

    Raises:
        CommandError: If git exits with a non-zero code.
    """
    run_command(["git", "init"], cwd=project_dir)


def git_add_all(project_dir: Path) -> None:
    """Stage all files in the project directory.

    Args:
        project_dir: Project root directory.

    Raises:
        CommandError: If git exits with a non-zero code.
    """
    run_command(["git", "add", "-A"], cwd=project_dir)


def git_commit(project_dir: Path, message: str) -> None:
    """Create a git commit with the given message.

    Args:
        project_dir: Project root directory.
        message: Commit message.

    Raises:
        CommandError: If git exits with a non-zero code.
    """
    run_command(["git", "commit", "-m", message], cwd=project_dir)


def run_command(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Execute an external command and return its result.

    Args:
        cmd: Command and arguments list.
        cwd: Working directory for the command.

    Returns:
        Completed process result with stdout and stderr captured.

    Raises:
        CommandError: If the process exits with a non-zero return code.
    """
    result = subprocess.run(  # noqa: S603  # nosec B603
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"Command failed: {' '.join(cmd)}"
        raise CommandError(msg, result.returncode, result.stderr)
    return result
