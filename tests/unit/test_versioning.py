"""Unit tests for yggtools.versioning."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from yggtools.uv import CommandError
from yggtools.versioning import (
    VersionError,
    _is_editable_project_block,
    _line_ending,
    _package_blocks,
    _replace_init_version,
    _replace_lock_version,
    _replace_project_version,
    _replace_version_line,
    bump_semver,
    increase_project_version,
)


class TestBumpSemver:
    """Tests for bump_semver."""

    def test_level_1_increases_patch(self) -> None:
        """Requirement: level 1 increments patch."""
        assert bump_semver("1.2.3", 1) == "1.2.4"

    def test_level_2_increases_minor_and_resets_patch(self) -> None:
        """Requirement: level 2 increments minor."""
        assert bump_semver("1.2.3", 2) == "1.3.0"

    def test_level_3_increases_major_and_resets_lower_parts(self) -> None:
        """Requirement: level 3 increments major."""
        assert bump_semver("1.2.3", 3) == "2.0.0"

    def test_rejects_invalid_level(self) -> None:
        """Requirement: levels outside 1..3 are rejected."""
        with pytest.raises(VersionError):
            bump_semver("1.2.3", 4)

    def test_rejects_prerelease(self) -> None:
        """Requirement: only stable SemVer is accepted."""
        with pytest.raises(VersionError):
            bump_semver("1.2.3-rc.1", 1)

    def test_rejects_leading_zeroes(self) -> None:
        """Requirement: SemVer numeric identifiers cannot have zero padding."""
        with pytest.raises(VersionError):
            bump_semver("01.2.3", 1)


class TestReplaceProjectVersion:
    """Tests for pyproject.toml version replacement."""

    def test_replaces_project_version_only(self) -> None:
        """Requirement: only [project].version is updated."""
        content = (
            '[build-system]\nversion = "old"\n\n'
            '[project]\nname = "my-lib"\nversion = "1.2.3"\n\n'
            '[tool.demo]\nversion = "old"\n'
        )
        updated = _replace_project_version(content, "1.2.4")
        assert 'version = "1.2.4"' in updated
        assert updated.count('version = "old"') == 2

    def test_preserves_project_version_quote_and_comment(self) -> None:
        """Requirement: quote style and trailing comments are preserved."""
        content = "[project]\nversion = '1.2.3'  # release\n"
        assert _replace_project_version(content, "1.2.4") == (
            "[project]\nversion = '1.2.4'  # release\n"
        )

    def test_fails_when_project_version_missing(self) -> None:
        """Requirement: missing [project].version fails."""
        with pytest.raises(VersionError):
            _replace_project_version('[project]\nname = "my-lib"\n', "1.2.4")

    def test_fails_when_project_section_ends_before_version(self) -> None:
        """Requirement: search stops at the next TOML section."""
        content = (
            '[project]\nname = "my-lib"\n[tool.demo]\nversion = "1.2.3"\n'
        )
        with pytest.raises(VersionError):
            _replace_project_version(content, "1.2.4")


class TestReplaceInitVersion:
    """Tests for package __version__ replacement."""

    def test_replaces_init_version(self) -> None:
        """Requirement: __version__ assignment is updated."""
        assert _replace_init_version('__version__ = "1.2.3"\n', "1.2.4") == (
            '__version__ = "1.2.4"\n'
        )

    def test_preserves_comment(self) -> None:
        """Requirement: trailing comment is preserved."""
        assert _replace_init_version(
            "__version__ = '1.2.3'  # x\n", "1.2.4"
        ) == ("__version__ = '1.2.4'  # x\n")

    def test_fails_when_init_version_missing(self) -> None:
        """Requirement: missing __version__ fails."""
        with pytest.raises(VersionError):
            _replace_init_version('NAME = "my-lib"\n', "1.2.4")


class TestReplaceLockVersion:
    """Tests for uv.lock version replacement."""

    def test_replaces_editable_project_version(self) -> None:
        """Requirement: editable local package version is updated."""
        content = (
            '[[package]]\nname = "other"\nversion = "9.9.9"\n\n'
            '[[package]]\nname = "my-lib"\nversion = "1.2.3"\n'
            'source = { editable = "." }\n'
        )
        updated = _replace_lock_version(content, "my-lib", "1.2.4")
        assert 'name = "my-lib"\nversion = "1.2.4"' in updated
        assert 'name = "other"\nversion = "9.9.9"' in updated

    def test_fails_when_editable_project_missing(self) -> None:
        """Requirement: missing editable package block fails."""
        content = '[[package]]\nname = "my-lib"\nversion = "1.2.3"\n'
        with pytest.raises(VersionError):
            _replace_lock_version(content, "my-lib", "1.2.4")

    def test_package_blocks_returns_ranges(self) -> None:
        """Requirement: uv.lock package blocks are detected."""
        lines = ["version = 1\n", "[[package]]\n", 'name = "a"\n']
        assert _package_blocks(lines) == [(1, 3)]

    def test_editable_project_block_requires_name_and_source(self) -> None:
        """Requirement: block must match name and editable source."""
        block = [
            "[[package]]\n",
            'name = "my-lib"\n',
            'source = { editable = "." }\n',
        ]
        assert _is_editable_project_block(block, "my-lib")
        assert not _is_editable_project_block(block, "other")

    def test_replace_version_line_ignores_other_lines(self) -> None:
        """Requirement: only version assignments are replaceable."""
        assert _replace_version_line('name = "my-lib"', "1.2.4") is None

    def test_line_ending_detects_variants(self) -> None:
        """Requirement: original line endings are preserved."""
        assert _line_ending("x\r\n") == "\r\n"
        assert _line_ending("x\n") == "\n"
        assert _line_ending("x") == ""


class TestIncreaseProjectVersion:
    """Tests for increase_project_version."""

    def test_updates_all_artifacts_and_runs_uv_lock(
        self, tmp_path: Path
    ) -> None:
        """Requirement: version bump updates all managed artifacts."""
        _write_project(tmp_path, version="1.2.3")
        with patch("yggtools.versioning.run_uv") as run_uv:
            update = increase_project_version(tmp_path, 2)
        assert update.old_version == "1.2.3"
        assert update.new_version == "1.3.0"
        assert 'version = "1.3.0"' in (tmp_path / "pyproject.toml").read_text()
        assert (
            '__version__ = "1.3.0"'
            in (tmp_path / "src" / "my_lib" / "__init__.py").read_text()
        )
        assert 'version = "1.3.0"' in (tmp_path / "uv.lock").read_text()
        run_uv.assert_called_once_with(["lock"], cwd=tmp_path, check=True)

    def test_can_skip_uv_lock(self, tmp_path: Path) -> None:
        """Requirement: uv lock can be skipped for isolated tests/demos."""
        _write_project(tmp_path, version="1.2.3")
        with patch("yggtools.versioning.run_uv") as run_uv:
            increase_project_version(tmp_path, 1, update_lock=False)
        run_uv.assert_not_called()

    def test_fails_without_project_identity(self, tmp_path: Path) -> None:
        """Requirement: project name and version are required."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n", encoding="utf-8"
        )
        with pytest.raises(VersionError):
            increase_project_version(tmp_path, 1, update_lock=False)

    def test_fails_when_required_artifact_missing(
        self, tmp_path: Path
    ) -> None:
        """Requirement: all managed artifacts must exist."""
        _write_project(tmp_path, version="1.2.3")
        (tmp_path / "uv.lock").unlink()
        with pytest.raises(VersionError):
            increase_project_version(tmp_path, 1, update_lock=False)

    def test_wraps_uv_lock_failure(self, tmp_path: Path) -> None:
        """Requirement: uv lock failures are reported as version errors."""
        _write_project(tmp_path, version="1.2.3")
        with (
            patch(
                "yggtools.versioning.run_uv",
                side_effect=CommandError("bad", 1, "err"),
            ),
            pytest.raises(VersionError),
        ):
            increase_project_version(tmp_path, 1)


def _write_project(tmp_path: Path, *, version: str) -> None:
    """Write a minimal versioned project.

    Args:
        tmp_path: Project root.
        version: Version value to write.
    """
    (tmp_path / "src" / "my_lib").mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "my-lib"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "my_lib" / "__init__.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        f'[[package]]\nname = "my-lib"\nversion = "{version}"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )
