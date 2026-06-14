# ADR-001 — Rebaseline: pipeline-based init-repo, quality as first-class commands

**Date:** 2026-06-14  
**Status:** Accepted  
**Author:** Antoine Barré

---

## Context

The initial implementation of `yggtools` accumulated several structural
problems:

1. **Scripts copied into scaffolded projects.** `check.sh`,
   `check_docstrings.py`, `code_metrics.py`, `generate_report.py`,
   `publish.sh`, and `security_deps.sh` were embedded as templates and
   copied into the target project's `scripts/` directory. This means every
   scaffolded project carries a frozen copy of the quality tooling. When
   `yggtools` evolves, those copies become stale and diverge silently.

2. **Shell orchestration.** `check.sh` drove the entire quality pipeline
   via bash: log files, sentinel `.exit` files, string parsing, colour
   escape codes. Bash is hard to test, non-portable, and cannot use Python
   data structures. It was 143 lines of glue that belongs in Python.

3. **`uv init` not used.** The scaffolding duplicated what `uv init --lib`
   already does (src layout, `.python-version`, `.gitignore`, `README.md`,
   first git commit). Running `uv init --lib` first and adding on top is
   simpler and guarantees compatibility with uv conventions.

4. **Flat module layout.** All logic lived in `init.py`, `check.py`,
   `scaffold.py`, `renderer.py`, `report.py`, `suppressions.py` at the
   package root. No grouping by domain, making future commands hard to add
   without polluting the top level.

5. **CLI command named `init`.** This is too generic. `init-repo` is
   precise and leaves room for future commands (`init-module`, etc.).

---

## Decision

### 1. `uv init --lib` is always the first step

`yggtools init-repo` calls `uv init --lib <name> --python <version>` as
step one. This delegates the canonical src layout, packaging metadata,
`.python-version`, `.gitignore`, `README.md`, and initial git commit to uv.
`yggtools` only adds what uv does not provide.

### 2. No scripts in the scaffolded project

The target project has no `scripts/` directory. The `Makefile` delegates
entirely to `yggtools` and `uv`:

```makefile
check:
    uv run yggtools run --all

test:
    uv run pytest

format:
    uv run ruff format src tests
```

Quality tooling lives in `yggtools` and is updated by upgrading the tool,
not by copying files into every project.

### 3. `init-repo` is a named pipeline of steps

Each step in `repo_init/steps.py` is a standalone function with a single
responsibility. `repo_init/pipeline.py` defines the ordered sequence and
executes it. Adding or reordering steps requires changing only the pipeline
list, not a monolithic function.

Steps:
1. `uv_init` — calls `uv init --lib`
2. `add_dev_deps` — calls `uv add --dev yggtools <quality tools>`
3. `patch_pyproject` — appends `[tool.ruff]`, `[tool.mypy]`,
   `[tool.yggtools]` sections
4. `write_makefile` — renders and writes `Makefile`
5. `write_tests_dir` — creates `tests/__init__.py` and `conftest.py`
6. `write_work_dir` — creates `work/.gitkeep`
7. `write_ci` — renders and writes `.github/workflows/ci.yml` and
   `.gitlab-ci.yml` (skipped when `--no-git`)
8. `git_commit` — creates the final commit

### 4. Quality checks use Registry + Strategy

`quality/runner.py` maintains a registry of check functions. Each check in
`quality/checks/` is a module that exports a single function matching the
`CheckFn` protocol. Registering a new check requires only implementing that
function and adding it to the registry — the runner and CLI need no changes.

### 5. Package sub-structure

```
src/yggtools/
├── cli.py              # typer: init-repo, run
├── repo_init/
│   ├── pipeline.py     # ordered step list + execute()
│   ├── steps.py        # one function per step
│   └── templates/      # Makefile.tmpl, ci ymls, pyproject patch
├── quality/
│   ├── runner.py       # Registry, run_all(), run_one()
│   ├── report.py       # work/report.md writer
│   └── checks/
│       ├── format.py
│       ├── lint.py
│       ├── docstrings.py
│       ├── typecheck.py
│       ├── metrics.py
│       ├── security.py
│       └── tests.py
└── uv.py               # Adapter: uv and git subprocess calls
```

### 6. Obsolete modules deleted

`init.py`, `check.py`, `scaffold.py`, `renderer.py`, `report.py`,
`suppressions.py`, `models.py`, `uv_runner.py` are replaced by the new
sub-packages. All embedded scripts (`templates/scripts/`) are deleted.

---

## Consequences

**Positive:**
- Scaffolded projects have no copied tooling to maintain.
- Quality pipeline is fully in Python: testable, type-checked, portable.
- New checks or init steps can be added without modifying existing code.
- `uv init --lib` keeps the project structure in sync with uv conventions.

**Negative:**
- Significant rewrite — all existing tests must be replaced.
- `yggtools` must be available as a dev dependency in every scaffolded
  project (already the case, just made explicit).
- Projects scaffolded with the old `init` command are incompatible and
  must be migrated manually.

---

## Alternatives rejected

- **Keep shell scripts, refactor Python around them:** shell remains
  untestable and non-portable. Rejected.
- **Keep scripts in `scripts/` but generate them from yggtools at
  `make check` time:** adds complexity without fixing the staleness
  problem. Rejected.
- **Use `uv init` without `--lib`:** produces an application layout
  (`main.py`), not a package layout. Rejected.
