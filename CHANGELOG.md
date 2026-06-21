# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-06-15

Complete architectural rebaseline. See
[ADR-001](doc/ADR-001-rebaseline.md) for the full rationale.

### Changed

- **Package renamed** from `uvforge` to `yggtools` (CLI command and PyPI
  name).
- CLI command `init` renamed to `init-repo`. First step now delegates to
  `uv init --lib`, which creates the canonical `src/` layout, `.gitignore`,
  `.python-version`, and `README.md`.
- Quality tooling moved entirely into `yggtools`: scaffolded projects no
  longer contain a `scripts/` directory. The generated `Makefile` calls
  `uv run yggtools run --all` instead of local shell scripts.
- Shell-based pipeline (`check.sh`, `generate_report.py`, sentinel `.exit`
  files) replaced by a Python Registry + Strategy architecture inside
  `yggtools.quality`.
- Flat module layout replaced by domain sub-packages:
  `yggtools.repo_init` and `yggtools.quality`.

### Added

- `yggtools run [CHECK]` command to run quality checks on any project.
- `yggtools run --all` runs every registered check; `--ci` additionally
  writes `work/report.md`.
- Registry pattern (`quality/runner.py`): new checks are added by
  implementing one function and decorating it with `@register("name")`.
- Pipeline pattern (`repo_init/pipeline.py`): `init-repo` steps are
  independently testable and listed in one ordered `STEPS` list.
- Strategy pattern: each check in `quality/checks/` is a standalone module
  exporting one `CheckFn`-protocol function.
- Adapter `uv.py`: all `uv` and `git` subprocess calls in one place.
- `--dry-run` and `--no-git` options on `init-repo`.
- GitHub Actions CI workflow (`.github/workflows/ci.yml`): quality pipeline
  on push and pull-request to `main`/`master`, Python 3.12 and 3.13 matrix,
  uploads `work/report.md` as artifact.
- GitHub Actions publish workflow (`.github/workflows/publish.yml`):
  triggered on tag `v*.*.*`, quality gate then PyPI publish via OIDC
  Trusted Publishing (no secret required).

### Removed

- `scripts/` directory from scaffolded projects.
- Modules `init.py`, `check.py`, `scaffold.py`, `renderer.py`, `report.py`,
  `suppressions.py`, `models.py`, `uv_runner.py`.
- Embedded script templates (`templates/scripts/`).
- CLI commands `check` and `update`.

---

## [0.1.0] — 2026-06-12 (unreleased)

Initial implementation under the name `uvforge`.

### Added

- `uvforge init`: scaffold a new Python package with `pyproject.toml`,
  `Makefile`, `src/`, `tests/`, `scripts/`, `.python-version`, `.gitignore`,
  `README.md`, and optional git initialisation.
- Quality pipeline (`scripts/check.sh`) covering format, lint (ruff,
  flake8), docstrings, type checking (mypy), cyclomatic complexity, security
  (bandit, pip-audit), and tests (pytest with 100% coverage).
- `Makefile` targets: `check`, `ci`, `check-dist`, `publish`.
