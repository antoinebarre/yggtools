# SRS — Software Requirements Specification

**Project:** yggtools
**Version:** 2.1
**Date:** 2026-06-21
**Author:** Antoine Barré
**Status:** Approved

---

## Table of contents

1. [Introduction](#1-introduction)
2. [General description](#2-general-description)
3. [Functional requirements](#3-functional-requirements)
4. [Non-functional requirements](#4-non-functional-requirements)
5. [System constraints](#5-system-constraints)
6. [Test requirements](#6-test-requirements)
7. [Glossary](#7-glossary)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for **yggtools**, a
command-line developer tool that scaffolds opinionated Python packages on
top of `uv` and provides a built-in quality pipeline accessible through a
`Makefile`.

### 1.2 Scope

yggtools covers:

- Initialising a new Python package (`yggtools init-repo`)
- Running quality checks on any project (`yggtools pipeline`, `yggtools run`)
- Inspecting and bumping package versions (`yggtools version`,
  `yggtools increase-version`)
- Generating CI workflow files for GitHub Actions

yggtools does not cover:

- Direct execution of underlying tools (ruff, mypy, pytest…) outside of the
  `run` command
- Management of PyPI secrets (user's responsibility)
- Creating git branches or managing remote workflows

### 1.3 Conventions

- **SHALL**: mandatory requirement
- **SHOULD**: recommended requirement
- **MAY**: optional requirement
- Requirement identifier: `REQ-<category>-<number>`

---

## 2. General description

### 2.1 Product perspective

yggtools is a developer tool (`dev tool`) installed globally via
`uv tool install yggtools`. It is added as a dev dependency in scaffolded
projects so that `make check` delegates to
`PYTHONPATH=src uv run python -m yggtools.cli pipeline`.

```
Developer
  │
  ├─ yggtools init-repo my-lib
  │       │
  │       ▼
  │  uv init --lib my-lib   (step 1, run by yggtools)
  │       │
  │       ▼
  │  my-lib/
  │  ├── Makefile  (calls: python -m yggtools.cli pipeline)
  │  ├── src/
  │  ├── tests/
  │  └── work/
  │
  └─ cd my-lib && make check
          │
          └─ PYTHONPATH=src uv run python -m yggtools.cli pipeline
```

### 2.2 Main functions

| ID | Function |
|----|----------|
| F-01 | Scaffold a Python package (`init-repo`) |
| F-02 | Patch `pyproject.toml` with quality tool configuration |
| F-03 | Generate a `Makefile` that delegates to `python -m yggtools.cli` |
| F-04 | Install dev dependencies via `uv add --dev` |
| F-05 | Run one or all quality checks on any project (`run`) |
| F-06 | Write JSON quality artifacts under `work/reports/` |
| F-07 | Generate GitHub Actions CI workflow |
| F-08 | Inspect package version artifacts |
| F-09 | Increase package version artifacts with SemVer levels |

### 2.3 User profile

Python developer (intermediate to expert), familiar with `uv`, modern
quality tools (ruff, mypy), and `make`-based workflows. Uses macOS, Linux,
or WSL.

### 2.4 Assumptions and dependencies

- `uv` ≥ 0.5 is installed and in `PATH`
- `git` is installed (unless `--no-git` is used)
- Python ≥ 3.12 is available in the uv environment

---

## 3. Functional requirements

### 3.1 `yggtools init-repo`

#### REQ-INIT-01

`yggtools init-repo` SHALL accept a mandatory `PROJECT_NAME` argument.

#### REQ-INIT-02

Step 1 SHALL call `uv init --lib PROJECT_NAME --python VERSION` in the
parent directory. This creates the `src/` layout, `.gitignore`,
`.python-version`, and `README.md`.

#### REQ-INIT-03

Step 2 SHALL call `uv add --dev` to install `yggtools` itself and all
required quality tools as dev dependencies of the new project.

#### REQ-INIT-04

Step 3 SHALL ensure the package layout exists. It SHALL create
`src/<package>/__init__.py` when missing, and SHALL add `__version__` when
the package initializer exists without one. The package name and version
SHALL be read from `[project].name` and `[project].version`.

#### REQ-INIT-05

Step 4 SHALL append the following sections to `pyproject.toml` if they are
absent: `[tool.pytest.ini_options]`, `[tool.coverage.run]`, `[tool.mypy]`,
`[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.lint.pydocstyle]`,
`[tool.flake8]`, `[tool.bandit]`, `[tool.yggtools.code_metrics]`.

#### REQ-INIT-06

Step 5 SHALL write a `Makefile` whose `check` and `ci` targets call
`PYTHONPATH=src uv run python -m yggtools.cli pipeline`.

#### REQ-INIT-07

Step 6 SHALL write `CLAUDE.md`.

#### REQ-INIT-08

Step 7 SHALL create `tests/__init__.py` and `tests/conftest.py`.

#### REQ-INIT-09

Step 8 SHALL create `work/.gitkeep`.

#### REQ-INIT-10

Step 9 SHALL generate CI workflow files unless `--no-git` is set.
The workflow SHALL run `make ci` on Python 3.12 and 3.13 with
`fail-fast: false`, and upload `work/reports/` as an artifact.

#### REQ-INIT-11

Step 10 SHALL create a git commit unless `--no-git` is set.

#### REQ-INIT-12

`yggtools init-repo` SHALL support `--dry-run`, which prints the planned
actions without executing them.

#### REQ-INIT-13

`yggtools init-repo` SHALL support `--no-git`, which skips the git commit
and the CI workflow generation.

#### REQ-INIT-14

`yggtools init-repo` SHALL support `--python VERSION` to set the target
Python version (default `3.12`).

#### REQ-INIT-15

`yggtools init-repo` SHALL exit with code `1` and print a clear error
message if `uv` is not found in `PATH`.

#### REQ-INIT-16

`yggtools init-repo` SHALL exit with code `1` and print a clear error
message if any pipeline step fails.

### 3.2 `yggtools pipeline`

#### REQ-PIPE-01

`yggtools pipeline` SHALL execute all staged quality checks in deterministic
order and print a Rich summary dashboard.

#### REQ-PIPE-02

`yggtools pipeline` SHALL always write per-check JSON artifacts and SHA-256
sidecars under `work/reports/`, plus a consolidated `pipeline.json`.

#### REQ-PIPE-03

`yggtools pipeline` SHALL exit with code `0` when every check passes, and
code `1` otherwise.

### 3.3 `yggtools run`

#### REQ-RUN-01

`yggtools run --all` SHALL execute every registered quality check in
registration order and print a PASS/FAIL summary.

#### REQ-RUN-02

`yggtools run CHECK_NAME` SHALL execute only the named check and exit with
code `1` if the check fails or the name is unknown.

#### REQ-RUN-03

`yggtools run --all --ci` SHALL be accepted for backward compatibility. The
`--ci` flag SHALL be a no-op because JSON artifacts are always written.

#### REQ-RUN-04

`yggtools run` SHALL exit with code `0` if all executed checks pass, or
code `1` if any check fails.

#### REQ-RUN-05

`yggtools run` SHALL support `--path PATH` to specify the project root
(default: current directory).

#### REQ-RUN-06

`yggtools run` without `--all` and without a check name SHALL exit with
code `1` and print a usage error.

### 3.4 Quality checks

#### REQ-CHECK-01 — Format

The `format` check SHALL run `uv run ruff format --check src tests` and
report the number of files that would be reformatted.

#### REQ-CHECK-02 — Lint (ruff)

The `ruff` check SHALL run `uv run ruff check src tests` and report the
number of errors.

#### REQ-CHECK-03 — Lint (flake8)

The `flake8` check SHALL run `uv run flake8 src tests` and report the
number of violations.

#### REQ-CHECK-04 — Version consistency

The `version-consistency` check SHALL compare `[project].version`,
`src/<package>/__init__.py::__version__`, and the editable local package
entry in `uv.lock`.

#### REQ-CHECK-05 — Type check

The `typecheck` check SHALL run `uv run mypy src tests` and report the
number of errors.

#### REQ-CHECK-06 — Metrics

The `metrics` check SHALL use the Python AST to measure cyclomatic
complexity and logical line count for every `.py` file in the configured
paths. Thresholds SHALL be read from `[tool.yggtools.code_metrics]` in
`pyproject.toml`.

#### REQ-CHECK-07 — Security (code)

The `security-code` check SHALL run `uv run bandit -r src` and report the
number of issues.

#### REQ-CHECK-08 — Security (deps)

The `security-deps` check SHALL export runtime dependencies with
`uv export --no-dev` and run `pip-audit`. If no runtime dependencies exist,
the check SHALL pass immediately.

#### REQ-CHECK-09 — Tests

The `tests` check SHALL run `uv run pytest` and report the summary line.

### 3.5 Version commands

#### REQ-VERSION-01

`yggtools version` SHALL list all managed package version artifacts and
their discovered versions.

#### REQ-VERSION-02

`yggtools version` SHALL exit with code `1` if a required version artifact
is missing or if versions diverge.

#### REQ-VERSION-03

`yggtools increase-version LEVEL` SHALL accept levels `1`, `2`, and `3`,
mapping to SemVer patch, minor, and major increments.

#### REQ-VERSION-04

`yggtools increase-version` SHALL update `pyproject.toml`,
`src/<package>/__init__.py`, and `uv.lock`, then run `uv lock`.

### 3.6 Registry

#### REQ-REG-01

Adding a new check SHALL require only: implementing a function that matches
the `CheckFn` protocol and decorating it with `@register("name")`. No
changes to the runner, CLI, or any other existing module SHALL be required.

#### REQ-REG-02

`registered_checks()` SHALL return check names in registration order.

---

## 4. Non-functional requirements

### 4.1 Performance

#### REQ-PERF-01

`yggtools init-repo` SHALL complete in under 120 seconds on a standard
internet connection (excluding uv dependency download time).

#### REQ-PERF-02

`yggtools pipeline` on the yggtools repository itself SHALL complete in
under 60 seconds.

### 4.2 Reliability

#### REQ-REL-01

Each quality check function SHALL not raise exceptions. Failures SHALL be
captured and returned as a `CheckResult` with `passed=False`.

#### REQ-REL-02

If a pipeline step in `init-repo` fails, yggtools SHALL exit with code `1`
and print the step name and error detail.

### 4.3 Usability

#### REQ-USE-01

Terminal output SHALL use colours to distinguish success (green) and
failure (red).

#### REQ-USE-02

`yggtools --help` and `yggtools <command> --help` SHALL display clear help
with all options listed.

### 4.4 Maintainability

#### REQ-MAIN-01

yggtools SHALL maintain 100% test coverage (branches included).

#### REQ-MAIN-02

All public functions and classes SHALL have Google-style docstrings.

#### REQ-MAIN-03

No module SHALL exceed 500 lines.

#### REQ-MAIN-04

No function SHALL have a cyclomatic complexity above 10.

### 4.5 Portability

#### REQ-PORT-01

yggtools SHALL run on macOS (≥ 13) and Linux (Ubuntu ≥ 22.04).

### 4.6 yggtools own CI

#### REQ-DEVCI-01

The yggtools repository SHALL have a GitHub Actions workflow running
`make ci` on every push and pull-request to `main`/`master`.

#### REQ-DEVCI-02

The CI workflow SHALL test on Python 3.12 and 3.13 with `fail-fast: false`.

#### REQ-DEVCI-03

The CI workflow SHALL upload `work/reports/` as an artifact after every
run, even on failure.

#### REQ-DEVCI-04

The yggtools repository SHALL have a publish workflow triggered on tag
`v*.*.*`, using PyPI Trusted Publishing (OIDC) without any explicit secret.

---

## 5. System constraints

| Component | Minimum version |
|-----------|----------------|
| Python | 3.12 |
| uv | 0.5 |
| git | 2.30 |

yggtools SHALL install via `uv tool install yggtools` without requiring
administrator rights.

---

## 6. Test requirements

#### REQ-TEST-01

Every module in `src/yggtools/` SHALL have unit tests with 100% branch
coverage.

#### REQ-TEST-02

Each pipeline step in `repo_init/steps.py` SHALL be tested in isolation
using a `RepoContext` built from `tmp_path`.

#### REQ-TEST-03

All `uv` and `git` subprocess calls SHALL be mocked in unit tests.

#### REQ-TEST-04

The Registry SHALL be tested: `@register`, `run_one`, `run_all`,
`registered_checks`.

#### REQ-TEST-05

Each check function SHALL be tested with mocked subprocess output covering
pass and fail paths.

#### REQ-TEST-06

Test function docstrings SHALL use the prefix `Requirement:` to state what
requirement is being verified.

---

## 7. Glossary

| Term | Definition |
|------|------------|
| **dev tool** | Tool installed globally for the developer, not present in project dependencies |
| **scaffold** | Creation of directory and file structure for a new project |
| **quality pipeline** | Ordered sequence of automated checks (format, lint, type, test, security) |
| **work/** | Temporary output directory (gitignored except `.gitkeep`) |
| **Registry** | Dict mapping check names to `CheckFn` functions; populated via `@register` |
| **Strategy** | Each check module exports exactly one `CheckFn` function |
| **Pipeline** | Ordered list of `PipelineStep` objects executed by `run_pipeline` |
| **uv** | Python package and environment manager developed by Astral |
| **hatchling** | Modern Python build backend, used by default with uv |
| **CheckFn** | Protocol: `(project_dir: Path) -> CheckResult` |
| **RepoContext** | Frozen dataclass holding all `init-repo` inputs |
