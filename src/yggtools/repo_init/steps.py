"""Individual steps of the init-repo pipeline.

Each step is a plain function that receives a ``RepoContext`` and performs
one focused action.  Steps must not call each other — ordering is the
responsibility of ``pipeline.py``.
"""

from __future__ import annotations

import importlib.resources
import re
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


_INIT_VERSION_RE = re.compile(r"^__version__\s*=", re.MULTILINE)


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


def step_ensure_package_layout(ctx: RepoContext) -> None:
    """Ensure the project has the expected ``src/<package>`` layout.

    This repairs projects created with ``uv init`` without ``--lib`` by
    creating the missing ``src`` package directory and a minimal
    ``__init__.py``.  Existing packages are preserved; if an initializer
    exists without ``__version__``, the version assignment is appended.

    Args:
        ctx: Pipeline context.

    Raises:
        StepError: If pyproject.toml is missing required project metadata.
    """
    if ctx.dry_run:
        return
    project_name, version = _read_project_identity(ctx)
    package_name = _package_name(project_name)
    package_dir = ctx.project_dir / "src" / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    init_file = package_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text(
            f'"""Top-level package for {project_name}."""\n\n'
            f'__version__ = "{version}"\n',
            encoding="utf-8",
        )
        return
    content = init_file.read_text(encoding="utf-8")
    if _INIT_VERSION_RE.search(content):
        return
    separator = "" if content.endswith("\n") else "\n"
    init_file.write_text(
        f'{content}{separator}\n__version__ = "{version}"\n',
        encoding="utf-8",
    )


def _read_project_identity(ctx: RepoContext) -> tuple[str, str]:
    """Read project name and version from pyproject.toml.

    Args:
        ctx: Pipeline context.

    Returns:
        Project name and version.

    Raises:
        StepError: If the pyproject metadata is absent or malformed.
    """
    pyproject = ctx.project_dir / "pyproject.toml"
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    project = data.get("project", {})
    if not isinstance(project, dict):
        msg = "pyproject.toml must contain a [project] table."
        raise StepError(msg)
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        msg = "pyproject.toml must define [project].name and version."
        raise StepError(msg)
    return name, version


def _package_name(project_name: str) -> str:
    """Normalize a distribution name to an import package name.

    Args:
        project_name: Distribution name from pyproject.toml.

    Returns:
        Import package directory name.
    """
    return project_name.replace("-", "_")


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


def _pytest_section(package_name: str) -> str:
    """Generate the pytest and coverage TOML sections.

    Args:
        package_name: Normalised package name.

    Returns:
        TOML string for ``[tool.pytest.ini_options]`` and
        ``[tool.coverage.run]``.
    """
    cov_opts = (
        f'"--tb=short --cov=src/{package_name}'
        ' --cov-report=term-missing --cov-fail-under=100"'
    )
    return (
        f"\n[tool.pytest.ini_options]\n"
        f'testpaths = ["tests"]\n'
        f"addopts = {cov_opts}\n"
        f'pythonpath = ["src"]\n'
        f'cache_dir = "work/.pytest_cache"\n'
        f"\n[tool.coverage.run]\n"
        f'data_file = "work/.coverage"\n'
        f'source = ["src/{package_name}"]\n'
    )


def _mypy_section() -> str:
    """Generate the mypy TOML section.

    Returns:
        TOML string for ``[tool.mypy]``.
    """
    return """
[tool.mypy]
strict = true
mypy_path = "src"
cache_dir = "work/.mypy_cache"
"""


def _ruff_section() -> str:
    """Generate the ruff TOML sections.

    Returns:
        TOML string for ``[tool.ruff]`` and sub-tables.
    """
    return """
[tool.ruff]
cache-dir = "work/.ruff_cache"
line-length = 79

[tool.ruff.lint]
select = ["ALL"]
ignore = ["TC001", "TC002", "TC003", "TC004"]

[tool.ruff.lint.pydocstyle]
convention = "google"
"""


def _flake8_section() -> str:
    """Generate the flake8 TOML section.

    Returns:
        TOML string for ``[tool.flake8]``.
    """
    return """
[tool.flake8]
max-line-length = 79
max-complexity = 10
docstring-convention = "google"
count = true
show-source = true
statistics = true
"""


def _bandit_section() -> str:
    """Generate the bandit TOML section.

    Returns:
        TOML string for ``[tool.bandit]``.
    """
    return """
[tool.bandit]
exclude_dirs = ["tests", "work", ".venv"]
"""


def _code_metrics_section(package_name: str) -> str:
    """Generate the yggtools code_metrics TOML section.

    Args:
        package_name: Normalised package name.

    Returns:
        TOML string for ``[tool.yggtools.code_metrics]``.
    """
    return f"""
[tool.yggtools.code_metrics]
paths = ["src/{package_name}", "tests"]
exclude = []
max_cyclomatic_complexity = 10
max_module_logical_lines = 900
"""


def _extract_tool_section(
    existing: dict[str, object],
) -> dict[str, object]:
    """Extract the ``[tool]`` section from parsed pyproject.toml.

    Args:
        existing: Parsed content of the current pyproject.toml.

    Returns:
        The tool dict, or an empty dict if absent or malformed.
    """
    raw = existing.get("tool", {})
    return raw if isinstance(raw, dict) else {}


def _collect_pyproject_additions(
    existing: dict[str, object],
    package_name: str,
) -> list[str]:
    """Build the list of TOML sections to append to pyproject.toml.

    Each section is only included when the corresponding key is absent
    from ``existing``, so that repeated runs are idempotent.

    Args:
        existing: Parsed content of the current pyproject.toml.
        package_name: Normalised package name (hyphens → underscores).

    Returns:
        List of TOML section strings ready to be appended.
    """
    tool = _extract_tool_section(existing)
    sections: list[tuple[str, str]] = [
        ("pytest", _pytest_section(package_name)),
        ("mypy", _mypy_section()),
        ("ruff", _ruff_section()),
        ("flake8", _flake8_section()),
        ("bandit", _bandit_section()),
    ]
    additions = [content for key, content in sections if key not in tool]
    raw_ygg = tool.get("yggtools", {})
    ygg = raw_ygg if isinstance(raw_ygg, dict) else {}
    if "code_metrics" not in ygg:
        additions.append(_code_metrics_section(package_name))
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
    project_name, _version = _read_project_identity(ctx)
    package_name = _package_name(project_name)
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
    package_name = _package_name(ctx.project_name)
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
