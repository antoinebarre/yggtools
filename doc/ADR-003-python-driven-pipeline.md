# ADR-003 — Python-driven quality pipeline with Rich console output

**Date:** 2026-06-20
**Status:** Proposed
**Author:** Antoine Barré

---

## Context

The current quality pipeline is **orchestrated by CI YAML** (GitHub Actions,
GitLab CI) with each check running as a separate job.  yggtools provides
the check implementations but the CI platform controls execution order,
dependencies between stages, matrix expansion, and artifact collection.

This creates several problems:

1. **Duplicated orchestration.** Adding or reordering a check requires
   editing both yggtools (Python) and the CI YAML.  The GitHub workflow is
   ~120 lines that mirror what `run_all` already does in Python.

2. **Non-portable.** The pipeline logic is split across GitHub-specific
   and GitLab-specific YAML files.  A developer running `make check`
   locally gets a different experience than CI: no structured artifacts,
   no checksums, minimal output.

3. **Poor local feedback.** The console currently prints one line per
   check with basic Rich markup.  There is no progress indication during
   execution, no structured summary table, and checksums are only shown
   in CI mode.

4. **Artifact opacity.** JSON reports and SHA-256 sidecars are only
   written when `--ci` is passed.  A developer has no way to inspect or
   verify artifacts locally without switching modes.

---

## Decision

### Pipeline ownership moves to yggtools

yggtools becomes the **sole orchestrator** of the quality pipeline.  The
CI YAML (GitHub and GitLab) reduces to a thin wrapper:

```yaml
# GitHub Actions — entire CI in one job
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run yggtools pipeline
      - uses: actions/upload-artifact@v4
        with:
          name: quality-report
          path: work/reports/
```

The `yggtools pipeline` command replaces `yggtools run --all`.  It runs
a fixed sequence of stages, writes all artifacts, and exits non-zero if
any stage fails.

### Pipeline stages

The pipeline executes stages in a fixed, deterministic order.  Each stage
groups related checks:

| #  | Stage               | Checks                        |
|----|---------------------|-------------------------------|
| 1  | **Linters**         | `format`, `ruff`, `flake8`    |
| 2  | **Type checking**   | `typecheck` (mypy)            |
| 3  | **Metrics**         | `metrics` (CC, module size)   |
| 4  | **Security**        | `security-code`, `security-deps` |
| 5  | **Tests & coverage**| `tests` (pytest + coverage)   |

Stages run sequentially.  Within a stage, checks run sequentially in
registration order.  If a check in an early stage fails, later stages
still execute (no fail-fast by default) so the developer gets the full
picture in one run.

### Artifact contract

Every pipeline run writes artifacts to `work/reports/`:

```
work/reports/
├── format.json
├── format.json.sha256
├── ruff.json
├── ruff.json.sha256
├── flake8.json
├── flake8.json.sha256
├── typecheck.json
├── typecheck.json.sha256
├── metrics.json
├── metrics.json.sha256
├── security-code.json
├── security-code.json.sha256
├── security-deps.json
├── security-deps.json.sha256
├── tests.json
├── tests.json.sha256
└── pipeline.json          # consolidated summary
```

Each check JSON follows the existing `yggtools.ci.check.v1` schema and
includes:

- Full stdout and stderr (verbosity max — no truncation).
- The command that was executed.
- Structured metadata (error counts, violations, complexity data).
- Duration in seconds.

The `pipeline.json` file adds:

- Pipeline-level status (`pass` / `fail`).
- Total duration.
- Per-artifact SHA-256 digest.
- Timestamp.

Artifacts are **always written**, whether running locally or in CI.
There is no longer a separate `--ci` mode for artifact generation.

### Rich console output

The console uses Rich tables, panels, and progress indicators to provide
a clear, information-dense display:

**During execution** — a Rich progress bar or status spinner per check,
showing which stage is running and elapsed time.

**After completion** — a summary panel with a Rich table:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      yggtools pipeline — myproject                 │
├──────────────┬────────┬──────────┬──────────────────────────────────┤
│ Check        │ Status │ Duration │ Detail                           │
├──────────────┼────────┼──────────┼──────────────────────────────────┤
│ format       │ PASS   │   0.42s  │ 0 file(s) to reformat            │
│ ruff         │ PASS   │   0.38s  │ 0 error(s)                       │
│ flake8       │ PASS   │   1.12s  │ 0 violation(s)                   │
│ typecheck    │ PASS   │   4.21s  │ Success                          │
│ metrics      │ PASS   │   0.15s  │ max CC=7, 0 violation(s)         │
│ security-code│ PASS   │   0.31s  │ 0 issue(s)                       │
│ security-deps│ PASS   │   2.07s  │ No vulnerabilities found         │
│ tests        │ PASS   │   6.53s  │ 103 passed · coverage 100%       │
├──────────────┴────────┴──────────┴──────────────────────────────────┤
│ 8/8 passed                                            Total 15.19s │
└─────────────────────────────────────────────────────────────────────┘
```

**Artifact table** — a second Rich table listing every artifact with
its path and SHA-256 digest:

```
┌──────────────────────────────────────────────────────────────────────┐
│ Artifacts — work/reports/                                            │
├────────────────────────┬─────────────────────────────────────────────┤
│ File                   │ SHA-256                                      │
├────────────────────────┼─────────────────────────────────────────────┤
│ format.json            │ a1b2c3d4e5f6…                                │
│ ruff.json              │ f6e5d4c3b2a1…                                │
│ …                      │ …                                            │
│ pipeline.json          │ 1234abcd5678…                                │
└────────────────────────┴─────────────────────────────────────────────┘
```

### CLI changes

| Before                         | After                            |
|--------------------------------|----------------------------------|
| `yggtools run --all`           | `yggtools pipeline`              |
| `yggtools run --all --ci`      | `yggtools pipeline` (same)       |
| `yggtools run <check>`         | `yggtools run <check>` (kept)    |
| `yggtools run <check> --ci`    | `yggtools run <check>` (always writes artifacts) |

- `yggtools pipeline` is the new primary command.  It runs all stages,
  writes all artifacts, and displays the Rich dashboard.
- `yggtools run <check>` is kept for running a single check during
  development.  It also writes artifacts and displays checksums.
- The `--ci` flag is removed.  Behavior is identical in all environments.

### CI YAML generation

The `init` and `init-repo` commands already generate CI templates.  They
will be updated to emit the simplified single-job YAML shown above.  The
generated YAML has no knowledge of individual checks — it delegates
everything to `yggtools pipeline`.

---

## Consequences

### Positive

- **Single source of truth.** The pipeline definition lives in Python.
  Adding a check requires only a `@register` decorator — no YAML to edit.

- **Portable.** `make check`, GitHub Actions, GitLab CI, and any other
  runner all execute the exact same pipeline with the same output.

- **Rich local experience.** Developers get the same structured feedback
  locally as in CI: tables, checksums, full artifacts.

- **Auditable artifacts.** Every run produces JSON contracts with SHA-256
  digests, regardless of environment.

- **Testable orchestration.** Pipeline ordering, fail behavior, and
  artifact writing are Python code covered by unit tests.

### Negative

- **No per-check parallelism in CI.** All checks run in one job instead
  of parallel CI jobs.  For a project of this scale (pipeline < 30s),
  this is acceptable.  If needed, Python-level parallelism
  (`concurrent.futures`) can be added later without changing the CI YAML.

- **Larger single artifact.** CI uploads one `work/reports/` directory
  instead of per-job artifacts.  This simplifies navigation but means
  a partial failure still produces the full artifact set.

### Migration

- The `--ci` flag on `yggtools run` is deprecated and ignored (no
  breaking change — it just becomes a no-op).
- Existing CI YAML files in scaffolded projects must be regenerated via
  `yggtools init` or manually simplified.

---

## Implementation outline

1. **New module `src/yggtools/quality/pipeline.py`** — defines the stage
   ordering, runs checks via the existing runner, writes all artifacts,
   returns a `PipelineResult` dataclass.

2. **New module `src/yggtools/quality/console.py`** — Rich rendering
   logic: progress display during execution, summary table, artifact
   table with checksums.  Separating rendering from pipeline logic keeps
   both testable.

3. **New CLI command `yggtools pipeline`** in `cli.py` — thin entry
   point calling the pipeline and console modules.

4. **Update `report.py`** — `write_check_json_reports` always writes
   artifacts (remove CI-only gating).  Add `pipeline.json` writer.

5. **Update CI templates** — `github_ci.yml.tmpl` and
   `gitlab_ci.yml.tmpl` reduce to a single-job wrapper.

6. **Deprecate `--ci` flag** — keep the option for backwards
   compatibility but make it a no-op.

7. **Tests** — unit tests for pipeline ordering, artifact generation,
   console rendering (using `rich.console.Console(file=StringIO())`).
