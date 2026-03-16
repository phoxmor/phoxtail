"""Template rendering utilities."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def render_template(template_path: str, context: dict) -> str:
    """Render a Jinja2 template from the cli/templates directory.

    Args:
        template_path: Relative path within templates/ (e.g. "docker/Dockerfile")
        context: Template variables
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        keep_trailing_newline=True,
        lstrip_blocks=True,
        trim_blocks=True,
    )
    template = env.get_template(template_path)
    return template.render(**context)
