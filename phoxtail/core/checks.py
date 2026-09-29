"""System checks for the fields and their callers.

Both catch at startup what would otherwise fail only after a click: a
``{% field %}`` call with a wrong name or option (many are drawn only in a
drawer or an htmx piece), and a search field over a model the search
engine cannot narrow (it fails on the first keystroke).
"""

from pathlib import Path

from django.core.checks import Error, Tags, register
from django.forms.renderers import get_default_renderer
from django.template import Origin, Template, TemplateDoesNotExist, TemplateSyntaxError, engines
from django.template.backends.django import DjangoTemplates
from django.template.base import Lexer, TokenType
from django.template.library import SimpleNode
from django.urls import URLResolver, get_resolver
from wagtail.search import index

from phoxtail.core.fields import FIELD_NAME, FIELD_TEMPLATES, refuse_unknown_options
from phoxtail.core.templatetags.phoxtail_core_tags import field
from phoxtail.core.views import SingleSelectSearchView


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


@register(Tags.urls)
def searched_models(app_configs, **kwargs):
    """Every model a search field searches declares its key a FilterField.

    The search sees only the form's allowed rows ("id is one of these"), and
    the search engine filters only on declared columns. A view no URL reaches
    cannot be searched, so the routed views are the ones checked.
    """
    views = {}
    for pattern in _patterns(get_resolver()):
        view = getattr(pattern.callback, "view_class", None)
        if isinstance(view, type) and issubclass(view, SingleSelectSearchView):
            form_field = view.form_class.base_fields.get(view.field_name)
            queryset = getattr(form_field, "queryset", None)
            if queryset is not None:
                views.setdefault(queryset.model, set()).add(view.__name__)
    errors = []
    for model, names in views.items():
        key = model._meta.pk.attname
        indexed = issubclass(model, index.Indexed)
        fields = model.get_search_fields() if indexed else []
        if not any(isinstance(f, index.FilterField) and f.get_attname(model) == key for f in fields):
            hint = f'Add index.FilterField("{key}") to {model.__name__}.search_fields.'
            errors.append(
                Error(
                    f"{model.__name__} is searched by {', '.join(sorted(names))}, but the search "
                    f"engine cannot narrow it to the form's choices.",
                    hint=hint if indexed else f"Make {model.__name__} an index.Indexed model. {hint}",
                    obj=model,
                    id="phoxtail_core.E003",
                )
            )
    return errors


def _patterns(resolver):
    for pattern in resolver.url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _patterns(pattern)
        else:
            yield pattern
