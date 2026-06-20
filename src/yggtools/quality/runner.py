"""Quality check registry and pipeline runner."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CheckResult:
    """Result of a single quality check.

    Attributes:
        name: Short identifier for the check (e.g. ``"format"``).
        passed: True when the check found no issues.
        detail: Human-readable summary line (counts, first error, etc.).
    """

    name: str
    passed: bool
    detail: str


class CheckFn(Protocol):
    """Protocol for a quality check function.

    A check function receives the project root directory and returns a
    ``CheckResult``.  It must not raise — failures must be captured in the
    result.
    """

    def __call__(self, project_dir: Path) -> CheckResult:
        """Run the check and return its result.

        Args:
            project_dir: Root directory of the project under audit.

        Returns:
            CheckResult describing pass/fail and a detail summary.
        """
        ...  # pragma: no cover


_REGISTRY: dict[str, CheckFn] = {}


def register(name: str) -> Callable[[CheckFn], CheckFn]:
    """Decorator that registers a function as a named quality check.

    Args:
        name: Unique identifier for the check.

    Returns:
        Decorator that registers and returns the decorated function unchanged.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        """Register fn under name and return it unchanged.

        Args:
            fn: Check function to register.

        Returns:
            The original function, unmodified.
        """
        _REGISTRY[name] = fn
        return fn

    return decorator


def registered_checks() -> list[str]:
    """Return the names of all registered checks in registration order.

    Returns:
        List of check names.
    """
    return list(_REGISTRY)


def run_one(name: str, project_dir: Path) -> CheckResult:
    """Run a single registered check by name.

    Args:
        name: Registered check name.
        project_dir: Project root directory.

    Returns:
        CheckResult from the check function.

    Raises:
        KeyError: If no check is registered under ``name``.
    """
    if name not in _REGISTRY:
        msg = f"Unknown check: {name!r}. Available: {list(_REGISTRY)}"
        raise KeyError(msg)
    return _REGISTRY[name](project_dir)


def run_all(project_dir: Path) -> list[CheckResult]:
    """Run all registered checks in registration order.

    Args:
        project_dir: Project root directory.

    Returns:
        List of CheckResult, one per registered check.
    """
    return [fn(project_dir) for fn in _REGISTRY.values()]
