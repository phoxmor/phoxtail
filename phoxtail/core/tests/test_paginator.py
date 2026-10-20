from django.core.paginator import Paginator
from django.template import engines


def render(number, count=30, per_page=10, **context):
    page = Paginator(range(count), per_page).get_page(number)
    source = (
        "{% load phoxtail_core_tags %}"
        '{% paginator page url="/list/filters/" include="#filters, #search" param="filter-page" %}'
    )
    return engines["django"].from_string(source).render({"page": page, **context})


def test_a_single_page_draws_nothing():
    assert render(1, count=5).strip() == ""


def test_each_button_asks_its_page_with_the_lists_state():
    html = render(2)

    assert html.count('hx-get="/list/filters/"') == 4  # Previous, pages 1 and 3, Next
    assert html.count('hx-include="#filters, #search"') == 4
    assert """hx-vals='{"filter-page": "1"}'""" in html
    assert """hx-vals='{"filter-page": "3"}'""" in html
    assert 'aria-current="page">2</span>' in html
    assert "Page 2 of 3" in html


def test_the_ends_are_dimmed_not_dropped():
    first, last = render(1), render(3)

    assert first.count('aria-disabled="true"') == 1
    assert last.count('aria-disabled="true"') == 1
    assert "Previous" in first and "Next" in last
