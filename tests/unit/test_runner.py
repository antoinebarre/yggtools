"""Unit tests for yggtools.quality.runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from yggtools.quality.runner import (
    CheckResult,
    _REGISTRY,
    register,
    registered_checks,
    run_all,
    run_one,
)


def _isolated_registry() -> dict:
    """Return a clean copy of the registry for test isolation.

    Returns:
        Snapshot of the current registry before modification.
    """
    return dict(_REGISTRY)


def test_register_adds_check_to_registry() -> None:
    """Requirement: @register must add the function to _REGISTRY under name."""
    original = dict(_REGISTRY)
    try:
        @register("_test_check")
        def _dummy(project_dir: Path) -> CheckResult:
            """Dummy check for testing.

            Args:
                project_dir: Unused.

            Returns:
                Always-passing CheckResult.
            """
            return CheckResult(name="_test_check", passed=True, detail="ok")

        assert "_test_check" in _REGISTRY
        assert _REGISTRY["_test_check"] is _dummy
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_registered_checks_returns_names_in_order() -> None:
    """Requirement: registered_checks() returns names in insertion order."""
    original = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        @register("alpha")
        def _a(project_dir: Path) -> CheckResult:
            """Alpha check stub.

            Args:
                project_dir: Unused.

            Returns:
                CheckResult stub.
            """
            return CheckResult(name="alpha", passed=True, detail="")

        @register("beta")
        def _b(project_dir: Path) -> CheckResult:
            """Beta check stub.

            Args:
                project_dir: Unused.

            Returns:
                CheckResult stub.
            """
            return CheckResult(name="beta", passed=True, detail="")

        assert registered_checks() == ["alpha", "beta"]
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_run_one_calls_registered_function(tmp_path: Path) -> None:
    """Requirement: run_one must call the registered check function."""
    original = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        @register("_ping")
        def _ping(project_dir: Path) -> CheckResult:
            """Ping check stub.

            Args:
                project_dir: Unused.

            Returns:
                CheckResult with detail 'pong'.
            """
            return CheckResult(name="_ping", passed=True, detail="pong")

        result = run_one("_ping", tmp_path)
        assert result.passed
        assert result.detail == "pong"
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)


def test_run_one_raises_on_unknown_check(tmp_path: Path) -> None:
    """Requirement: run_one must raise KeyError for unregistered check name."""
    with pytest.raises(KeyError, match="Unknown check"):
        run_one("__nonexistent__", tmp_path)


def test_run_all_returns_result_per_registered_check(tmp_path: Path) -> None:
    """Requirement: run_all must return one CheckResult per registered check."""
    original = dict(_REGISTRY)
    _REGISTRY.clear()
    try:
        for name in ("x", "y"):
            def _make(n: str):  # noqa: ANN202
                """Factory for stub check functions.

                Args:
                    n: Check name to embed in the returned function.

                Returns:
                    Check function returning a passing CheckResult.
                """
                def _check(project_dir: Path) -> CheckResult:
                    """Stub check.

                    Args:
                        project_dir: Unused.

                    Returns:
                        Passing CheckResult.
                    """
                    return CheckResult(name=n, passed=True, detail="")
                return _check
            _REGISTRY[name] = _make(name)

        results = run_all(tmp_path)
        assert len(results) == 2
        assert {r.name for r in results} == {"x", "y"}
    finally:
        _REGISTRY.clear()
        _REGISTRY.update(original)
