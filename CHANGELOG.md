# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-06-14

### Changed

- **Package renamed** from `uvforge` to `yggtools` to consolidate all
  developer tooling under a single namespace.
- CLI command renamed from `uvforge` to `yggtools`.
- All internal Python imports updated from `uvforge.*` to `yggtools.*`.

### Added

- GitHub Actions CI workflow (`.github/workflows/ci.yml`): quality pipeline
  on push and pull-request targeting `main`/`master`, matrix Python 3.12 and
  3.13, uploads `work/report.md` as artifact.
- GitHub Actions publish workflow (`.github/workflows/publish.yml`): triggered
  on tag `v*.*.*`, quality gate then PyPI publish via OIDC Trusted Publishing
  (no secret required).
- `uvforge init` now generates CI workflows for scaffolded projects:
  `.github/workflows/ci.yml` (GitHub Actions) and `.gitlab-ci.yml`
  (GitLab CI), both with Python matrix 3.12 + 3.13. Skipped when `--no-git`.
- Markdown quality report generation (`scripts/generate_report.py`) driven
  by the `mkforge` DSL, written to `work/report.md` after each pipeline run.
- Suppressions scanning (`src/yggtools/suppressions.py`): detects
  `# noqa`, `# type: ignore`, `# nosec`, and `# pragma: no cover` annotations
  across the source tree and includes them in the report.
- Sentinel files (`work/<check>.exit`) for inter-process result communication
  between `scripts/check.sh` and `scripts/generate_report.py`.

### Fixed

- PyPI name conflict: original name `uvforge` was already registered by
  another owner; renamed to `yggtools`.

---

## [0.1.0] — 2026-06-12 (unreleased)

Initial implementation under the name `uvforge`.

### Added

- `uvforge init`: scaffold a new Python package with `pyproject.toml`,
  `Makefile`, `src/`, `tests/`, `scripts/`, `.python-version`, `.gitignore`,
  `README.md`, and optional git initialisation.
- `uvforge check`: structural conformance audit reporting missing files,
  missing `__init__.py`, and non-executable scripts.
- Jinja2 template engine rendering all scaffolded files from embedded
  templates in `yggtools.templates`.
- Quality pipeline (`scripts/check.sh`) covering format, lint (ruff, flake8),
  docstrings, type checking (mypy), cyclomatic complexity, security (bandit,
  pip-audit), and tests (pytest with 100 % coverage).
- `Makefile` targets: `check`, `ci`, `check-dist`, `publish`.
