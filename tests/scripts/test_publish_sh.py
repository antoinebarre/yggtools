"""Tests for the embedded publish.sh script."""

from __future__ import annotations

import subprocess
from pathlib import Path

_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "src"
    / "uvforge"
    / "templates"
    / "scripts"
    / "publish.sh"
)


def _run_script(cwd: Path, action: str) -> subprocess.CompletedProcess[str]:
    """Execute publish.sh with the given action in the specified directory.

    Args:
        cwd: Working directory for the script execution.
        action: Publish action parameter
            (build, check-dist, publish-test, publish).

    Returns:
        Completed process with stdout/stderr captured.
    """
    return subprocess.run(
        ["bash", str(_SCRIPT), action],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _make_buildable_project(tmp_path: Path) -> Path:
    """Create a minimal Python project that uv can build.

    Args:
        tmp_path: Temporary directory.

    Returns:
        Path to the project directory.
    """
    project = tmp_path / "testpkg"
    project.mkdir()
    (project / "work").mkdir()
    (project / "work" / ".gitkeep").touch()
    src = project / "src" / "testpkg"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""testpkg."""\n')
    (src / "py.typed").touch()
    pyproject_lines = [
        "[build-system]",
        'requires = ["hatchling"]',
        'build-backend = "hatchling.build"',
        "",
        "[project]",
        'name = "testpkg"',
        'version = "0.1.0"',
        'requires-python = ">=3.12"',
        "",
        "[tool.hatch.build.targets.wheel]",
        'packages = ["src/testpkg"]',
        "",
    ]
    (project / "pyproject.toml").write_text(
        "\n".join(pyproject_lines),
    )
    return project


def test_publish_sh_fails_without_action(tmp_path: Path) -> None:
    """Requirement: publish.sh must exit non-zero when no action is given."""
    result = subprocess.run(
        ["bash", str(_SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0


def test_publish_sh_fails_on_unknown_action(tmp_path: Path) -> None:
    """Requirement: publish.sh must exit 2 for an unknown action."""
    project = _make_buildable_project(tmp_path)
    result = _run_script(project, "badaction")
    assert result.returncode == 2
    assert "Unknown publish action" in result.stderr


def test_publish_sh_build_creates_dist_then_cleans(tmp_path: Path) -> None:
    """Requirement: publish.sh build must clean work/dist/ on exit."""
    project = _make_buildable_project(tmp_path)
    result = _run_script(project, "build")
    dist = project / "work" / "dist"
    assert result.returncode == 0
    assert not dist.exists() or list(dist.iterdir()) == []


def test_publish_sh_check_dist_exits_zero(tmp_path: Path) -> None:
    """Requirement: publish.sh check-dist must exit 0 on a valid package."""
    project = _make_buildable_project(tmp_path)
    result = _run_script(project, "check-dist")
    assert result.returncode == 0


def test_publish_sh_work_gitkeep_preserved(tmp_path: Path) -> None:
    """Requirement: publish.sh must preserve work/.gitkeep after cleanup."""
    project = _make_buildable_project(tmp_path)
    _run_script(project, "build")
    assert (project / "work" / ".gitkeep").exists()
