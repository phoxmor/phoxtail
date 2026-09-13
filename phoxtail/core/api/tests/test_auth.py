"""What each internal-link endpoint asks of its caller.

The five endpoints asked for nothing beyond being authenticated: any account
with a session or an unrestricted token could rename or delete a link that
menus across the project point at. Each now names the permission its act
needs and ``guarded()`` asks both halves about it — whether the person holds
it, and whether their credential covers it.

The model is a registered snippet, so Wagtail's Groups form already offers
``add``, ``change`` and ``delete``. It offers ``view`` for no model at all —
Wagtail treats seeing a thing as implied by editing it — so that one currently
has no checkbox anywhere. The row exists and is checked; what is missing is an
interface that grants it.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission

READS = ["/core/v1/internal-links/", "/core/v1/internal-links/{id}/"]


def grant(user, codename: str):
    """Give *user* a permission and hand back an instance that can see it.

    Django caches permissions on the user instance at first lookup, and the
    request is served with the instance the test holds, so a fresh one is the
    documented way to make a just-granted permission visible.
    """
    user.user_permissions.add(Permission.objects.get(codename=codename, content_type__app_label="phoxtail_core"))
    return type(user).objects.get(pk=user.pk)


def test_unauthenticated_request_is_401(db, raw_client):
    """No caller at all is a different event from the wrong caller."""
    assert raw_client.get("/core/v1/internal-links/").status_code == 401


@pytest.mark.parametrize("path", READS)
def test_reading_without_the_permission_is_403(raw_client, regular_user, link, path):
    response = raw_client.get(path.format(id=link.id), user=regular_user)
    assert response.status_code == 403
    assert "view_internallink" in response.json()["detail"]


@pytest.mark.parametrize("path", READS)
def test_reading_with_the_permission_is_allowed(raw_client, regular_user, link, path):
    """The widening this commit is for: no superuser flag involved."""
    user = grant(regular_user, "view_internallink")
    assert raw_client.get(path.format(id=link.id), user=user).status_code == 200


def test_reading_does_not_grant_creating(raw_client, regular_user):
    user = grant(regular_user, "view_internallink")
    response = raw_client.post(
        "/core/v1/internal-links/",
        json={"label": "Billing", "url_name": "dashboard:billing"},
        user=user,
    )
    assert response.status_code == 403
    assert "add_internallink" in response.json()["detail"]


def test_creating_does_not_grant_changing(raw_client, regular_user, link):
    user = grant(regular_user, "add_internallink")
    response = raw_client.patch(
        f"/core/v1/internal-links/{link.id}/",
        json={"label": "Renamed"},
        headers={"If-Match": "*"},
        user=user,
    )
    assert response.status_code == 403
    assert "change_internallink" in response.json()["detail"]


def test_changing_does_not_grant_deleting(raw_client, regular_user, link):
    """The act this pass most exists for — it used to need no permission."""
    user = grant(regular_user, "change_internallink")
    response = raw_client.delete(f"/core/v1/internal-links/{link.id}/", user=user)
    assert response.status_code == 403
    assert "delete_internallink" in response.json()["detail"]


def test_deleting_with_the_permission_is_allowed(raw_client, regular_user, link):
    from phoxtail.core.models import InternalLink

    user = grant(regular_user, "delete_internallink")
    assert raw_client.delete(f"/core/v1/internal-links/{link.id}/", user=user).status_code == 204
    assert not InternalLink.objects.filter(pk=link.pk).exists()


def test_superuser_is_still_admitted(client, link):
    """Unchanged for them: Django answers has_perm True for a superuser."""
    assert client.get("/core/v1/internal-links/").status_code == 200
