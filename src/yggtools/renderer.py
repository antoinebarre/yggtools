"""Jinja2 template rendering for yggtools project files."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from yggtools import __version__
from yggtools.models import ProjectContext

_TEMPLATES_PACKAGE = "yggtools.templates"


def render_template(template_name: str, ctx: ProjectContext) -> str:
    """Load and render a Jinja2 template from the embedded templates package.

    Args:
        template_name: Filename of the template, e.g. ``pyproject.toml.tmpl``.
        ctx: Project context providing template variables.

    Returns:
        Rendered template content as a string.

    Raises:
        FileNotFoundError: If the template does not exist in the package.
    """
    raw = _load_template(template_name)
    env = Environment(  # noqa: S701  # nosec B701
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    template = env.from_string(raw)
    return template.render(
        project_name=ctx.project_name,
        package_name=ctx.package_name,
        python_version=ctx.python_version,
        yggtools_version=__version__,
    )


def list_templates() -> list[str]:
    """Return the names of all embedded Jinja2 templates.

    Returns:
        Sorted list of template filenames ending in ``.tmpl``.
    """
    package = files(_TEMPLATES_PACKAGE)
    return sorted(
        item.name for item in package.iterdir() if item.name.endswith(".tmpl")
    )


def list_embedded_scripts() -> list[str]:
    """Return the names of all embedded script files.

    Returns:
        Sorted list of script filenames inside ``templates/scripts/``.
    """
    package = files(f"{_TEMPLATES_PACKAGE}.scripts")
    return sorted(
        item.name
        for item in package.iterdir()
        if not item.name.startswith("__")
    )


def embedded_script_path(script_name: str) -> Path:
    """Resolve the filesystem path of an embedded script.

    Uses ``importlib.resources`` to locate the script and return a
    usable ``Path``.  Works both from the source tree and from an
    installed wheel because the templates package is included in the
    wheel via ``force-include``.

    Args:
        script_name: Filename of the script, e.g. ``check.sh``.

    Returns:
        Absolute path to the embedded script file.

    Raises:
        FileNotFoundError: If the script does not exist in the package.
    """
    resource = files(f"{_TEMPLATES_PACKAGE}.scripts").joinpath(script_name)
    if not resource.is_file():
        msg = f"Embedded script not found: {script_name}"
        raise FileNotFoundError(msg)
    return Path(str(resource))


def _load_template(name: str) -> str:
    """Read raw text of an embedded template file.

    Args:
        name: Template filename.

    Returns:
        Raw template text.

    Raises:
        FileNotFoundError: If the template file is not found.
    """
    resource = files(_TEMPLATES_PACKAGE).joinpath(name)
    if not resource.is_file():
        msg = f"Template not found: {name}"
        raise FileNotFoundError(msg)
    return resource.read_text(encoding="utf-8")
