"""Ordered pipeline for the init-repo command."""

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
    step_write_makefile,
    step_write_tests_dir,
    step_write_work_dir,
)


@dataclass(frozen=True)
class PipelineStep:
    """A named step in the init-repo pipeline.

    Attributes:
        name: Short label shown in progress output.
        fn: The step function to execute.
    """

    name: str
    fn: Callable[[RepoContext], None]


STEPS: list[PipelineStep] = [
    PipelineStep("uv init --lib", step_uv_init),
    PipelineStep("add dev dependencies", step_add_dev_deps),
    PipelineStep("patch pyproject.toml", step_patch_pyproject),
    PipelineStep("write Makefile", step_write_makefile),
    PipelineStep("create tests/", step_write_tests_dir),
    PipelineStep("create work/", step_write_work_dir),
    PipelineStep("write CI workflows", step_write_ci),
    PipelineStep("git commit", step_git_commit),
]


def run_pipeline(ctx: RepoContext) -> None:
    """Execute all init-repo steps in order.

    Each step is called with ``ctx``.  Execution stops on the first
    ``StepError``, which propagates to the caller.

    Args:
        ctx: Immutable pipeline context.
    """
    for step in STEPS:
        step.fn(ctx)
