import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django_htmx.middleware import HtmxDetails

from phoxtail.tokens.permissions.models import AccessTokensAdminPermission

from .factories import AccessTokenFactory, UserFactory

User = get_user_model()


@pytest.fixture(autouse=True)
def _htmx_attr(rf, monkeypatch):
    """Attach ``request.htmx`` to RequestFactory requests.

    RequestFactory bypasses middleware, so HtmxMiddleware never runs.
    Mirrors phoxtail/core/tests/conftest.py.
    """
    original_get = rf.__class__.get
    original_post = rf.__class__.post

    def patched_get(self, *args, **kwargs):
        request = original_get(self, *args, **kwargs)
        request.htmx = HtmxDetails(request)
        return request

    def patched_post(self, *args, **kwargs):
        request = original_post(self, *args, **kwargs)
        request.htmx = HtmxDetails(request)
        return request

    monkeypatch.setattr(rf.__class__, "get", patched_get)
    monkeypatch.setattr(rf.__class__, "post", patched_post)


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(username="admin", email="admin@example.com", password="testpass123")


@pytest.fixture
def access_token(db, user):
    return AccessTokenFactory(user=user)


def grant_token_permissions(user, *codenames):
    """Grant tokens-admin permissions and return a fresh user instance.

    Re-fetching is necessary because Django caches ``user.has_perm`` results
    on the user instance, and the cache is not invalidated by adding new
    rows to ``user_permissions``.
    """
    ct = ContentType.objects.get_for_model(AccessTokensAdminPermission)
    perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
    assert perms.count() == len(codenames), (
        f"Missing tokens permissions; got {[p.codename for p in perms]}, expected {list(codenames)}"
    )
    user.user_permissions.add(*perms)
    return User.objects.get(pk=user.pk)


def issue_key(user, scope="cms:read", **fields):
    """A key as the authorization server leaves it after a consent: the row
    with its digest, the raw value known only to the client. Written
    directly; the flow that mints one is pinned in its own tests."""
    from datetime import timedelta

    from django.utils import timezone
    from oauth2_provider.models import Application, get_access_token_model, set_token_value
    from oauth2_provider.settings import oauth2_settings
    from oauthlib.common import generate_token

    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="http://localhost:9999/cb",
        name="probe",
    )
    raw = generate_token()
    fields.setdefault("expires", timezone.now() + timedelta(seconds=oauth2_settings.ACCESS_TOKEN_EXPIRE_SECONDS))
    token = get_access_token_model()(user=user, application=app, scope=scope, **fields)
    set_token_value(token, raw)
    token.save()
    return raw, token
