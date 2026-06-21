"""Unit tests for yggtools.repo_init.steps."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from yggtools.repo_init.steps import (
    RepoContext,
    StepError,
    _collect_pyproject_additions,
    _package_name,
    step_add_dev_deps,
    step_ensure_package_layout,
    step_git_commit,
    step_patch_pyproject,
    step_uv_init,
    step_write_ci,
    step_write_claude_md,
    step_write_makefile,
    step_write_tests_dir,
    step_write_work_dir,
)
from yggtools.uv import CommandError


def _ctx(
    tmp_path: Path,
    *,
    no_git: bool = False,
    dry_run: bool = False,
) -> RepoContext:
    """Build a minimal RepoContext for step tests.

    Args:
        tmp_path: Pytest temporary directory used as parent_dir.
        no_git: Skip git and CI steps.
        dry_run: Enable dry-run mode.

    Returns:
        Configured RepoContext.
    """
    return RepoContext(
        project_name="my-lib",
        python_version="3.12",
        parent_dir=tmp_path,
        no_git=no_git,
        dry_run=dry_run,
    )


class TestRepoContext:
    """Tests for RepoContext properties."""

    def test_project_dir_is_parent_plus_name(self, tmp_path: Path) -> None:
        """Requirement: project_dir must equal parent_dir / project_name."""
        ctx = _ctx(tmp_path)
        assert ctx.project_dir == tmp_path / "my-lib"


class TestStepUvInit:
    """Tests for step_uv_init."""

    def test_calls_uv_init_lib_with_context_values(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: step_uv_init must call uv_init_lib correctly."""
        ctx = _ctx(tmp_path)
        with patch("yggtools.repo_init.steps.uv_init_lib") as mock:
            step_uv_init(ctx)
        mock.assert_called_once_with(tmp_path, "my-lib", "3.12")

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_uv_init must skip execution in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        with patch("yggtools.repo_init.steps.uv_init_lib") as mock:
            step_uv_init(ctx)
        mock.assert_not_called()

    def test_raises_step_error_on_command_failure(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: step_uv_init must raise StepError when uv fails."""
        ctx = _ctx(tmp_path)
        with (
            patch(
                "yggtools.repo_init.steps.uv_init_lib",
                side_effect=CommandError("fail", 1, ""),
            ),
            pytest.raises(StepError),
        ):
            step_uv_init(ctx)


class TestStepAddDevDeps:
    """Tests for step_add_dev_deps."""

    def test_calls_uv_add_dev(self, tmp_path: Path) -> None:
        """Requirement: step_add_dev_deps must call uv_add_dev."""
        ctx = _ctx(tmp_path)
        with patch("yggtools.repo_init.steps.uv_add_dev") as mock:
            step_add_dev_deps(ctx)
        mock.assert_called_once()

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_add_dev_deps must skip in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        with patch("yggtools.repo_init.steps.uv_add_dev") as mock:
            step_add_dev_deps(ctx)
        mock.assert_not_called()

    def test_raises_step_error_on_failure(self, tmp_path: Path) -> None:
        """Requirement: step_add_dev_deps must raise StepError on failure."""
        ctx = _ctx(tmp_path)
        with (
            patch(
                "yggtools.repo_init.steps.uv_add_dev",
                side_effect=CommandError("fail", 1, ""),
            ),
            pytest.raises(StepError),
        ):
            step_add_dev_deps(ctx)


class TestStepEnsurePackageLayout:
    """Tests for step_ensure_package_layout."""

    def _minimal_pyproject(
        self,
        project_dir: Path,
        *,
        name: str = "my-lib",
        version: str = "0.1.0",
    ) -> None:
        """Write a minimal pyproject.toml.

        Args:
            project_dir: Project directory.
            name: Project distribution name.
            version: Project version.
        """
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "{version}"\n',
            encoding="utf-8",
        )

    def test_creates_src_package_when_missing(self, tmp_path: Path) -> None:
        """Requirement: missing src package layout must be created."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir)
        step_ensure_package_layout(ctx)
        init_file = ctx.project_dir / "src" / "my_lib" / "__init__.py"
        assert init_file.exists()
        assert '__version__ = "0.1.0"' in init_file.read_text()

    def test_appends_version_to_existing_init(self, tmp_path: Path) -> None:
        """Requirement: existing package initializer gets __version__."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir)
        package_dir = ctx.project_dir / "src" / "my_lib"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text(
            '"""Existing package."""\n',
            encoding="utf-8",
        )
        step_ensure_package_layout(ctx)
        content = (package_dir / "__init__.py").read_text()
        assert '"""Existing package."""' in content
        assert '__version__ = "0.1.0"' in content

    def test_preserves_existing_version(self, tmp_path: Path) -> None:
        """Requirement: existing __version__ must not be overwritten."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir, version="0.2.0")
        package_dir = ctx.project_dir / "src" / "my_lib"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text(
            '__version__ = "0.1.0"\n',
            encoding="utf-8",
        )
        step_ensure_package_layout(ctx)
        assert (package_dir / "__init__.py").read_text() == (
            '__version__ = "0.1.0"\n'
        )

    def test_uses_project_name_from_pyproject(self, tmp_path: Path) -> None:
        """Requirement: package dir follows [project].name."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir, name="other-lib")
        step_ensure_package_layout(ctx)
        assert (ctx.project_dir / "src" / "other_lib").exists()

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: layout repair must skip in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        self._minimal_pyproject(ctx.project_dir)
        step_ensure_package_layout(ctx)
        assert not (ctx.project_dir / "src").exists()

    def test_fails_without_project_table(self, tmp_path: Path) -> None:
        """Requirement: malformed pyproject fails clearly."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        (ctx.project_dir / "pyproject.toml").write_text(
            'project = "bad"\n',
            encoding="utf-8",
        )
        with pytest.raises(StepError):
            step_ensure_package_layout(ctx)

    def test_fails_without_project_name_or_version(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: name and version are required."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        (ctx.project_dir / "pyproject.toml").write_text(
            "[project]\n",
            encoding="utf-8",
        )
        with pytest.raises(StepError):
            step_ensure_package_layout(ctx)

    def test_package_name_normalizes_hyphen(self) -> None:
        """Requirement: package name maps hyphen to underscore."""
        assert _package_name("my-lib") == "my_lib"


class TestCollectPyprojectAdditions:
    """Tests for _collect_pyproject_additions."""

    def test_includes_code_metrics_when_yggtools_not_a_dict(self) -> None:
        """Requirement: code_metrics section added when yggtools is int."""
        existing: dict[str, object] = {"tool": {"yggtools": 42}}
        additions = _collect_pyproject_additions(existing, "my_lib")
        combined = "\n".join(additions)
        assert "[tool.yggtools.code_metrics]" in combined


class TestStepPatchPyproject:
    """Tests for step_patch_pyproject."""

    def _minimal_pyproject(self, project_dir: Path) -> None:
        """Write a minimal pyproject.toml for patching tests.

        Args:
            project_dir: Directory to write into.
        """
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "my-lib"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )

    def test_appends_ruff_section(self, tmp_path: Path) -> None:
        """Requirement: step_patch_pyproject must add [tool.ruff] section."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir)
        step_patch_pyproject(ctx)
        content = (ctx.project_dir / "pyproject.toml").read_text()
        assert "[tool.ruff]" in content

    def test_appends_mypy_section(self, tmp_path: Path) -> None:
        """Requirement: step_patch_pyproject must add [tool.mypy] section."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir)
        step_patch_pyproject(ctx)
        content = (ctx.project_dir / "pyproject.toml").read_text()
        assert "[tool.mypy]" in content

    def test_appends_yggtools_metrics_section(self, tmp_path: Path) -> None:
        """Requirement: step_patch_pyproject must add yggtools section."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir)
        step_patch_pyproject(ctx)
        content = (ctx.project_dir / "pyproject.toml").read_text()
        assert "[tool.yggtools.code_metrics]" in content

    def test_uses_project_name_from_pyproject(self, tmp_path: Path) -> None:
        """Requirement: patching must use [project].name for src paths."""
        ctx = _ctx(tmp_path)
        self._minimal_pyproject(ctx.project_dir)
        pyproject = ctx.project_dir / "pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "other-lib"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        step_patch_pyproject(ctx)
        content = pyproject.read_text()
        assert 'source = ["src/other_lib"]' in content
        assert 'paths = ["src/other_lib", "tests"]' in content

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_patch_pyproject must not write in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        ctx.project_dir.mkdir(parents=True)
        step_patch_pyproject(ctx)
        assert not (ctx.project_dir / "pyproject.toml").exists()


class TestStepWriteMakefile:
    """Tests for step_write_makefile."""

    def test_writes_makefile(self, tmp_path: Path) -> None:
        """Requirement: step_write_makefile must create a Makefile."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_makefile(ctx)
        assert (ctx.project_dir / "Makefile").exists()

    def test_makefile_references_yggtools_module(self, tmp_path: Path) -> None:
        """Requirement: Makefile must invoke yggtools as a module."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_makefile(ctx)
        content = (ctx.project_dir / "Makefile").read_text()
        assert "python -m yggtools.cli" in content

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_write_makefile must not write in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        ctx.project_dir.mkdir(parents=True)
        step_write_makefile(ctx)
        assert not (ctx.project_dir / "Makefile").exists()


class TestStepWriteTestsDir:
    """Tests for step_write_tests_dir."""

    def test_creates_tests_init_and_conftest(self, tmp_path: Path) -> None:
        """Requirement: step_write_tests_dir must create tests/__init__.py."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_tests_dir(ctx)
        assert (ctx.project_dir / "tests" / "__init__.py").exists()
        assert (ctx.project_dir / "tests" / "conftest.py").exists()

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_write_tests_dir must not write in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        ctx.project_dir.mkdir(parents=True)
        step_write_tests_dir(ctx)
        assert not (ctx.project_dir / "tests").exists()


class TestStepWriteWorkDir:
    """Tests for step_write_work_dir."""

    def test_creates_work_gitkeep(self, tmp_path: Path) -> None:
        """Requirement: step_write_work_dir must create work/.gitkeep."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_work_dir(ctx)
        assert (ctx.project_dir / "work" / ".gitkeep").exists()

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_write_work_dir must not write in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        ctx.project_dir.mkdir(parents=True)
        step_write_work_dir(ctx)
        assert not (ctx.project_dir / "work").exists()


class TestStepWriteCi:
    """Tests for step_write_ci."""

    def test_writes_github_and_gitlab_workflows(self, tmp_path: Path) -> None:
        """Requirement: step_write_ci must create both CI workflow files."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_ci(ctx)
        assert (ctx.project_dir / ".github" / "workflows" / "ci.yml").exists()
        assert (ctx.project_dir / ".gitlab-ci.yml").exists()

    def test_skips_when_no_git(self, tmp_path: Path) -> None:
        """Requirement: step_write_ci must skip when no_git=True."""
        ctx = _ctx(tmp_path, no_git=True)
        ctx.project_dir.mkdir(parents=True)
        step_write_ci(ctx)
        assert not (ctx.project_dir / ".github").exists()
        assert not (ctx.project_dir / ".gitlab-ci.yml").exists()

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_write_ci must not write in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        ctx.project_dir.mkdir(parents=True)
        step_write_ci(ctx)
        assert not (ctx.project_dir / ".github").exists()

    def test_github_workflow_contains_python_version(
        self,
        tmp_path: Path,
    ) -> None:
        """Requirement: GitHub CI must include the Python version."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_ci(ctx)
        content = (
            ctx.project_dir / ".github" / "workflows" / "ci.yml"
        ).read_text()
        assert "3.12" in content


class TestStepWriteClaudeMd:
    """Tests for step_write_claude_md."""

    def test_writes_claude_md(self, tmp_path: Path) -> None:
        """Requirement: step_write_claude_md must create CLAUDE.md."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_claude_md(ctx)
        assert (ctx.project_dir / "CLAUDE.md").exists()

    def test_claude_md_contains_package_name(self, tmp_path: Path) -> None:
        """Requirement: CLAUDE.md must reference the package source path."""
        ctx = _ctx(tmp_path)
        ctx.project_dir.mkdir(parents=True)
        step_write_claude_md(ctx)
        content = (ctx.project_dir / "CLAUDE.md").read_text()
        assert "my_lib" in content

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_write_claude_md must not write in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        ctx.project_dir.mkdir(parents=True)
        step_write_claude_md(ctx)
        assert not (ctx.project_dir / "CLAUDE.md").exists()


class TestStepGitCommit:
    """Tests for step_git_commit."""

    def test_calls_git_commit(self, tmp_path: Path) -> None:
        """Requirement: step_git_commit must call git_commit with message."""
        ctx = _ctx(tmp_path)
        with patch("yggtools.repo_init.steps.git_commit") as mock:
            step_git_commit(ctx)
        mock.assert_called_once_with(
            ctx.project_dir,
            "chore: yggtools init-repo",
        )

    def test_skips_when_no_git(self, tmp_path: Path) -> None:
        """Requirement: step_git_commit must skip when no_git=True."""
        ctx = _ctx(tmp_path, no_git=True)
        with patch("yggtools.repo_init.steps.git_commit") as mock:
            step_git_commit(ctx)
        mock.assert_not_called()

    def test_skips_in_dry_run(self, tmp_path: Path) -> None:
        """Requirement: step_git_commit must skip in dry-run mode."""
        ctx = _ctx(tmp_path, dry_run=True)
        with patch("yggtools.repo_init.steps.git_commit") as mock:
            step_git_commit(ctx)
        mock.assert_not_called()
