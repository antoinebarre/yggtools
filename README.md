# yggtools

`yggtools` is a CLI dev tool that scaffolds opinionated Python packages on
top of [uv](https://docs.astral.sh/uv/). It sets up a complete project in
one command and provides a built-in quality pipeline you run with
`make check`.

## Install

```bash
uv tool install yggtools
```

## Quick start

```bash
# Scaffold a new library
yggtools init-repo my-lib

# Run the quality pipeline
cd my-lib
make check
```

## Commands

| Command | Description |
|---------|-------------|
| `yggtools init-repo NAME` | Scaffold a new Python package |
| `yggtools init` | Complete an existing uv project in place |
| `yggtools reset` | Restore yggtools-generated AI, CI, and Makefile files |
| `yggtools pipeline` | Run the full staged quality pipeline |
| `yggtools run [CHECK]` | Run quality checks on the current project |
| `yggtools version` | List versions found in package artifacts |
| `yggtools increase-version LEVEL` | Bump patch/minor/major versions |

## Quality checks

| Check | Tool |
|-------|------|
| Format | `ruff format --check` |
| Lint (ruff) | `ruff check` |
| Lint (flake8) | `flake8` |
| Version consistency | `pyproject.toml`, `__init__.py`, `uv.lock` |
| Type check | `mypy --strict` |
| Metrics | built-in CC + line-count |
| Security (code) | `bandit` |
| Security (deps) | `pip-audit` |
| Tests | `pytest --cov-fail-under=100` |

## Documentation

- [User guide](doc/user_guide.md)
- [Architecture Decision Record — rebaseline](doc/ADR-001-rebaseline.md)
- [Software Requirements Specification](doc/SRS.md)
- [Software Design Document](doc/SDD.md)

## License

MIT
