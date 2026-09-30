"""A page says which language it is written in."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.utils.translation import override


@pytest.mark.django_db
def test_the_page_is_marked_with_the_active_language(rf):
    request = rf.get("/el/")
    request.user = AnonymousUser()

    with override("el"):
        page = render_to_string("phoxtail_dashboard/base.html", request=request)

    assert '<html lang="el">' in page
