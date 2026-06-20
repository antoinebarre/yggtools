# yggtools — Design overview

**Version:** 2.0
**Date:** 2026-06-15
**Author:** Antoine Barré

---

## 1. Vision

`yggtools` is a developer tool that sits on top of `uv` and provides two
things:

1. **`init-repo`** — a one-command project scaffold that runs `uv init --lib`
   and then adds everything a quality-focused Python package needs.
2. **`run`** — a built-in quality pipeline that any scaffolded project calls
   via `make check` (backed by `uv run yggtools run --all`).

The key design principle: **no scripts are copied into the scaffolded
project**. Quality tooling lives in `yggtools` and is updated by upgrading
the tool, not by patching files in every project.

---

## 2. Commands

| Command | Description |
|---------|-------------|
| `yggtools init-repo NAME` | Scaffold a new Python package |
| `yggtools run [CHECK]` | Run a named quality check |
| `yggtools run --all` | Run all registered quality checks |

---

## 3. Architecture

```
src/yggtools/
├── cli.py                 # Typer: init-repo, run
├── uv.py                  # Adapter: all uv/git subprocess calls
├── quality/
│   ├── runner.py          # Registry + CheckFn protocol
│   ├── report.py          # Markdown report writer
│   └── checks/            # One module per check, @register("name")
│       ├── format.py
│       ├── lint.py
│       ├── docstrings.py
│       ├── typecheck.py
│       ├── metrics.py
│       ├── security.py
│       └── tests.py
└── repo_init/
    ├── pipeline.py        # STEPS list + run_pipeline()
    ├── steps.py           # RepoContext, StepError, one fn per step
    └── templates/         # Jinja2 templates (package resource)
```

### Design patterns

| Pattern | Where | Benefit |
|---------|-------|---------|
| Registry | `quality/runner.py` | Add a check with one `@register("name")` |
| Strategy | `quality/checks/` | Each check is an isolated, testable function |
| Pipeline | `repo_init/pipeline.py` | Steps are reorderable, independently testable |
| Adapter | `uv.py` | All subprocess calls in one place; easy to mock |

---

## 4. `init-repo` pipeline steps

| # | Step | What it does |
|---|------|-------------|
| 1 | `uv init --lib` | Delegates canonical src layout to uv |
| 2 | add dev deps | `uv add --dev yggtools <quality tools>` |
| 3 | patch pyproject | Appends tool config sections |
| 4 | write Makefile | Renders `Makefile.tmpl` |
| 5 | create `tests/` | `__init__.py` + `conftest.py` |
| 6 | create `work/` | `.gitkeep` |
| 7 | write CI | `.github/workflows/ci.yml` |
| 8 | git commit | Initial commit |

---

## 5. Structure generated in the target project

```
my-lib/
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore              (from uv init)
├── .python-version         (from uv init)
├── Makefile                (delegates to yggtools run)
├── README.md               (from uv init)
├── pyproject.toml          (uv init + yggtools patches)
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

Notable differences from the old design:

- No `scripts/` directory.
- No `doc/` or `generate_report.py` in the project.
- `Makefile` calls `uv run yggtools run --all`, not `bash scripts/check.sh`.

---

## 6. Quality pipeline

`make check` → `uv run yggtools run --all`

| # | Check | Tool |
|---|-------|------|
| 1 | format | `ruff format --check` |
| 2 | ruff | `ruff check` |
| 3 | flake8 | `flake8` |
| 4 | docstrings | `flake8 --select=D` |
| 5 | typecheck | `mypy --strict` |
| 6 | metrics | AST (pure Python) |
| 7 | security-code | `bandit` |
| 8 | security-deps | `pip-audit` |
| 9 | tests | `pytest --cov-fail-under=100` |

`make ci` → `uv run yggtools run --all --ci` (same + writes `work/report.md`)

---

## 7. Dependencies of yggtools itself

| Package | Role |
|---------|------|
| `typer` | CLI with typed arguments and auto-completion |
| `rich` | Coloured terminal output |
| `jinja2` | Template rendering for Makefile, CI workflow, conftest |

yggtools does NOT depend on the tools it runs (ruff, mypy, etc.). Those are
injected into the target project as dev dependencies.

---

## 8. Development phases

### Phase 1 — Foundation (done)

- [x] `yggtools init-repo` pipeline (8 steps)
- [x] `yggtools run` with Registry + Strategy quality pipeline
- [x] All 9 checks implemented
- [x] 82 unit tests, 100% coverage
- [x] GitHub Actions CI and publish workflows
- [x] PyPI publication as `yggtools`

### Phase 2 — Planned

- [ ] `yggtools run --list` to enumerate registered checks
- [ ] `yggtools run --check-project` to audit project conformance
- [ ] GitLab CI template generation
- [ ] Shell auto-completion
