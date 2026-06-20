"""Ordered pipeline for the init-repo and init commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from yggtools.repo_init.steps import (
    RepoContext,
    step_add_dev_deps,
    step_git_commit,
    step_patch_pyproject,
    step_uv_init,
    step_write_ci,
    step_write_claude_md,
    step_write_makefile,
    step_write_tests_dir,
    step_write_work_dir,
)


@dataclass(frozen=True)
class PipelineStep:
    """A named step in the init pipeline.

    Attributes:
        name: Short label shown in progress output.
        fn: The step function to execute.
    """

    name: str
    fn: Callable[[RepoContext], None]


# Steps shared by both init-repo and init (everything after uv init --lib).
_COMPLETION_STEPS: list[PipelineStep] = [
    PipelineStep("add dev dependencies", step_add_dev_deps),
    PipelineStep("patch pyproject.toml", step_patch_pyproject),
    PipelineStep("write Makefile", step_write_makefile),
    PipelineStep("write CLAUDE.md", step_write_claude_md),
    PipelineStep("create tests/", step_write_tests_dir),
    PipelineStep("create work/", step_write_work_dir),
    PipelineStep("write CI workflows", step_write_ci),
    PipelineStep("git commit", step_git_commit),
]

# Full pipeline: uv init --lib first, then completion steps.
# Used by ``yggtools init-repo PROJECT_NAME``.
STEPS_FULL: list[PipelineStep] = [
    PipelineStep("uv init --lib", step_uv_init),
    *_COMPLETION_STEPS,
]

# In-place pipeline: completion steps only, applied to the current directory.
# Used by ``yggtools init`` (after the user already ran ``uv init --lib``).
STEPS_INIT: list[PipelineStep] = list(_COMPLETION_STEPS)

# Backward-compatible alias: equivalent to STEPS_FULL.
STEPS: list[PipelineStep] = STEPS_FULL


def run_pipeline(ctx: RepoContext) -> None:
    """Execute all steps in STEPS_FULL in order.

    Each step is called with ``ctx``.  Execution stops on the first
    ``StepError``, which propagates to the caller.

    Args:
        ctx: Immutable pipeline context.
    """
    for step in STEPS_FULL:
        step.fn(ctx)


def run_init_pipeline(ctx: RepoContext) -> None:
    """Execute the in-place completion steps in order.

    Runs ``STEPS_INIT`` (all steps except ``uv init --lib``).  Used by the
    ``yggtools init`` command which operates on an already-initialised
    project directory.

    Args:
        ctx: Immutable pipeline context.

    Raises:
        StepError: Propagated from any failing step.
    """
    for step in STEPS_INIT:
        step.fn(ctx)
