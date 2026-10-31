import logging

from django.template import engines


def render(source):
    return engines["django"].from_string("{% load phoxtail_design_tags %}" + source).render({})


def test_a_known_icon_renders_its_svg():
    assert 'id="icon-graph-5"' in render('{% icon "graph_5" %}')


def test_an_unknown_icon_renders_nothing_and_warns(caplog):
    with caplog.at_level(logging.WARNING, logger="phoxtail.design.templatetags.phoxtail_design_tags"):
        html = render('<p>{% icon "no_such_icon" %}Account</p>')

    assert html == "<p>Account</p>"
    assert "Icon 'no_such_icon' not found" in caplog.text
