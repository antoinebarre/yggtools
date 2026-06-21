# ADR-004 — Add `yggtools increase-version` and version consistency lint

**Date:** 2026-06-20
**Status:** Accepted
**Author:** Antoine Barré

---

## Context

The package version currently appears in several artifacts that must stay
synchronized:

1. `pyproject.toml` — canonical distribution metadata:
   `[project].version`.
2. `src/<package>/__init__.py` — runtime package metadata:
   `__version__`.
3. `uv.lock` — locked package version for the current project entry,
   identified by `[project].name`.

Updating these files manually is error-prone.  A release can be built with one
version in `pyproject.toml`, imported with another version at runtime, and
locked with a stale version in `uv.lock`.

The project also needs a simple release command that maps directly to Semantic
Versioning without forcing users to remember which component is patch, minor,
or major.

---

## Decision

### Add `yggtools increase-version`

Add a new CLI command:

```bash
yggtools increase-version LEVEL
```

`LEVEL` is an integer from 1 to 3:

| Level | SemVer component | Example        | Meaning                        |
|-------|------------------|----------------|--------------------------------|
| 1     | patch            | `1.2.3 → 1.2.4` | Backward-compatible bug fix    |
| 2     | minor            | `1.2.3 → 1.3.0` | Backward-compatible feature    |
| 3     | major            | `1.2.3 → 2.0.0` | Breaking change                |

The command reads the current version from `pyproject.toml`, computes the next
SemVer version, then updates every managed artifact:

- `pyproject.toml`
- `src/<package>/__init__.py`
- `uv.lock`

After editing files, the command runs `uv lock` so the lockfile remains in the
format expected by uv.

### SemVer rules

`increase-version` only accepts stable `MAJOR.MINOR.PATCH` versions in its
first implementation.

Pre-releases, build metadata, calendar versions, and dynamic versions are
rejected with a clear error message.  They can be added later once the release
workflow needs them.

The increment rules are:

```text
level 1: major.minor.patch -> major.minor.(patch + 1)
level 2: major.minor.patch -> major.(minor + 1).0
level 3: major.minor.patch -> (major + 1).0.0
```

### Add `version-consistency` lint

Add a quality check named `version-consistency` to the Linters stage.

The check reads all managed version artifacts and fails when:

- a required version artifact is missing;
- two artifacts contain different versions;
- the lockfile has no package entry matching `[project].name`.

The check intentionally ignores dependency versions in `uv.lock`, including an
installed `yggtools` dependency when the command is executed inside another
package.

The check is pure Python and does not invoke external commands.  It emits
structured metadata listing each artifact, path, discovered version, and
missing artifact names.

### Add `yggtools version`

Add an inspection command:

```bash
yggtools version
```

The command lists every managed version artifact with its path and
discovered version.  It exits with code `1` when a required artifact is
missing or when versions diverge.  This command is intentionally backed by
the same artifact discovery logic as `version-consistency`, so release
checks and human inspection share one source of truth.

### Release workflow

The intended release flow becomes:

```bash
yggtools increase-version 1
yggtools version
make check
uv build
```

For larger changes:

```bash
yggtools increase-version 2  # compatible feature
yggtools increase-version 3  # breaking change
```

The quality pipeline catches any mismatch before build or publish.

---

## Consequences

**Positive:**

- Version updates become deterministic and repeatable.
- Developers choose release intent with a small numeric level instead of
  editing individual SemVer components by hand.
- CI can block inconsistent package artifacts before publishing.
- The lockfile is treated as a first-class release artifact.

**Negative:**

- The first version supports only stable SemVer.
- Projects that intentionally use dynamic versions must either opt out or wait
  for a later design extension.
- `increase-version` must preserve TOML formatting carefully enough to avoid
  noisy diffs.

---

## Alternatives rejected

**Use `bumpversion` or another release tool** — adds another configuration
surface and duplicates the yggtools goal of providing an opinionated, compact
workflow. Rejected for now.

**Use textual arguments (`patch`, `minor`, `major`) instead of levels** — more
self-documenting, but the requested interface is numeric. The command can add
aliases later without changing the level contract.

**Only update `pyproject.toml`** — leaves runtime metadata and `uv.lock` stale,
which is the inconsistency this ADR is meant to prevent. Rejected.

**Skip the lint and rely on the command** — manual edits, merge conflicts, or
future tools can still introduce drift. The lint gives an independent safety
net. Rejected.
