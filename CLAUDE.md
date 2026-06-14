# Claude Code Instructions

These instructions apply to the whole repository.

## Coding Standards

- Strictly follow Python PEP rules and the Google Python Style Guide for all
  Python code.
- Keep each function's cyclomatic complexity at or below 10.
- Keep Python modules below 500 lines unless an ADR explicitly justifies a
  larger module.
- Do not split a module purely to reduce its line count or cyclomatic
  complexity. A split is justified only when the resulting modules have
  genuinely independent reasons to change. Validation helpers that are only
  ever used by one module belong in that module, not in a separate file.
- Do not optimize for maintainability-index scores when they encourage
  artificial fragmentation into very small files.
- Write Google-style docstrings for every function and class, including private
  functions and classes.
- Write clean, auditable code with simple control flow.
- Favor clarity over cleverness.
- Use precise names for modules, classes, functions, variables, and tests.
- Keep comments rare and useful.
- Apply SOLID principles strictly:
  - Single Responsibility: each module, class, and function must have one clear
    reason to change.
  - Open/Closed: add behavior through new focused implementations, rules,
    strategies, or registries instead of editing large conditional blocks.
  - Liskov Substitution: implementations of a public protocol must remain
    interchangeable and must not weaken expected behavior.
  - Interface Segregation: depend on narrow protocols or callables rather than
    broad objects with unrelated responsibilities.
  - Dependency Inversion: high-level workflows depend on stable interfaces, not
    concrete low-level details.

## Dependencies

- Minimize external dependencies.
- Prefer Python standard library packages.
- Do not add third-party dependencies unless explicitly requested by the user or
  unless there is a clear technical need that cannot reasonably be met with the
  standard library.
- Explain the reason for any new dependency before adding it.
- Allowed external dependencies for yggtools itself: `typer`, `rich`, `jinja2`.
  These are justified because: `typer` provides typed CLI generation that cannot
  be replicated cleanly with `argparse`; `rich` provides the terminal formatting
  expected by the tool's UX; `jinja2` provides template rendering with
  inheritance that `string.Template` cannot match.

## Implementation Guidance

- Start substantial feature work and architecture changes with an Architecture
  Decision Record in `doc/` before implementing code.
- Keep changes focused on the requested behavior.
- Keep public interfaces small.
- Name modules, classes, functions, variables, and tests with business/domain
  vocabulary first. Prefer names such as `scaffold_project`, `render_template`,
  or `copy_scripts` over architecture-first names such as `node`, `processor`,
  `handler`, or `orchestrator`.
- Prefer concrete, short, auditable names over abstract framework names.
- Avoid global mutable state unless there is a clear reason.
- Prefer deterministic behavior and explicit inputs.
- Use design patterns deliberately:
  - use Strategy when behavior varies by profile, format, rule, or policy;
  - use Registry when behavior must be extended without modifying the engine;
  - use Adapter when exposing a simple callable or external API behind an
    internal interface;
  - use Factory functions when object creation has validation or multiple
    variants.
- Do not introduce a design pattern for decoration.
- Write tests for new behavior.
- For new public behavior, add targeted unit tests and integration tests only as
  workflow coverage; do not rely on end-to-end tests alone.
- Maintain 100% test coverage.
- Test function docstrings must state the requirement being verified using the
  prefix `Requirement:`.
- Every module, function, class, method, and test must include a strict
  Google-style docstring, including private functions and classes.
- Function and method docstrings must include:
  - a precise summary that explains the domain behavior;
  - `Args:` for every parameter except `self` and `cls`;
  - `Returns:` for every non-`None` return value;
  - `Raises:` for every intentionally raised exception.
- Class docstrings must include `Attributes:` when instances expose public
  attributes.
- Avoid placeholder docstrings such as `Function result.` or vague summaries.

## Project Structure

- Source code lives in `src/yggtools/`.
- Tests live in `tests/`.
- Scripts (quality pipeline) live in `scripts/`.
- Temporary outputs (coverage, caches, build artifacts) go into `work/`.
- Embedded templates and scripts for project scaffolding live in
  `src/yggtools/templates/`.

## Quality Checks

Before finishing code changes, run:

```bash
make check
```

Use `make ci` for non-mutating verification and `make check-dist` before
publishing.
