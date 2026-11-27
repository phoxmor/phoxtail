"""A public page stands on the ground.

The bar reserves room under the page with body padding, and padding shows the
body's own background. Without the ground class the body is unpainted, so that
strip came out as the browser's white instead of the ground's grey. A page
that extends the base can change the class through the ``bodyclass`` block.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from django.template import engines
from django.test import RequestFactory
from wagtail.models import Site

pytestmark = pytest.mark.django_db


def _render(source):
    request = RequestFactory().get("/")
    request.user = AnonymousUser()
    page = Site.objects.get(is_default_site=True).root_page.specific
    template = engines["django"].from_string('{% extends "phoxtail_cms/pages/base.html" %}' + source)
    return template.render({"page": page}, request=request)


def test_the_page_body_is_the_ground():
    assert '<body class="phx-ground">' in _render("")


def test_a_page_can_replace_the_body_class():
    html = _render("{% block bodyclass %}my-ground{% endblock %}")
    assert '<body class="my-ground">' in html
    assert "phx-ground" not in html


def test_a_page_can_add_to_the_body_class():
    html = _render("{% block bodyclass %}{{ block.super }} my-page{% endblock %}")
    assert '<body class="phx-ground my-page">' in html
