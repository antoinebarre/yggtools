"""Individual steps of the init-repo pipeline.

Each step is a plain function that receives a ``RepoContext`` and performs
one focused action.  Steps must not call each other — ordering is the
responsibility of ``pipeline.py``.
"""

from __future__ import annotations

import importlib.resources
import tomllib
from dataclasses import dataclass
from pathlib import Path

import jinja2

from yggtools.uv import (
    DEV_DEPS,
    CommandError,
    git_commit,
    uv_add_dev,
    uv_init_lib,
)


@dataclass(frozen=True)
class RepoContext:
    """Immutable context for the init-repo pipeline.

    Attributes:
        project_name: Name of the project (used by ``uv init --lib``).
        python_version: Target Python version string (e.g. ``"3.12"``).
        parent_dir: Directory in which the project will be created.
        no_git: When True, skip CI workflow generation and final commit.
        dry_run: When True, print actions without writing anything.
    """

    project_name: str
    python_version: str
    parent_dir: Path
    no_git: bool = False
    dry_run: bool = False

    @property
    def project_dir(self) -> Path:
        """Absolute path to the project directory.

        Returns:
            ``parent_dir / project_name``.
        """
        return self.parent_dir / self.project_name


class StepError(RuntimeError):
    """Raised when a pipeline step fails for a recoverable reason."""


def step_uv_init(ctx: RepoContext) -> None:
    """Run ``uv init --lib`` to create the base project structure.

    Creates ``src/<package>/``, ``pyproject.toml``, ``.python-version``,
    ``.gitignore``, ``README.md``, and the initial git commit via uv.

    Args:
        ctx: Pipeline context.

    Raises:
        StepError: If ``uv init`` fails.
    """
    if ctx.dry_run:
        return
    try:
        uv_init_lib(ctx.parent_dir, ctx.project_name, ctx.python_version)
    except CommandError as exc:
        msg = f"uv init --lib failed: {exc}"
        raise StepError(msg) from exc


def step_add_dev_deps(ctx: RepoContext) -> None:
    """Add yggtools and quality tooling as dev dependencies.

    Runs ``uv add --dev yggtools bandit mypy ruff pytest …`` inside the
    newly created project directory.

    Args:
        ctx: Pipeline context.

    Raises:
        StepError: If ``uv add --dev`` fails.
    """
    if ctx.dry_run:
        return
    try:
        uv_add_dev(ctx.project_dir, DEV_DEPS)
    except CommandError as exc:
        msg = f"uv add --dev failed: {exc}"
        raise StepError(msg) from exc


def _collect_pyproject_additions(
    existing: dict[str, object],
    package_name: str,
) -> list[str]:
    """Build the list of TOML sections to append to pyproject.toml.

    Each section is only included when the corresponding key is absent from
    ``existing``, so that repeated runs are idempotent.

    Args:
        existing: Parsed content of the current pyproject.toml.
        package_name: Normalised package name (hyphens → underscores).

    Returns:
        List of TOML section strings ready to be appended.
    """
    raw_tool = existing.get("tool", {})
    tool: dict[str, object] = raw_tool if isinstance(raw_tool, dict) else {}
    additions: list[str] = []

    if "pytest" not in tool:
        cov_opts = (
            f'"--tb=short --cov=src/{package_name}'
            ' --cov-report=term-missing --cov-fail-under=100"'
        )
        additions.append(
            f"\n[tool.pytest.ini_options]\n"
            f'testpaths = ["tests"]\n'
            f"addopts = {cov_opts}\n"
            f'pythonpath = ["src"]\n'
            f'cache_dir = "work/.pytest_cache"\n'
            f"\n[tool.coverage.run]\n"
            f'data_file = "work/.coverage"\n'
            f'source = ["src/{package_name}"]\n',
        )
    if "mypy" not in tool:
        additions.append("""
[tool.mypy]
strict = true
mypy_path = "src"
cache_dir = "work/.mypy_cache"
""")
    if "ruff" not in tool:
        additions.append("""
[tool.ruff]
cache-dir = "work/.ruff_cache"
line-length = 79

[tool.ruff.lint]
select = ["ALL"]
ignore = ["TC001", "TC002", "TC003", "TC004"]

[tool.ruff.lint.pydocstyle]
convention = "google"
""")
    if "flake8" not in tool:
        additions.append("""
[tool.flake8]
max-line-length = 79
max-complexity = 10
docstring-convention = "google"
count = true
show-source = true
statistics = true
""")
    if "bandit" not in tool:
        additions.append("""
[tool.bandit]
exclude_dirs = ["tests", "work", ".venv"]
""")
    raw_ygg = tool.get("yggtools", {}) if isinstance(tool, dict) else {}
    yggtools_tool = raw_ygg if isinstance(raw_ygg, dict) else {}
    if "code_metrics" not in yggtools_tool:
        additions.append(f"""
[tool.yggtools.code_metrics]
paths = ["src/{package_name}", "tests"]
exclude = []
max_cyclomatic_complexity = 10
max_module_logical_lines = 900
""")
    return additions


def step_patch_pyproject(ctx: RepoContext) -> None:
    """Append yggtools tool sections to the project's pyproject.toml.

    Adds ``[tool.ruff]``, ``[tool.mypy]``, ``[tool.pytest.ini_options]``,
    ``[tool.coverage.run]``, ``[tool.flake8]``, ``[tool.bandit]``, and
    ``[tool.yggtools.code_metrics]`` blocks.  Existing keys are not
    overwritten — the function appends only sections that are absent.

    Args:
        ctx: Pipeline context.
    """
    if ctx.dry_run:
        return
    pyproject = ctx.project_dir / "pyproject.toml"
    with pyproject.open("rb") as fh:
        existing = tomllib.load(fh)
    package_name = ctx.project_name.replace("-", "_")
    additions = _collect_pyproject_additions(existing, package_name)
    if additions:
        with pyproject.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(additions))


def step_write_makefile(ctx: RepoContext) -> None:
    """Render and write the Makefile into the project directory.

    Args:
        ctx: Pipeline context.
    """
    if ctx.dry_run:
        return
    content = _render_template("Makefile.tmpl")
    (ctx.project_dir / "Makefile").write_text(content, encoding="utf-8")


def step_write_tests_dir(ctx: RepoContext) -> None:
    """Create the ``tests/`` directory with a minimal ``conftest.py``.

    Args:
        ctx: Pipeline context.
    """
    if ctx.dry_run:
        return
    tests_dir = ctx.project_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / "__init__.py").write_text(
        '"""Test suite."""\n',
        encoding="utf-8",
    )
    (tests_dir / "conftest.py").write_text(
        '"""Pytest configuration."""\n',
        encoding="utf-8",
    )


def step_write_work_dir(ctx: RepoContext) -> None:
    """Create the ``work/`` directory with a ``.gitkeep`` placeholder.

    Args:
        ctx: Pipeline context.
    """
    if ctx.dry_run:
        return
    work_dir = ctx.project_dir / "work"
    work_dir.mkdir(exist_ok=True)
    (work_dir / ".gitkeep").write_text("", encoding="utf-8")


def step_write_ci(ctx: RepoContext) -> None:
    """Render and write CI workflow files for GitHub Actions and GitLab CI.

    Skipped when ``ctx.no_git`` is True.

    Args:
        ctx: Pipeline context.
    """
    if ctx.no_git or ctx.dry_run:
        return
    python_version = ctx.python_version
    github_content = _render_template(
        "github_ci.yml.tmpl",
        python_version=python_version,
    )
    github_dir = ctx.project_dir / ".github" / "workflows"
    github_dir.mkdir(parents=True, exist_ok=True)
    (github_dir / "ci.yml").write_text(github_content, encoding="utf-8")

    gitlab_content = _render_template(
        "gitlab_ci.yml.tmpl",
        python_version=python_version,
    )
    (ctx.project_dir / ".gitlab-ci.yml").write_text(
        gitlab_content,
        encoding="utf-8",
    )


def step_git_commit(ctx: RepoContext) -> None:
    """Stage all new files and create the final init-repo commit.

    Skipped when ``ctx.no_git`` or ``ctx.dry_run`` is True.

    Args:
        ctx: Pipeline context.
    """
    if ctx.no_git or ctx.dry_run:
        return
    git_commit(ctx.project_dir, "chore: yggtools init-repo")


def step_write_claude_md(ctx: RepoContext) -> None:
    """Render and write CLAUDE.md into the project directory.

    CLAUDE.md contains the coding standards and Claude Code instructions
    for the scaffolded project.

    Args:
        ctx: Pipeline context.
    """
    if ctx.dry_run:
        return
    package_name = ctx.project_name.replace("-", "_")
    content = _render_template("CLAUDE.md.tmpl", package_name=package_name)
    (ctx.project_dir / "CLAUDE.md").write_text(content, encoding="utf-8")


def _render_template(name: str, **variables: str) -> str:
    """Load and render a Jinja2 template from the repo_init/templates package.

    Args:
        name: Template filename (e.g. ``"Makefile.tmpl"``).
        **variables: Template variables passed to Jinja2.

    Returns:
        Rendered template string.
    """
    pkg = importlib.resources.files("yggtools.repo_init.templates")
    source = pkg.joinpath(name).read_text(encoding="utf-8")
    return jinja2.Template(source, undefined=jinja2.StrictUndefined).render(
        **variables,
    )
