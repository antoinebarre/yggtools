"""Shared pytest fixtures for the yggtools test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Return an empty temporary directory for use as a project root.

    Args:
        tmp_path: Pytest built-in temporary directory fixture.

    Returns:
        Path to an empty directory suitable for project tests.
    """
    d = tmp_path / "my-lib"
    d.mkdir()
    return d
