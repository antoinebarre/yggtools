"""Unit tests for yggtools.repo_init.pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call, patch

from yggtools.repo_init.pipeline import STEPS, run_pipeline
from yggtools.repo_init.steps import RepoContext


def _ctx(tmp_path: Path) -> RepoContext:
    """Build a minimal RepoContext for pipeline tests.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        Configured RepoContext.
    """
    return RepoContext(
        project_name="my-lib",
        python_version="3.12",
        parent_dir=tmp_path,
    )


def test_steps_list_is_non_empty() -> None:
    """Requirement: STEPS must contain at least one PipelineStep."""
    assert len(STEPS) > 0


def test_steps_have_unique_names() -> None:
    """Requirement: each PipelineStep name must be unique."""
    names = [s.name for s in STEPS]
    assert len(names) == len(set(names))


def test_run_pipeline_calls_all_steps_in_order(tmp_path: Path) -> None:
    """Requirement: run_pipeline must call every step function in STEPS order."""
    ctx = _ctx(tmp_path)
    call_order: list[str] = []

    patched = []
    for step in STEPS:
        mock = MagicMock(side_effect=lambda c, n=step.name: call_order.append(n))
        patched.append(
            patch.object(step, "fn", mock)
        )

    for p in patched:
        p.start()
    try:
        run_pipeline(ctx)
    finally:
        for p in patched:
            p.stop()

    assert call_order == [s.name for s in STEPS]
