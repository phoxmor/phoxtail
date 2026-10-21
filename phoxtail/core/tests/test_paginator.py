import re

from django.core.paginator import Paginator
from django.template import engines

from phoxtail.core.templatetags.phoxtail_core_tags import page_steps, page_window


def page(number, count=30, per_page=10):
    return Paginator(range(count), per_page).get_page(number)


def render(number, count=30, per_page=10, **context):
    source = (
        "{% load phoxtail_core_tags %}"
        '{% paginator page url="/list/filters/" include="#filters, #search" param="filter-page" %}'
    )
    return engines["django"].from_string(source).render({"page": page(number, count, per_page), **context})


def asked(html):
    """The page each button asks for, in order."""
    return re.findall(r"""hx-vals='\{"filter-page": "(\d+)"\}'""", html)


def test_a_single_page_draws_nothing():
    assert render(1, count=5).strip() == ""


def test_each_button_asks_its_page_with_the_lists_state():
    html = render(3, count=100)

    # First, Previous, pages 1, 2, 4, 5, Next, Last
    assert asked(html) == ["1", "2", "1", "2", "4", "5", "4", "10"]
    assert html.count('hx-get="/list/filters/"') == 8
    assert html.count('hx-include="#filters, #search"') == 8
    assert 'aria-current="page">3</span>' in html


def test_the_ends_are_icons_named_for_screen_readers():
    labels = re.findall(r'aria-label="([^"]*)"', render(2))

    assert labels == ["Pagination", "First page", "Previous", "Next", "Last page"]


def test_the_ends_are_dimmed_not_dropped():
    first, last = render(1), render(3)

    assert first.count('aria-disabled="true"') == 2
    assert last.count('aria-disabled="true"') == 2
    assert "First page" not in first and "Previous" not in first
    assert "Next" not in last and "Last page" not in last


def test_every_page_draws_as_many_buttons():
    counts = {render(n, count=100).count('class="phx-button') for n in range(1, 11)}

    assert counts == {9}


def test_the_window_centres_the_current_page():
    assert page_window(page(5, count=100)) == [(3, False), (4, True), (5, True), (6, True), (7, False)]


def test_the_window_slides_at_either_end():
    assert [n for n, _ in page_window(page(1, count=100))] == [1, 2, 3, 4, 5]
    assert [n for n, _ in page_window(page(10, count=100))] == [6, 7, 8, 9, 10]


def test_a_phone_keeps_the_three_nearest_even_at_the_ends():
    assert [n for n, near in page_window(page(1, count=100)) if near] == [1, 2, 3]
    assert [n for n, near in page_window(page(10, count=100)) if near] == [8, 9, 10]


def test_fewer_pages_than_the_window_shows_them_all():
    assert page_window(page(2, count=30)) == [(1, True), (2, True), (3, True)]


def test_the_ends_ask_for_first_previous_next_and_last():
    before, after = page_steps(page(4, count=100))

    assert [number for _, _, number in before] == [1, 3]
    assert [number for _, _, number in after] == [5, 10]
