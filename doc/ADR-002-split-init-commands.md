# ADR-002 — Split `init-repo` into `uv init --lib` + `yggtools init`

**Date:** 2026-06-20
**Status:** Accepted
**Author:** Antoine Barré

---

## Context

`yggtools init-repo PROJECT_NAME` currently does two things in one command:

1. Calls `uv init --lib PROJECT_NAME` to create the project directory and
   canonical `src/` layout.
2. Completes the scaffold (dev deps, `pyproject.toml` patches, `Makefile`,
   `tests/`, `work/`, CI, git commit).

This design has a circular dependency problem: to run step 1, `yggtools` must
be installed globally (`uv tool install yggtools`). Step 2 then adds `yggtools`
as a dev dependency of the new project (`uv add --dev yggtools`). The user ends
up installing `yggtools` twice: once globally to run `init-repo`, and once as a
project dev dependency so that `make check` works.

More importantly, a developer who only wants to scaffold a project is **forced
to install `yggtools` globally first**, even though `uv` itself is the natural
entry point for project creation.

The cleaner workflow separates the two responsibilities:

```bash
# Step 1 — pure uv, no yggtools required
uv init --lib my-lib
cd my-lib

# Step 2 — yggtools completes the scaffold in the current directory
yggtools init
```

`yggtools init` is now an **in-place** command: it operates on the current
directory, which must already be a valid `uv`-managed project (i.e., it must
contain `pyproject.toml`).

---

## Decision

1. **Add `yggtools init`** — a new CLI command that operates on the current
   directory. It performs steps 2–8 of the former `init-repo` pipeline:
   add dev deps, patch `pyproject.toml`, write `Makefile`, create `tests/`,
   `work/`, CI workflow, initial git commit.
   It also copies a `CLAUDE.md` into the project (see §CLAUDE.md propagation).

2. **Keep `yggtools init-repo NAME`** — retained as a convenience one-shot
   command for users who have `yggtools` installed globally. It now calls
   `uv init --lib NAME`, then `cd`s into the new directory and runs the same
   steps as `yggtools init`.

3. **`yggtools init` validates the context** — exits with code 1 and a clear
   message if `pyproject.toml` is absent in the current directory.

4. **`CLAUDE.md` propagation** — both `init` and `init-repo` write a
   `CLAUDE.md` into the project containing the coding standards (PEP rules,
   Google docstrings, SOLID, 100% coverage, cyclomatic complexity limit).

---

## Consequences

**Positive:**

- Users can run `uv init --lib my-lib && cd my-lib && yggtools init` without
  any prior global installation of `yggtools` if they install it as a dev dep
  first, or via `uvx yggtools init`.
- `uv init` is the canonical project-creation entry point; `yggtools init`
  is a complement, not a replacement.
- The two commands have clearly separated responsibilities.

**Negative:**

- Two-step workflow requires a `cd` between `uv init` and `yggtools init`.
- `yggtools init-repo` is now a thin wrapper; it must be kept in sync with
  `yggtools init`.

---

## Alternatives rejected

**Remove `init-repo` entirely** — breaks existing users who have `yggtools`
installed globally and rely on the one-shot command. Rejected.

**Keep `init-repo` as-is, document the two-step workaround** — does not solve
the circular dependency problem. Rejected.

**Make `init` auto-detect whether a `pyproject.toml` exists** and run `uv init`
if not — conflates two responsibilities in one command. Rejected.
