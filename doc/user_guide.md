# yggtools — User Guide

**Version:** 1.0.0
**Date:** 2026-06-15

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
- **`uv init --lib` first.** The first init step delegates to `uv init --lib`,
  which creates the canonical `src/` layout and keeps the project structure
  in sync with uv conventions.
- **All Python, no shell.** The quality pipeline is implemented in Python
  (Registry + Strategy pattern), making it testable and type-checked.

`yggtools` is itself a `uv` tool, so it never pollutes your project's
virtual environment.

---

## 2. Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.12 | Managed by uv |
| [uv](https://docs.astral.sh/uv/) | 0.5 | Required at runtime |
| git | 2.30 | Optional — used by `init-repo` for the initial commit |

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

### Create a new library called `my-lib`

```bash
yggtools init-repo my-lib
```

This:
1. Runs `uv init --lib my-lib` to create the `src/` layout.
2. Adds `yggtools` and all quality tools as dev dependencies.
3. Patches `pyproject.toml` with ruff, mypy, pytest, and yggtools config.
4. Writes a `Makefile` that delegates to `yggtools run`.
5. Creates `tests/`, `work/`, and `.github/workflows/ci.yml`.
6. Creates a first git commit.

Resulting structure:

```
my-lib/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── .python-version
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

Then run the quality pipeline:

```bash
cd my-lib
make check
```

### Preview without writing anything

```bash
yggtools init-repo my-lib --dry-run
```

---

## 5. Command reference

### `yggtools init-repo`

```
yggtools init-repo PROJECT_NAME [OPTIONS]
```

Scaffold a new Python package from scratch.

| Option | Default | Description |
|--------|---------|-------------|
| `--python VERSION` | `3.12` | Target Python version |
| `--no-git` | off | Skip git commit (and CI workflow generation) |
| `--dry-run` | off | Print planned actions without writing |
| `--parent-dir PATH` | current directory | Where to create the project |

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
| 5 | create `tests/` | `__init__.py` and `conftest.py` |
| 6 | create `work/` | `.gitkeep` |
| 7 | write CI | `.github/workflows/ci.yml` (skipped with `--no-git`) |
| 8 | git commit | Initial commit |

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
| `docstrings` | built-in AST docstring scanner |
| `typecheck` | `mypy --strict` |
| `metrics` | built-in CC and logical-line counter |
| `security-code` | `bandit -r src` |
| `security-deps` | `pip-audit` on runtime deps |
| `tests` | `pytest --cov-fail-under=100` |

---

## 6. Project structure generated

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

### `Makefile`

All targets delegate to `yggtools run` or standard `uv` commands.

| Target | What it does |
|--------|-------------|
| `make check` | `uv run yggtools run --all` |
| `make ci` | `uv run yggtools run --all --ci` |
| `make format` | `uv run ruff format src tests` |
| `make test` | `uv run pytest` |
| `make clean` | Remove `work/` contents (keep `.gitkeep`) |
| `make build` | `uv build` |
| `make check-dist` | `uv run twine check dist/*` |
| `make publish` | `uv run twine upload dist/*` |

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
| 1 | Format | `ruff format --check` |
| 2 | Lint (ruff) | `ruff check` |
| 3 | Lint (flake8) | `flake8` |
| 4 | Docstrings | Built-in AST scanner |
| 5 | Type check | `mypy --strict` |
| 6 | Metrics | Built-in (CC ≤ 10, logical lines ≤ 900) |
| 7 | Security (code) | `bandit -r src` |
| 8 | Security (deps) | `pip-audit` |
| 9 | Tests | `pytest --cov-fail-under=100` |

### Run only a single check

```bash
yggtools run typecheck
yggtools run tests
yggtools run format
```

### Auto-format before committing

```bash
uv run ruff format src tests
make check
```

---

## 8. CI workflows

When `yggtools init-repo` runs without `--no-git`, it writes
`.github/workflows/ci.yml`.

### GitHub Actions

Triggered on push and pull-request to `main`/`master`. Runs `make ci` on
Python 3.12 and 3.13 (`fail-fast: false`). Uploads `work/report.md` as an
artifact after every run, even on failure.

Push your project to GitHub and CI activates automatically:

```bash
git remote add origin https://github.com/yourname/my-lib.git
git push -u origin main
```

---

## 9. Publishing a package

### Build and validate

```bash
make build         # uv build → dist/
make check-dist    # twine check dist/*
```

### Publish to PyPI

```bash
make publish       # twine upload dist/*
```

For PyPI **Trusted Publishing** (OIDC, no token required), configure your
publisher on [pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
before the first upload, then use the standard `publish.yml` workflow
pattern.

---

## 10. Typical day-to-day workflow

### Starting a new project

```bash
# 1. Install yggtools once, globally
uv tool install yggtools

# 2. Scaffold the project
yggtools init-repo my-lib --python 3.13
cd my-lib

# 3. Verify the pipeline passes on a clean slate
make check

# 4. Open in your editor and start coding
code .
```

### Daily development loop

```bash
# Write code in src/my_lib/, tests in tests/

# Auto-format
uv run ruff format src tests

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
# 2. Update CHANGELOG.md
# 3. Run the full pipeline
make check

# 4. Commit, tag, push — CI publishes to PyPI automatically
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v1.1.0"
git tag v1.1.0
git push origin main
git push origin v1.1.0
```

### Updating yggtools itself

```bash
uv tool upgrade yggtools
```

After an upgrade, scaffolded projects automatically benefit from the updated
quality checks the next time `make check` runs — no files need to be copied
or updated in the project.
