# yggtools — User Guide

**Version:** 1.0.0  
**Date:** 2026-06-14

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

`yggtools` is a CLI tool that scaffolds opinionated Python packages managed
by [uv](https://docs.astral.sh/uv/). It generates a complete, ready-to-run
project with:

- `src/` layout with a properly installed editable package
- pre-configured linting, type checking, security scanning, and tests
- a `Makefile` pipeline (`make check`, `make ci`)
- CI workflows for GitHub Actions and GitLab CI
- a publish script ready for PyPI via Trusted Publishing

It is itself installed as a `uv` tool, so it never pollutes your project's
virtual environment.

---

## 2. Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Python | 3.12 | Managed by uv |
| [uv](https://docs.astral.sh/uv/) | 0.4 | Required at runtime |
| git | any | Optional — used by `yggtools init` for the first commit |

Install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## 3. Installation

### Install as a uv tool (recommended)

`uv tool install` installs `yggtools` in an isolated environment and exposes
the `yggtools` command globally. This is the correct way to use it — it never
conflicts with your project dependencies.

```bash
uv tool install yggtools
```

Verify the installation:

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

### Check installed tools

```bash
uv tool list
```

### Pin a specific version

```bash
uv tool install yggtools==1.0.0
```

---

## 4. Quick start

### Create a new library called `my-lib`

```bash
yggtools init my-lib
```

This creates a `my-lib/` directory in the current working directory,
initialises a git repository, and runs `uv sync` to install all dev
dependencies.

```
my-lib/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitlab-ci.yml
├── .gitignore
├── .python-version
├── Makefile
├── README.md
├── pyproject.toml
├── scripts/
│   ├── check.sh
│   ├── check_docstrings.py
│   ├── code_metrics.py
│   ├── generate_report.py
│   ├── publish.sh
│   └── security_deps.sh
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

### Initialise in the current directory

If you are already inside the project directory:

```bash
mkdir my-lib && cd my-lib
yggtools init
```

`yggtools init` without a name argument uses the current directory name as
the project name.

---

## 5. Command reference

### `yggtools init`

```
yggtools init [PROJECT_NAME] [OPTIONS]
```

Scaffold a new Python package.

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `PROJECT_NAME` | current directory name | Name of the project (used for the directory and `pyproject.toml`) |
| `--python VERSION` | `3.12` | Target Python version |
| `--no-git` | off | Skip `git init` and first commit |
| `--force` | off | Overwrite an existing project without prompting |
| `--dry-run` | off | Print what would be created without writing anything |

**Examples:**

```bash
# Default — Python 3.12, with git
yggtools init my-lib

# Target Python 3.13
yggtools init my-lib --python 3.13

# Skip git initialisation (no .github/ or .gitlab-ci.yml generated)
yggtools init my-lib --no-git

# Preview what would be created
yggtools init my-lib --dry-run

# Overwrite an existing project
yggtools init my-lib --force

# Initialise in the current directory with Python 3.13
cd my-lib
yggtools init --python 3.13
```

**What `--dry-run` prints:**

```
[dry-run] Would create:
  would create  pyproject.toml
  would create  Makefile
  would create  .gitignore
  would create  README.md
  would create  src/my_lib/__init__.py
  would create  src/my_lib/py.typed
  would create  tests/__init__.py
  would create  tests/conftest.py
  would create  work/.gitkeep
  would create  scripts/check.sh
  would create  scripts/check_docstrings.py
  would create  scripts/code_metrics.py
  would create  scripts/generate_report.py
  would create  scripts/publish.sh
  would create  scripts/security_deps.sh
  would create  .github/workflows/ci.yml
  would create  .gitlab-ci.yml
```

---

### `yggtools check`

```
yggtools check [PATH]
```

Audit a project directory for structural conformance. Checks that required
directories, scripts, Makefile targets, and dev dependencies are in place.
Exits with code `1` if any check fails.

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH` | current directory | Project directory to audit |

**Examples:**

```bash
# Audit the current directory
yggtools check

# Audit a specific project
yggtools check ~/projects/my-lib
```

**Example output:**

```
          yggtools check — /home/user/my-lib
┌──────────────────────┬────────┬─────────────────────────┐
│ Check                │ Status │ Detail                  │
├──────────────────────┼────────┼─────────────────────────┤
│ src/my_lib/          │  PASS  │                         │
│ tests/               │  PASS  │                         │
│ scripts/check.sh     │  PASS  │                         │
│ Makefile             │  PASS  │                         │
│ dev dependencies     │  PASS  │                         │
└──────────────────────┴────────┴─────────────────────────┘

All checks passed.
```

---

## 6. Project structure generated

### `pyproject.toml`

Pre-configured with:
- `hatchling` build backend
- `src/` layout (`packages = ["src/my_lib"]`)
- pytest with 100 % coverage enforcement (`--cov-fail-under=100`)
- mypy in strict mode
- ruff with all rules enabled, line length 79
- flake8 with max complexity 10 and Google docstring convention
- bandit security scanner
- dev dependency group with all quality tools

### `Makefile`

| Target | What it does |
|--------|-------------|
| `make format` | Auto-format with ruff |
| `make lint` | Lint with ruff |
| `make flake8` | Lint with flake8 |
| `make docstrings` | Check Google-style docstrings |
| `make typecheck` | mypy strict type checking |
| `make metrics` | Cyclomatic complexity and line count |
| `make security` | bandit (code) + pip-audit (deps) |
| `make test` | pytest with coverage |
| `make check` | Full pipeline (local mode, with report) |
| `make ci` | Full pipeline (CI mode) |
| `make build` | Build wheel and sdist |
| `make check-dist` | Validate the built distribution |
| `make publish` | Publish to PyPI |

### `scripts/`

| Script | Purpose |
|--------|---------|
| `check.sh` | Orchestrates the full quality pipeline |
| `check_docstrings.py` | Verifies Google-style docstrings on all modules |
| `code_metrics.py` | Measures cyclomatic complexity and logical line counts |
| `generate_report.py` | Writes `work/report.md` after each pipeline run |
| `publish.sh` | Wraps `uv build` and `twine` for PyPI publishing |
| `security_deps.sh` | Runs `pip-audit` on runtime dependencies |

### `work/`

Temporary output directory (gitignored except `.gitkeep`):
- `.coverage` — coverage data
- `report.md` — last quality report
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` — tool caches

---

## 7. Quality pipeline

Run the full pipeline locally:

```bash
make check
```

Run in CI mode (same checks, no interactive output):

```bash
make ci
```

The pipeline runs these checks in order:

| # | Check | Tool |
|---|-------|------|
| 1 | Format | `ruff format --check` |
| 2 | Lint | `ruff check` |
| 3 | Flake8 | `flake8` |
| 4 | Docstrings | `check_docstrings.py` |
| 5 | Type check | `mypy --strict` |
| 6 | Metrics | `code_metrics.py` (CC ≤ 10, lines ≤ 900) |
| 7 | Security (code) | `bandit -r src` |
| 8 | Security (deps) | `pip-audit` |
| 9 | Tests | `pytest --cov-fail-under=100` |

A Markdown report is written to `work/report.md` after each run.

### Auto-format before committing

```bash
make format   # auto-fix formatting
make check    # verify everything passes
```

### Run only tests

```bash
make test
```

### Run only type checking

```bash
make typecheck
```

---

## 8. CI workflows

When `yggtools init` is run without `--no-git`, it generates two CI
workflow files.

### GitHub Actions (`.github/workflows/ci.yml`)

Triggered on push and pull-request to `main`/`master`. Runs `make ci` on
a matrix of Python 3.12 and 3.13. Uploads `work/report.md` as an artifact
even on failure.

Push your project to GitHub and CI activates automatically:

```bash
git remote add origin https://github.com/yourname/my-lib.git
git push -u origin main
```

### GitLab CI (`.gitlab-ci.yml`)

Same coverage: two jobs (`quality:3.12`, `quality:3.13`) using
`python:3.12-slim` and `python:3.13-slim` Docker images. Artifacts kept
for 30 days.

Push to GitLab:

```bash
git remote add origin https://gitlab.com/yourname/my-lib.git
git push -u origin main
```

---

## 9. Publishing a package

### Build and validate

```bash
make build         # creates dist/my_lib-*.whl and dist/my_lib-*.tar.gz
make check-dist    # runs twine check on the built files
```

### Publish to PyPI

The generated `publish.sh` script wraps `uv build` and `twine upload`.

```bash
make publish
```

For PyPI Trusted Publishing (OIDC, no token needed), configure your
publisher on [pypi.org/manage/account/publishing/](https://pypi.org/manage/account/publishing/)
before the first upload.

---

## 10. Typical day-to-day workflow

### Starting a new project

```bash
# 1. Install yggtools once, globally
uv tool install yggtools

# 2. Scaffold the project
yggtools init my-lib --python 3.13
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
make format

# Run tests only (fast feedback)
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
# 1. Bump the version in pyproject.toml and src/my_lib/__init__.py
# 2. Update CHANGELOG.md
# 3. Run the full pipeline
make check

# 4. Commit, tag, push — CI publishes to PyPI automatically
git add pyproject.toml src/my_lib/__init__.py CHANGELOG.md
git commit -m "chore: release v1.1.0"
git tag v1.1.0
git push origin main
git push origin v1.1.0
```

### Auditing an existing project

```bash
yggtools check ~/projects/legacy-lib
```

### Updating yggtools itself

```bash
uv tool upgrade yggtools
```
