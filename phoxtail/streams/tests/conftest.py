import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from phoxtail.streams.permissions import StreamsAdminPermission

from .factories import (
    BlockFactory,
    BlockSystemPromptFactory,
    BlockVariantFactory,
    VariantCollectionFactory,
)

User = get_user_model()


def grant_studio_access(user):
    """Grant access_stream_studio permission to a user."""
    ct = ContentType.objects.get_for_model(StreamsAdminPermission)
    perm, _ = Permission.objects.get_or_create(
        content_type=ct,
        codename="access_stream_studio",
        defaults={"name": "Can access the Stream Studio"},
    )
    user.user_permissions.add(perm)
    return User.objects.get(pk=user.pk)


@pytest.fixture
def user():
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def studio_user(user):
    return grant_studio_access(user)


@pytest.fixture
def superuser():
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="testpass123"
    )


@pytest.fixture
def block():
    return BlockFactory()


@pytest.fixture
def collection():
    return VariantCollectionFactory()


@pytest.fixture
def variant(block, collection):
    return BlockVariantFactory(block=block, collection=collection)


@pytest.fixture
def system_prompt():
    return BlockSystemPromptFactory()
