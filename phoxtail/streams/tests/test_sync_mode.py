"""The sync page's Remote/Local switch always shows one side chosen.

The search box reads the chosen side to send it along, so a page with neither
side chosen would stop the search from working.
"""

from __future__ import annotations

import re

import pytest
from django.test import RequestFactory

from phoxtail.remotes.models import Remote
from phoxtail.streams.admin.sync.views import admin_sync_index
from phoxtail.streams.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _chosen(mode):
    Remote.objects.create(name="Remote", base_url="https://remote.example.com", token="token")
    request = RequestFactory().get("/", {"mode": mode})
    request.user = UserFactory(is_superuser=True, is_staff=True)
    request.htmx = True

    html = admin_sync_index(request).content.decode()

    return re.findall(r'<input type="radio" name="mode" value="(\w+)"[^>]* checked>', html)


@pytest.mark.parametrize(("mode", "chosen"), [("local", ["local"]), ("remote", ["remote"]), ("foo", ["remote"])])
def test_the_switch_shows_the_asked_side_or_the_default(mode, chosen):
    assert _chosen(mode) == chosen
