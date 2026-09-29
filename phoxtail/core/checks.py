"""System checks for the field templates' callers.

A ``{% field %}`` call with a wrong name or option fails only when its page
is drawn, and many are drawn only after a click (a drawer, an htmx piece).
This check reads every template of every installed app at startup instead.
"""

from pathlib import Path

from django.core.checks import Error, Tags, register
from django.forms.renderers import get_default_renderer
from django.template import Origin, Template, TemplateDoesNotExist, TemplateSyntaxError, engines
from django.template.backends.django import DjangoTemplates
from django.template.base import Lexer, TokenType
from django.template.library import SimpleNode

from phoxtail.core.fields import FIELD_NAME, FIELD_TEMPLATES, refuse_unknown_options
from phoxtail.core.templatetags.phoxtail_core_tags import field


@register(Tags.templates)
def field_calls(app_configs, **kwargs):
    """Every ``{% field %}`` names a field template and only the options it takes."""
    errors = []
    for backend in engines.all():
        if not isinstance(backend, DjangoTemplates):
            continue
        # The folders runserver watches for template changes, found the same way.
        folders = {
            folder for loader in backend.engine.template_loaders for folder in getattr(loader, "get_dirs", list)()
        }
        for folder in sorted(map(Path, folders)):
            for path in sorted(folder.rglob("*.html")):
                errors += _check_template(backend.engine, folder, path)
    return errors


def _check_template(engine, folder, path):
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    # Only a template that calls the tag is compiled.
    if "field" not in source or not any(
        token.token_type == TokenType.BLOCK and token.contents.split()[:1] == ["field"]
        for token in Lexer(source).tokenize()
    ):
        return []
    # Named as its loader would name it, so a relative {% include "./…" %} resolves.
    origin = Origin(str(path), template_name=path.relative_to(folder).as_posix())
    try:
        nodes = Template(source, origin=origin, engine=engine).nodelist.get_nodes_by_type(SimpleNode)
    except TemplateSyntaxError as error:
        return [Error(f"{path}: {error}", id="phoxtail_core.E001")]
    errors = []
    for node in nodes:
        if node.func is not field:
            continue
        # The tag also takes its first two arguments by keyword.
        expression = node.args[0] if node.args else node.kwargs.get("name")
        if expression is None or not isinstance(expression.var, str) or expression.filters:
            continue
        name = expression.var
        where = f"{path}, line {node.token.lineno}"
        try:
            if not FIELD_NAME.fullmatch(name):
                raise TypeError(f"{name!r} is not a field name")
            get_default_renderer().get_template(f"{FIELD_TEMPLATES}/{name}.html")
            refuse_unknown_options(name, node.kwargs.keys() - {"name", "bound_field"})
        except TemplateDoesNotExist:
            errors.append(Error(f"{where}: there is no {name!r} field", id="phoxtail_core.E002"))
        except TypeError as error:
            errors.append(Error(f"{where}: {error}", id="phoxtail_core.E002"))
    return errors
