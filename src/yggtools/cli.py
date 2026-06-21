"""Command-line entry point for yggtools."""

from __future__ import annotations

import typer

from yggtools.quality.commands import register as register_quality_commands
from yggtools.repo_init.commands import register as register_repo_init_commands
from yggtools.version_commands import register as register_version_commands

app = typer.Typer(
    name="yggtools",
    help="Developer toolbox: scaffolding, quality pipeline.",
    no_args_is_help=True,
)

register_quality_commands(app)
register_repo_init_commands(app)
register_version_commands(app)


def main() -> None:  # pragma: no cover
    """Run the yggtools CLI application."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
