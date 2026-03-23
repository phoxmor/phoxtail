import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django_htmx.middleware import HtmxDetails

from phoxtail.core.permissions import AppPermissionPolicy
from phoxtail.core.tests.testapp.models import TestAdminPermission

User = get_user_model()


@pytest.fixture(autouse=True)
def _htmx_attr(rf, monkeypatch):
    """Ensure request.htmx is set on all RequestFactory requests.

    RequestFactory bypasses middleware, so django_htmx's HtmxMiddleware
    never runs. This fixture patches rf methods to attach the htmx
    attribute directly.
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
def policy():
    return AppPermissionPolicy(TestAdminPermission)


@pytest.fixture
def user():
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def superuser():
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="testpass123"
    )


def grant_permissions(user, *codenames):
    """Grant permissions from TestAdminPermission to a user."""
    ct = ContentType.objects.get_for_model(TestAdminPermission)
    perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
    user.user_permissions.add(*perms)
    # Clear Django's permission cache
    return User.objects.get(pk=user.pk)
