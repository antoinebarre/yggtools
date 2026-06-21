"""Unit tests for yggtools.repo_init.pipeline."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from yggtools.repo_init.pipeline import (
    STEPS,
    STEPS_FULL,
    STEPS_INIT,
    run_init_pipeline,
    run_pipeline,
)
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


def test_steps_full_starts_with_uv_init() -> None:
    """Requirement: STEPS_FULL first step must be uv init --lib."""
    assert STEPS_FULL[0].name == "uv init --lib"


def test_steps_init_does_not_contain_uv_init() -> None:
    """Requirement: STEPS_INIT must not include the uv init --lib step."""
    names = [s.name for s in STEPS_INIT]
    assert "uv init --lib" not in names


def test_steps_init_is_steps_full_minus_uv_init() -> None:
    """Requirement: STEPS_INIT must equal STEPS_FULL without the first step."""
    assert STEPS_FULL[1:] == STEPS_INIT


def test_steps_is_alias_for_steps_full() -> None:
    """Requirement: STEPS must be the same list as STEPS_FULL."""
    assert STEPS is STEPS_FULL


def test_run_pipeline_calls_all_steps_in_order(tmp_path: Path) -> None:
    """Requirement: run_pipeline must call every step in order."""
    ctx = _ctx(tmp_path)
    call_order: list[str] = []

    def _make_spy(name: str) -> Callable[[object], None]:
        """Return a spy function that records the step name when called.

        Args:
            name: Step name to record.

        Returns:
            Callable that appends name to call_order.
        """

        def _spy(_ctx: object) -> None:
            """Record invocation of this step.

            Args:
                _ctx: Ignored pipeline context.
            """
            call_order.append(name)

        return _spy

    spied = [
        type(step)(name=step.name, fn=_make_spy(step.name))
        for step in STEPS_FULL
    ]
    with patch("yggtools.repo_init.pipeline.STEPS_FULL", spied):
        run_pipeline(ctx)

    assert call_order == [s.name for s in STEPS_FULL]


def test_run_init_pipeline_calls_completion_steps_in_order(
    tmp_path: Path,
) -> None:
    """Requirement: run_init_pipeline must call every STEPS_INIT step."""
    ctx = _ctx(tmp_path)
    call_order: list[str] = []

    def _make_spy(name: str) -> Callable[[object], None]:
        """Return a spy function that records the step name when called.

        Args:
            name: Step name to record.

        Returns:
            Callable that appends name to call_order.
        """

        def _spy(_ctx: object) -> None:
            """Record invocation of this step.

            Args:
                _ctx: Ignored pipeline context.
            """
            call_order.append(name)

        return _spy

    spied = [
        type(step)(name=step.name, fn=_make_spy(step.name))
        for step in STEPS_INIT
    ]
    with patch("yggtools.repo_init.pipeline.STEPS_INIT", spied):
        run_init_pipeline(ctx)

    assert call_order == [s.name for s in STEPS_INIT]
