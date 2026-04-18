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
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="testpass123"
    )


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
        f"Missing tokens permissions; got {[p.codename for p in perms]}, "
        f"expected {list(codenames)}"
    )
    user.user_permissions.add(*perms)
    return User.objects.get(pk=user.pk)
