import re

from django.template import engines


def render(blocks=""):
    source = '{% extends "phoxtail_core/page_header.html" %}{% load phoxtail_design_tags %}' + blocks
    return engines["django"].from_string(source).render({})


def test_an_empty_block_leaves_its_box_empty_so_css_hides_it():
    html = render("{% block title %}Remotes{% endblock %}")

    assert '<p class="phx-page-header__subtitle"></p>' in html
    assert '<div class="phx-page-header__controls"></div>' in html
    assert '<div class="phx-page-header__below"></div>' in html


def test_the_page_has_one_name_its_icon_before_it():
    html = render('{% block icon %}{% icon "graph_5" %}{% endblock %}{% block title %}Remotes{% endblock %}')

    assert html.count("<h1") == 1
    title = re.search(r'<h1 class="phx-page-header__title">(.*?)</h1>', html, re.S).group(1)
    assert title.index('id="icon-graph-5"') < title.index("Remotes")


def test_a_filled_block_lands_in_its_box():
    html = render(
        "{% block title %}Calendar{% endblock %}"
        "{% block subtitle %}Oct 19 – 25{% endblock %}"
        '{% block controls %}<button class="phx-button">Filters</button>{% endblock %}'
    )

    assert '<p class="phx-page-header__subtitle">Oct 19 – 25</p>' in html
    assert '<div class="phx-page-header__controls"><button class="phx-button">Filters</button></div>' in html
