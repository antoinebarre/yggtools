# SDD — Software Design Document

**Project:** yggtools
**Version:** 2.1
**Date:** 2026-06-21
**Author:** Antoine Barré
**Status:** Approved

---

## Table of contents

1. [Design objectives and constraints](#1-design-objectives-and-constraints)
2. [Package structure](#2-package-structure)
3. [Sub-package: `quality`](#3-sub-package-quality)
4. [Sub-package: `repo_init`](#4-sub-package-repo_init)
5. [Adapter: `uv.py`](#5-adapter-uvpy)
6. [CLI: `cli.py`](#6-cli-clipy)
7. [Templates](#7-templates)
8. [Execution flows](#8-execution-flows)
9. [Error handling](#9-error-handling)
10. [Testing strategy](#10-testing-strategy)
11. [yggtools own CI](#11-yggtools-own-ci)

---

## 1. Design objectives and constraints

### 1.1 Objectives

- **No scripts in scaffolded projects.** Quality tooling lives inside
  `yggtools`, versioned and updated as one unit.
- **All Python, no shell.** The quality pipeline is implemented in Python:
  testable, type-checked, portable.
- **Open/Closed.** Adding a new check or a new init step must not require
  modifying existing code.
- **Minimal external dependencies.** Only `typer`, `rich`, and `jinja2`.

### 1.2 Design patterns used

| Pattern | Where | Why |
|---------|-------|-----|
| Registry | `quality/runner.py` | New checks registered via `@register("name")` |
| Strategy | `quality/checks/` | Each check is one `CheckFn` function |
| Pipeline | `repo_init/pipeline.py` | Ordered `STEPS` list, independently testable |
| Adapter | `uv.py` | All subprocess calls in one place |

### 1.3 Constraints

- All subprocess calls (`uv`, `git`) go through `uv.py`.
- Check functions SHALL NOT raise — failures are returned as `CheckResult`.
- Templates are Jinja2 files accessed via `importlib.resources`.

---

## 2. Package structure

```
src/yggtools/
├── __init__.py
├── cli.py                    # Thin Typer composition entry point
├── cli_support.py            # Shared CLI path and text helpers
├── uv.py                     # Adapter: uv and git subprocess calls
├── version_commands.py       # Typer commands: version, increase-version
├── version_display.py        # Rich rendering for version commands
├── versioning.py             # SemVer bumping across package artifacts
├── quality/
│   ├── __init__.py
│   ├── commands.py           # Typer commands: pipeline, run
│   ├── display.py            # Rich rendering for quality command output
│   ├── objectives.py         # Quality objective row calculation
│   ├── pipeline.py           # Staged orchestration + JSON artifacts
│   ├── runner.py             # Registry, CheckFn protocol, run_all / run_one
│   ├── report.py             # Legacy Markdown report helper
│   └── checks/
│       ├── __init__.py
│       ├── format.py         # @register("format")
│       ├── lint.py           # @register("ruff"), @register("flake8")
│       ├── typecheck.py      # @register("typecheck")
│       ├── metrics.py        # @register("metrics")
│       ├── security.py       # @register("security-code"), @register("security-deps")
│       ├── tests.py          # @register("tests")
│       └── version.py        # @register("version-consistency")
└── repo_init/
    ├── __init__.py
    ├── commands.py           # Typer commands: init-repo, init, reset
    ├── display.py            # Dry-run and progress rendering
    ├── pipeline.py           # STEPS list + run_pipeline()
    ├── steps.py              # RepoContext, StepError, one function per step
    └── templates/            # Jinja2 templates (package resource)
        ├── __init__.py
        ├── Makefile.tmpl
        ├── github_ci.yml.tmpl
        ├── gitlab_ci.yml.tmpl
        └── CLAUDE.md.tmpl
```

---

## 3. Sub-package: `quality`

### 3.1 `quality/runner.py`

```python
@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str

class CheckFn(Protocol):
    def __call__(self, project_dir: Path) -> CheckResult: ...

_REGISTRY: dict[str, CheckFn] = {}

def register(name: str) -> Callable[[CheckFn], CheckFn]: ...
def registered_checks() -> list[str]: ...
def run_one(name: str, project_dir: Path) -> CheckResult: ...
def run_all(project_dir: Path) -> list[CheckResult]: ...
```

`_REGISTRY` is a module-level dict. `register` is a decorator factory that
stores the function under `name` and returns it unchanged.

`run_one` raises `KeyError` if `name` is not registered. `run_all` iterates
`_REGISTRY.values()` in insertion order.

The registry is populated at import time when the check modules are imported.
`cli.py` imports all check modules at top level so the registry is fully
populated before any command runs.

### 3.2 `quality/checks/`

Each module in this package exports exactly one function decorated with
`@register`. The function signature matches `CheckFn`:

```python
def check_format(project_dir: Path) -> CheckResult:
    ...
```

Every check:
1. Builds a `uv run <tool>` command via `run_uv()`.
2. Captures stdout/stderr.
3. Returns `CheckResult(passed=..., detail=...)`.
4. Does NOT raise.

**Registered checks and their tools:**

| Module | Name | Tool / approach |
|--------|------|----------------|
| `format.py` | `format` | `ruff format --check src tests` |
| `lint.py` | `ruff` | `ruff check src tests` |
| `lint.py` | `flake8` | `flake8 src tests` |
| `version.py` | `version-consistency` | Version artifact consistency |
| `typecheck.py` | `typecheck` | `mypy src tests` |
| `metrics.py` | `metrics` | Pure Python AST analysis |
| `security.py` | `security-code` | `bandit -r src` |
| `security.py` | `security-deps` | `pip-audit` on `uv export --no-dev` |
| `tests.py` | `tests` | `pytest` |

### 3.3 `quality/checks/metrics.py` — internal design

`metrics.py` does not call an external tool. It:

1. Reads `[tool.yggtools.code_metrics]` from `pyproject.toml` using
   `tomllib`.
2. Walks configured `paths` and applies `ast.parse` on each `.py` file.
3. Counts cyclomatic complexity using `ast.walk`:
   - +1 per `If`, `For`, `While`, `ExceptHandler`, `With`, `Assert`,
     `comprehension`
   - +(`n-1`) per `BoolOp` with `n` operands
   - +1 per `IfExp`
4. Counts logical lines: `ast.stmt` nodes excluding `FunctionDef`,
   `AsyncFunctionDef`, `ClassDef`.
5. Returns a `CheckResult` listing the first violation or confirming all
   metrics pass.

Configuration defaults (read from `[tool.yggtools.code_metrics]`):

| Key | Default |
|-----|---------|
| `paths` | `["src", "tests"]` |
| `exclude` | `[]` |
| `max_cyclomatic_complexity` | `10` |
| `max_module_logical_lines` | `900` |

### 3.4 `quality/pipeline.py`

```python
@dataclass(frozen=True)
class Stage:
    name: str
    checks: tuple[str, ...]

def run_pipeline(project_dir: Path) -> PipelineResult: ...
def write_pipeline_artifacts(result, project_dir, output_dir) -> PipelineReport: ...
```

The pipeline runs staged checks in deterministic order and writes one JSON
artifact per check plus `pipeline.json`, each with a `.sha256` sidecar.

### 3.5 `quality/report.py`

```python
def write_report(
    results: list[CheckResult],
    project_dir: Path,
    output: Path,
) -> None: ...
```

Legacy helper for Markdown report output. The primary pipeline artifact
contract is now JSON under `work/reports/`.

---

## 4. Sub-package: `repo_init`

### 4.1 `repo_init/steps.py`

```python
@dataclass(frozen=True)
class RepoContext:
    project_name: str
    python_version: str
    parent_dir: Path
    no_git: bool = False
    dry_run: bool = False

    @property
    def project_dir(self) -> Path: ...

class StepError(RuntimeError): ...
```

Each step is a top-level function `step_<name>(ctx: RepoContext) -> None`.
Steps raise `StepError` on failure; they never swallow exceptions silently.

| Function | What it does |
|----------|-------------|
| `step_uv_init` | Calls `uv_init_lib(parent_dir, name, python)` |
| `step_ensure_package_layout` | Creates or repairs `src/<package>/__init__.py` |
| `step_add_dev_deps` | Calls `uv_add_dev(project_dir, DEV_DEPS)` |
| `step_patch_pyproject` | Appends missing tool sections to `pyproject.toml` |
| `step_write_makefile` | Renders `Makefile.tmpl` → `Makefile` |
| `step_write_tests_dir` | Creates `tests/__init__.py` and `tests/conftest.py` |
| `step_write_work_dir` | Creates `work/.gitkeep` |
| `step_write_ci` | Renders GitHub and GitLab CI templates |
| `step_git_commit` | Calls `git_commit(project_dir, "chore: yggtools init-repo")` |

`step_write_ci` and `step_git_commit` are no-ops when `ctx.no_git is True`.

Template rendering uses `importlib.resources.files("yggtools.repo_init.templates")`.

### 4.2 `repo_init/pipeline.py`

```python
@dataclass(frozen=True)
class PipelineStep:
    name: str
    fn: Callable[[RepoContext], None]

STEPS: list[PipelineStep] = [
    PipelineStep("uv init --lib",           step_uv_init),
    PipelineStep("ensure src package layout", step_ensure_package_layout),
    PipelineStep("add dev dependencies",     step_add_dev_deps),
    PipelineStep("patch pyproject.toml",     step_patch_pyproject),
    PipelineStep("write Makefile",           step_write_makefile),
    PipelineStep("create tests/",            step_write_tests_dir),
    PipelineStep("create work/",             step_write_work_dir),
    PipelineStep("write CI workflows",       step_write_ci),
    PipelineStep("git commit",               step_git_commit),
]

def run_pipeline(ctx: RepoContext) -> None: ...
```

`run_pipeline` iterates `STEPS` and calls `step.fn(ctx)`. It propagates
`StepError` to the caller (the CLI).

---

## 5. Adapter: `uv.py`

All subprocess calls to `uv` and `git` go through this module.

```python
DEV_DEPS: list[str]            # fixed list of quality tools + yggtools

class UvNotFoundError(RuntimeError): ...
class CommandError(RuntimeError):
    returncode: int
    stderr: str

@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str
    stderr: str

def check_uv_available() -> None: ...
def run_uv(args, *, cwd, capture, check) -> RunResult: ...
def uv_init_lib(project_dir, project_name, python_version) -> None: ...
def uv_add_dev(project_dir, deps) -> None: ...
def uv_sync(project_dir) -> None: ...
def git_commit(project_dir, message) -> None: ...
```

`run_uv` uses `subprocess.run` with `check=False` and raises `CommandError`
manually when `check=True` and the return code is non-zero. This gives
uniform error reporting.

`git_commit` runs `git add -A` then `git commit -m <message>` in sequence,
both with `check=True`.

---

## 6. CLI composition and command modules

```python
app = typer.Typer(name="yggtools")

register_quality_commands(app)
register_repo_init_commands(app)
register_version_commands(app)
```

`cli.py` owns only the package entry point and command composition. Business
commands live beside their owning domain:

| Module | Commands | Responsibility |
| --- | --- | --- |
| `quality.commands` | `pipeline`, `run` | Quality check orchestration and JSON artifact writing |
| `repo_init.commands` | `init-repo`, `init`, `reset` | Repository scaffold and generated-file reset workflows |
| `version_commands` | `version`, `increase-version` | Version inspection and SemVer bump entry points |

All check modules are imported at module level in `quality.commands` to
populate the registry before any quality command is dispatched.

### `init-repo` flow

```
init_repo()
  ├── build RepoContext
  ├── if dry_run → display.print_dry_run_plan(ctx) and return
  ├── check_uv_available()        → exit 1 on UvNotFoundError
  ├── run_with_progress(ctx)      → exit 1 on StepError or Exception
  └── print success message
```

### `run` flow

```
run()
  ├── if not (check_name or all_checks) → exit 1 with usage error
  ├── resolve project_dir (path or cwd)
  ├── run one check or all registered checks
  ├── write one JSON artifact per result
  ├── print compact summary
  └── exit 0 if all passed else 1
```

---

### `version` flow

```
version()
  ├── collect version artifacts from pyproject.toml, src/<package>/__init__.py, uv.lock
  ├── print Rich table
  └── exit 1 when a required artifact is missing or versions differ
```

### `increase-version` flow

```
increase_version()
  ├── read [project].version
  ├── compute SemVer bump from level 1/2/3
  ├── update pyproject.toml, src/<package>/__init__.py, uv.lock
  └── run uv lock
```

---

## 7. Templates

Templates are Jinja2 files in `src/yggtools/repo_init/templates/`, accessed
at runtime via:

```python
importlib.resources.files("yggtools.repo_init.templates").joinpath(name)
```

| File | Variables |
|------|-----------|
| `Makefile.tmpl` | `project_name` |
| `github_ci.yml.tmpl` | `python_version` |
| `gitlab_ci.yml.tmpl` | `python_version` |

The `templates/` directory is a Python package (contains `__init__.py`) so
hatchling includes it in the wheel automatically.

---

## 8. Execution flows

### 8.1 `yggtools init-repo my-lib`

```
CLI
 └── RepoContext(project_name="my-lib", python_version="3.12", ...)
      │
      └── run_pipeline(ctx)
           ├── step_uv_init       → uv_init_lib(parent, "my-lib", "3.12")
           ├── step_ensure_package_layout → src/my_lib/__init__.py + __version__
           ├── step_add_dev_deps  → uv_add_dev(project_dir, DEV_DEPS)
           ├── step_patch_pyproject → read pyproject.toml, append sections
           ├── step_write_makefile  → render Makefile.tmpl → Makefile
           ├── step_write_tests_dir → tests/__init__.py, tests/conftest.py
           ├── step_write_work_dir  → work/.gitkeep
           ├── step_write_ci        → .github/workflows/ci.yml
           └── step_git_commit      → git add -A && git commit
```

### 8.2 `yggtools pipeline` (from inside a project)

```
CLI
 └── run_pipeline(project_dir)
      ├── check_format(project_dir)       → run_uv(["run","ruff","format","--check",...])
      ├── check_ruff(project_dir)         → run_uv(["run","ruff","check",...])
      ├── check_flake8(project_dir)       → run_uv(["run","flake8",...])
      ├── check_version_consistency(project_dir) → pure Python artifact audit
      ├── check_typecheck(project_dir)    → run_uv(["run","mypy",...])
      ├── check_metrics(project_dir)      → AST analysis (pure Python)
      ├── check_security_code(project_dir)→ run_uv(["run","bandit",...])
      ├── check_security_deps(project_dir)→ run_uv(["run","pip-audit",...])
      └── check_tests(project_dir)        → run_uv(["run","pytest"])
      └── write_pipeline_artifacts(...)   → work/reports/*.json + *.sha256
```

---

## 9. Error handling

### 9.1 Exception hierarchy

```python
class UvNotFoundError(RuntimeError): ...

class CommandError(RuntimeError):
    returncode: int
    stderr: str

class StepError(RuntimeError): ...
```

### 9.2 CLI handling

| Exception | Handler |
|-----------|---------|
| `UvNotFoundError` | Print install URL, exit 1 |
| `StepError` | Print step name and message, exit 1 |
| `Exception` | Print unexpected error, exit 1 |

Check functions (`CheckFn`) never raise — they return `CheckResult(passed=False)`.

---

## 10. Testing strategy

### 10.1 Test organisation

```
tests/
├── conftest.py               # project_dir fixture
└── unit/
    ├── test_runner.py        # Registry: register, run_one, run_all
    ├── test_checks.py        # All 9 check functions (mocked run_uv)
    ├── test_report.py        # legacy report writer
    ├── test_steps.py         # All 8 pipeline steps (mocked uv.py)
    ├── test_pipeline.py      # STEPS non-empty, unique names, execution order
    ├── test_uv.py            # Adapter: check_uv_available, run_uv, git_commit
    ├── test_versioning.py    # SemVer and artifact updates
    └── test_cli.py           # CLI commands (mocked internals where needed)
```

### 10.2 Key testing patterns

**Registry isolation:** each test that mutates `_REGISTRY` saves `dict(_REGISTRY)`,
clears it, and restores it in a `finally` block.

**Pipeline step isolation:** steps are tested with a `RepoContext` pointing
to `tmp_path`. All uv/git calls are patched via `unittest.mock.patch`.

**Frozen dataclass patching:** `PipelineStep` is frozen, so pipeline tests
patch `STEPS` wholesale:

```python
spied = [type(step)(name=step.name, fn=_make_spy(step.name)) for step in STEPS]
with patch("yggtools.repo_init.pipeline.STEPS", spied):
    run_pipeline(ctx)
```

### 10.3 Coverage

100% branch coverage is enforced via `--cov-fail-under=100`. Templates are
excluded from coverage measurement (`omit = ["src/yggtools/repo_init/templates/*"]`).

---

## 11. yggtools own CI

### 11.1 Files

| File | Trigger | Role |
|------|---------|------|
| `.github/workflows/ci.yml` | push / PR → `main`, `master` | Full quality pipeline |
| `.github/workflows/publish.yml` | tag `v*.*.*` | Quality gate + PyPI publish |

### 11.2 CI workflow

```
trigger: push or PR → main / master

job: quality (matrix: 3.12, 3.13, fail-fast: false)
  ├── actions/checkout@v4
  ├── astral-sh/setup-uv@v5 (cache enabled)
  ├── uv python install <version>
  ├── uv sync --python <version>
  ├── make ci
  └── actions/upload-artifact@v4  (work/reports/, if: always)
```

### 11.3 Publish workflow

```
trigger: push of tag v[0-9]+.[0-9]+.[0-9]*

job: quality (Python 3.12)
  └── make ci   ← blocking gate

job: publish (needs: quality)
  permissions: id-token: write   ← OIDC for PyPI Trusted Publishing
  environment: pypi
  ├── verify tag matches pyproject.toml version
  ├── rm -rf dist && uv build --out-dir dist/
  ├── uv run twine check dist/*
  └── pypa/gh-action-pypi-publish@release/v1
```

### 11.4 PyPI Trusted Publishing configuration

Before the first publish, configure on pypi.org → Project → Publishing:

| Field | Value |
|-------|-------|
| Owner | `antoinebarre` |
| Repository | `yggtools` |
| Workflow filename | `publish.yml` |
| Environment | `pypi` |

No `PYPI_TOKEN` secret is needed in the GitHub repository.
