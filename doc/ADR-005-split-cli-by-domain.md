# ADR-005 - Split CLI implementation by domain

**Date:** 2026-06-21
**Status:** Accepted
**Author:** Antoine Barre

---

## Context

`src/yggtools/cli.py` contains every Typer command, Rich rendering helper,
quality objective formatter, repository initialisation helper, reset helper,
and version command helper. The module has grown beyond 1,200 lines, which
exceeds the repository module-size objective and makes unrelated changes
compete in one file.

The current shape also hides the domain boundaries already present in the
project: quality checks live under `quality/`, repository scaffolding lives
under `repo_init/`, and version mutation lives in `versioning.py`.

## Decision

Split CLI implementation by business domain while preserving the public
`yggtools.cli:main` entry point.

`cli.py` becomes a thin Typer composition module. Domain modules register their
own commands:

- `quality.commands` registers `pipeline` and `run`.
- `repo_init.commands` registers `init-repo`, `init`, and `reset`.
- `version_commands` registers `version` and `increase-version`.

Console rendering and small formatting helpers move next to the domain that
owns their vocabulary. Shared path and text helpers move to `cli_support.py`.

## Consequences

Positive:

- CLI changes now have domain-specific reasons to change.
- `cli.py` stays below the module-size threshold and remains a stable entry
  point for packaging.
- Quality, repository initialisation, and version commands can be tested at
  their natural module boundaries.

Negative:

- Tests that patch private helpers must patch the new domain modules.
- The command registration path has one extra indirection through
  `register(app)`.

## Alternatives rejected

**Create one generic `commands.py` and one generic `display.py`.** This would
reduce `cli.py` size but preserve cross-domain coupling in new files.
Rejected.

**Keep all command functions in `cli.py` and move only helpers.** This leaves
the central file responsible for every business workflow. Rejected.

**Convert `versioning.py` into a package immediately.** That move is useful
later, but it changes import topology more than this refactor requires.
Rejected for this focused split.
