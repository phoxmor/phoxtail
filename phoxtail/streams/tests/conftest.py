import pytest
from django.contrib.auth import get_user_model

from .factories import (
    BlockFactory,
    BlockVariantFactory,
    VariantCollectionFactory,
)

User = get_user_model()


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


@pytest.fixture
def block():
    return BlockFactory()


@pytest.fixture
def collection():
    return VariantCollectionFactory()


@pytest.fixture
def variant(block, collection):
    return BlockVariantFactory(block=block, collection=collection)
