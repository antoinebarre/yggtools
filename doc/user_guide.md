# yggtools — User Guide

**Version:** 1.0.0
**Date:** 2026-06-20

---

## Table of contents

1. [What is yggtools?](#1-what-is-yggtools)
2. [Prerequisites](#2-prerequisites)
3. [Installation](#3-installation)
4. [Quick start](#4-quick-start)
5. [Command reference](#5-command-reference)
6. [Project structure generated](#6-project-structure-generated)
7. [Quality pipeline](#7-quality-pipeline)
8. [CI workflows](#8-ci-workflows)
9. [Publishing a package](#9-publishing-a-package)
10. [Typical day-to-day workflow](#10-typical-day-to-day-workflow)

---

## 1. What is yggtools?

`yggtools` is a CLI dev tool that scaffolds opinionated Python packages
managed by [uv](https://docs.astral.sh/uv/). A single command creates a
complete, ready-to-run project and installs a quality pipeline you can run
with `make check`.

Key design decisions:

- **No scripts in the scaffolded project.** The generated `Makefile` calls
  `uv run yggtools run --all`. Quality tooling stays inside `yggtools` and
  is updated by upgrading the tool, not by copying files into every project.
- **`uv init --lib` first.** The scaffolding delegates to `uv init --lib`,
  which creates the canonical `src/` layout and keeps the project structure
  in sync with uv conventions.
- **All Python, no shell.** The quality pipeline is implemented in Python
  (Registry + Strategy pattern), making it testable and type-checked.
- **Two modes, one pipeline.** `init-repo` is a one-shot convenience wrapper.
  `init` lets you run the same scaffold on an existing `uv init --lib`
  project, without requiring `yggtools` to be installed globally beforehand.

`yggtools` is a `uv` tool, so it never pollutes your project's virtual
environment.

---

## 2. Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.12 | Managed by uv |
| [uv](https://docs.astral.sh/uv/) | 0.5 | Required at runtime |
| git | 2.30 | Optional — used for the initial commit |

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 3. Installation

### Install as a uv tool (recommended)

`uv tool install` installs `yggtools` in an isolated environment and exposes
the `yggtools` command globally. It never conflicts with your project
dependencies.

```bash
uv tool install yggtools
```

Verify:

```bash
yggtools --help
```

### Upgrade

```bash
uv tool upgrade yggtools
```

### Uninstall

```bash
uv tool uninstall yggtools
```

### Install a specific version

```bash
uv tool install yggtools==1.0.0
```

---

## 4. Quick start

### Option A — one-shot (yggtools installed globally)

```bash
yggtools init-repo my-lib
cd my-lib
make check
```

### Option B — without global installation (recommended for CI or shared teams)

```bash
uv init --lib my-lib
cd my-lib
uvx yggtools init
make check
```

`uvx` runs `yggtools` from the uv tool cache without a permanent global
install. The `init` command detects the existing `pyproject.toml` and
completes the scaffold in place.

### Preview without writing anything

```bash
yggtools init-repo my-lib --dry-run
# or, inside an existing project:
yggtools init --dry-run
```

---

## 5. Command reference

### `yggtools init-repo`

```
yggtools init-repo [PROJECT_NAME] [OPTIONS]
```

Scaffold a new Python package from scratch. Creates the project directory,
then runs the full pipeline including `uv init --lib`.

`PROJECT_NAME` defaults to the current directory name.

| Option | Default | Description |
|--------|---------|-------------|
| `--python VERSION` | `3.12` | Target Python version |
| `--no-git` | off | Skip git commit and CI workflow generation |
| `--dry-run` | off | Print planned actions without writing |

**Examples:**

```bash
# Default — Python 3.12, with git
yggtools init-repo my-lib

# Target Python 3.13
yggtools init-repo my-lib --python 3.13

# Skip git and CI files
yggtools init-repo my-lib --no-git

# Preview only
yggtools init-repo my-lib --dry-run
```

**Pipeline steps executed:**

| # | Step | What it does |
|---|------|-------------|
| 1 | `uv init --lib` | Creates `src/` layout, `.gitignore`, `.python-version` |
| 2 | add dev deps | `uv add --dev yggtools <quality tools>` |
| 3 | patch pyproject | Adds `[tool.ruff]`, `[tool.mypy]`, `[tool.yggtools]` sections |
| 4 | write Makefile | Delegates all targets to `yggtools run` |
| 5 | write CLAUDE.md | Coding standards for Claude Code |
| 6 | create `tests/` | `__init__.py` and `conftest.py` |
| 7 | create `work/` | `.gitkeep` |
| 8 | write CI | `.github/workflows/ci.yml` (skipped with `--no-git`) |
| 9 | git commit | Initial commit (skipped with `--no-git`) |

---

### `yggtools init`

```
yggtools init [OPTIONS]
```

Complete the yggtools scaffold in the **current directory**. Designed to be
run after `uv init --lib`. Exits with code 1 if `pyproject.toml` is absent.

Runs all pipeline steps **except** `uv init --lib` (steps 2–9 above).

| Option | Default | Description |
|--------|---------|-------------|
| `--python VERSION` | `3.12` | Target Python version |
| `--no-git` | off | Skip git commit and CI workflow generation |
| `--dry-run` | off | Print planned actions without writing |

**Typical usage:**

```bash
uv init --lib my-lib
cd my-lib
uvx yggtools init           # or: yggtools init (if installed globally)
make check
```

This flow does not require `yggtools` to be installed before the project
exists, which avoids the circular dependency of `init-repo` on a global
install.

---

### `yggtools run`

```
yggtools run [CHECK_NAME] [OPTIONS]
```

Run quality checks on a project.

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `CHECK_NAME` | — | Name of a single check to run |
| `--all` | off | Run all registered checks |
| `--ci` | off | CI mode: also write `work/report.md` |
| `--path PATH` | current directory | Project root to audit |

**Examples:**

```bash
# Run all checks on the current project
yggtools run --all

# CI mode (same checks + markdown report)
yggtools run --all --ci

# Run a single check
yggtools run typecheck

# Run all checks on another project
yggtools run --all --path ~/projects/my-lib
```

**Available check names:**

| Name | Tool |
|------|------|
| `format` | `ruff format --check` |
| `ruff` | `ruff check` |
| `flake8` | `flake8` |
| `typecheck` | `mypy --strict` |
| `metrics` | Built-in CC and logical-line counter |
| `security-code` | `bandit -r src` |
| `security-deps` | `pip-audit` on runtime deps |
| `tests` | `pytest --cov-fail-under=100` |

---

## 6. Project structure generated

```
my-lib/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── .python-version
├── CLAUDE.md               ← coding standards for Claude Code
├── Makefile
├── README.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── my_lib/
│       ├── __init__.py
│       └── py.typed
├── tests/
│   ├── __init__.py
│   └── conftest.py
└── work/
    └── .gitkeep
```

### `pyproject.toml`

The file created by `uv init --lib` is extended with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src/<package> --cov-report=term-missing --cov-fail-under=100"
cache_dir = "work/.pytest_cache"

[tool.coverage.run]
data_file = "work/.coverage"
source = ["src/<package>"]

[tool.mypy]
strict = true
mypy_path = "src"
cache_dir = "work/.mypy_cache"

[tool.ruff]
line-length = 79
cache-dir = "work/.ruff_cache"

[tool.ruff.lint]
select = ["ALL"]
ignore = ["TC001", "TC002", "TC003", "TC004"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.flake8]
max-line-length = 79
max-complexity = 10
docstring-convention = "google"

[tool.bandit]
exclude_dirs = ["tests", "work", ".venv"]

[tool.yggtools.code_metrics]
paths = ["src/<package>", "tests"]
max_cyclomatic_complexity = 10
max_module_logical_lines = 900
```

### `CLAUDE.md`

Pre-filled coding standards for [Claude Code](https://claude.ai/code):
PEP rules, Google-style docstrings, SOLID principles, 100% test coverage,
cyclomatic complexity ≤ 10, module size ≤ 500 lines.

Claude Code reads this file automatically when you open the project.

### `Makefile`

All targets delegate to `yggtools run` or standard `uv` commands.

| Target | What it does |
|--------|-------------|
| `make check` | `uv run yggtools run --all` |
| `make ci` | `uv run yggtools run --all --ci` |
| `make format` | `uv run ruff format src tests` |
| `make test` | `uv run pytest` |
| `make lint` | `uv run ruff check src tests` |
| `make typecheck` | `uv run mypy src tests` |
| `make metrics` | `uv run yggtools run metrics` |
| `make security` | `uv run yggtools run security-code && security-deps` |
| `make clean` | Remove `work/` contents (keep `.gitkeep`) |
| `make build` | `uv build → dist/` |

### `work/`

Temporary output directory — gitignored except `.gitkeep`:

- `.coverage` — coverage data file
- `report.md` — last quality report (CI mode only)
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` — tool caches

---

## 7. Quality pipeline

Run the full pipeline locally:

```bash
make check
```

Run in CI mode (same checks, writes `work/report.md`):

```bash
make ci
```

The pipeline runs these checks in order:

| # | Check | Tool |
|---|-------|------|
| 1 | format | `ruff format --check` |
| 2 | ruff | `ruff check` |
| 3 | flake8 | `flake8` |
| 4 | metrics | Built-in (CC ≤ 10, logical lines ≤ 900) |
| 5 | security-code | `bandit -r src` |
| 6 | security-deps | `pip-audit` |
| 7 | tests | `pytest --cov-fail-under=100` |
| 8 | typecheck | `mypy --strict` |

### Run a single check

```bash
yggtools run typecheck
yggtools run tests
yggtools run format
```

### Thresholds (configurable in `pyproject.toml`)

```toml
[tool.yggtools.code_metrics]
max_cyclomatic_complexity = 10   # per function
max_module_logical_lines = 900   # per .py file
```

Raise or lower these thresholds in the project's `pyproject.toml` at any
time. The pipeline reads the file at runtime.

### Auto-format before committing

```bash
make format
make check
git add -A && git commit -m "feat: …"
```

---

## 8. CI workflows

When `init-repo` or `init` runs without `--no-git`, it writes
`.github/workflows/ci.yml` and `.gitlab-ci.yml`.

### GitHub Actions

Triggered on push and pull-request to `main`/`master`. Runs `make ci` on
the configured Python version. Uploads `work/report.md` as an artifact
after every run, even on failure.

Push your project to GitHub and CI activates automatically:

```bash
git remote add origin https://github.com/yourname/my-lib.git
git push -u origin main
```

### GitLab CI

`.gitlab-ci.yml` runs the same `make ci` pipeline on every push.

---

## 9. Publishing a package

### Build

```bash
make build         # uv build → dist/
```

### Publish to PyPI

```bash
uv run twine upload dist/*
```

For PyPI **Trusted Publishing** (OIDC, no token required), configure your
publisher on [pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
before the first upload.

---

## 10. Typical day-to-day workflow

### Starting a new project

#### With global install

```bash
# Install once
uv tool install yggtools

# Scaffold
yggtools init-repo my-lib --python 3.13
cd my-lib
make check
```

#### Without global install (team / CI context)

```bash
# Create project with uv
uv init --lib my-lib
cd my-lib

# Scaffold with uvx (no permanent install needed)
uvx yggtools init --python 3.13
make check
```

### Daily development loop

```bash
# Write code in src/my_lib/, tests in tests/

# Auto-format
make format

# Fast feedback — tests only
make test

# Full pipeline before committing
make check

# Commit
git add -A
git commit -m "feat: add my feature"
git push
```

### Releasing a new version

```bash
# 1. Bump the version in pyproject.toml
# 2. Run the full pipeline
make check

# 3. Commit, tag, push — CI runs automatically
git add pyproject.toml
git commit -m "chore: release v1.1.0"
git tag v1.1.0
git push origin main --tags
```

### Updating yggtools in a scaffolded project

```bash
uv upgrade yggtools
make check
```

After an upgrade, scaffolded projects automatically benefit from updated
quality checks — no project files need to be modified.

### Updating yggtools itself (global tool)

```bash
uv tool upgrade yggtools
```
