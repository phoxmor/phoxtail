"""Each field takes only the options its template reads."""

from pathlib import Path

import pytest
from django import forms
from django.forms.renderers import get_default_renderer
from django.template.base import TextNode, Variable, VariableNode
from django.template.defaulttags import CommentNode, ForNode, IfNode, LoadNode, TemplateLiteral, WithNode
from django.template.library import SimpleNode
from django.template.loader_tags import IncludeNode
from django.templatetags.i18n import TranslateNode

from phoxtail.core import fields
from phoxtail.core.fields import FIELD_OPTIONS, render_field

# Values render_field sets itself, and the options it reads in Python.
SET_BY_RENDER = {"field", "supporting", "htmx", "trailing", "control_type"}
READ_BY_RENDER = {"help_text", "show_help_text"}
# Values a search view passes when it redraws the field's parts; never options.
SET_BY_VIEW = {"single_select_search": {"search_value"}}
LITERALS = {"True", "False", "None"}

ENGINE = get_default_renderer().engine.engine
TEMPLATES = Path(fields.__file__).parent / "templates" / fields.FIELD_TEMPLATES


def _names(expression):
    """The context names a filter expression reads: its variable and its filters' arguments."""
    variables = [expression.var] + [arg for _, args in expression.filters for lookup, arg in args if lookup]
    return {var.lookups[0] for var in variables if isinstance(var, Variable) and var.lookups}


def _condition(condition):
    if isinstance(condition, TemplateLiteral):
        return _names(condition.value)
    return set().union(*(_condition(side) for side in (condition.first, condition.second) if side is not None))


def _reads(nodelist):
    """Every context name a nodelist reads, following literal includes.

    Fails on any tag it does not know, so a new tag cannot hide what it reads.
    """
    names = set()
    for node in nodelist:
        if isinstance(node, (TextNode, CommentNode, LoadNode)):
            continue
        if isinstance(node, VariableNode):
            names |= _names(node.filter_expression)
        elif isinstance(node, TranslateNode) and node.asvar is None:
            names |= _names(node.filter_expression)
        elif isinstance(node, SimpleNode) and node.target_var is None:
            for arg in [*node.args, *node.kwargs.values()]:
                names |= _names(arg)
        elif isinstance(node, IfNode):
            for condition, branch in node.conditions_nodelists:
                names |= (_condition(condition) if condition is not None else set()) | _reads(branch)
        elif isinstance(node, ForNode):
            loop = _reads(node.nodelist_loop) - {*node.loopvars, "forloop"}
            names |= _names(node.sequence) | loop | _reads(node.nodelist_empty)
        elif isinstance(node, WithNode):
            names |= set().union(*map(_names, node.extra_context.values())) | (
                _reads(node.nodelist) - set(node.extra_context)
            )
        elif isinstance(node, IncludeNode):
            names |= set().union(_names(node.template), *map(_names, node.extra_context.values()))
            # A template named by a variable is the caller's (item_template),
            # not part of the field.
            if isinstance(node.template.var, str):
                names |= _reads(ENGINE.get_template(node.template.var).nodelist) - set(node.extra_context)
        else:
            raise AssertionError(f"the test does not know what {node!r} reads; teach _reads")
    return names - LITERALS


def test_every_field_declares_its_options():
    assert set(FIELD_OPTIONS) == {path.stem for path in TEMPLATES.glob("*.html")}


@pytest.mark.parametrize("name", sorted(FIELD_OPTIONS))
def test_a_fields_options_are_what_its_template_reads(name):
    reads = _reads(ENGINE.get_template(f"{fields.FIELD_TEMPLATES}/{name}.html").nodelist)
    options, htmx = FIELD_OPTIONS[name]

    assert reads - SET_BY_RENDER - SET_BY_VIEW.get(name, set()) | READ_BY_RENDER == options
    assert ("htmx" in reads) == htmx


class ContactForm(forms.Form):
    email = forms.EmailField()


def test_a_misspelled_option_fails_naming_the_valid_ones():
    with pytest.raises(TypeError, match=r"'input' field has no option show_lable; its options are .*show_label"):
        render_field("input", ContactForm()["email"], show_lable=False)


class MemberForm(forms.Form):
    user = fields.SingleSelectSearchField(queryset=None)


def test_a_field_that_reads_no_htmx_refuses_it():
    with pytest.raises(TypeError, match="has no option hx_get"):
        render_field("single_select_search", MemberForm()["user"], hx_get="/users/")
