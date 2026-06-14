"""Check project docstring requirements."""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

SOURCE_ROOTS = (Path("src"), Path("tests"), Path("scripts"))


@dataclass(frozen=True)
class DocstringIssue:
    """A docstring requirement violation.

    Attributes:
        path: File containing the violation.
        line: One-based line number.
        name: Function or class name.
        message: Violation details.
    """

    path: Path
    line: int
    name: str
    message: str


def main() -> int:
    """Check docstring rules.

    Returns:
        Process exit code.
    """
    issues = collect_issues(SOURCE_ROOTS)
    if issues:
        _write_line("Docstring check failed:")
        for issue in issues:
            _write_line(
                f"{issue.path}:{issue.line}: {issue.name}: {issue.message}",
            )
        return 1
    _write_line("Docstring check passed.")
    return 0


def collect_issues(roots: tuple[Path, ...]) -> tuple[DocstringIssue, ...]:
    """Collect docstring issues from Python source roots.

    Args:
        roots: Directories to inspect.

    Returns:
        Sorted docstring issues.
    """
    issues: list[DocstringIssue] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            issues.extend(_file_issues(path))
    return tuple(issues)


def _file_issues(path: Path) -> tuple[DocstringIssue, ...]:
    """Collect docstring issues from one Python file.

    Args:
        path: Python file to parse.

    Returns:
        Docstring issues found in the file.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    issues: list[DocstringIssue] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            issues.extend(_function_issues(path, node))
    return tuple(issues)


def _function_issues(
    path: Path,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[DocstringIssue, ...]:
    """Collect function docstring issues.

    Args:
        path: File containing the function.
        node: Function AST node.

    Returns:
        Docstring issues for the function.
    """
    docstring = ast.get_docstring(node) or ""
    issues: list[DocstringIssue] = []
    if node.name.startswith("_") and not docstring:
        issues.append(
            DocstringIssue(
                path,
                node.lineno,
                node.name,
                "private functions must have Google-style docstrings",
            ),
        )
    if node.name.startswith("test_") and "Requirement:" not in docstring:
        issues.append(
            DocstringIssue(
                path,
                node.lineno,
                node.name,
                "test docstring must state the verified requirement",
            ),
        )
    return tuple(issues)


def _write_line(message: str) -> None:
    """Write one line to standard output.

    Args:
        message: Text to write.
    """
    sys.stdout.write(f"{message}\n")


if __name__ == "__main__":
    raise SystemExit(main())
