import factory
from django.contrib.auth import get_user_model

from phoxtail.streams.models import (
    Block,
    BlockVariant,
    VariantCollection,
)

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class BlockFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Block

    name = factory.Sequence(lambda n: f"Block {n}")
    identifier = factory.Sequence(lambda n: f"block_{n}")
    description = factory.Faker("sentence")
    sort_order = factory.Sequence(lambda n: n)


class VariantCollectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VariantCollection

    name = factory.Sequence(lambda n: f"Collection {n}")
    identifier = factory.Sequence(lambda n: f"collection_{n}")
    description = factory.Faker("sentence")


class BlockVariantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BlockVariant

    block = factory.SubFactory(BlockFactory)
    collection = factory.SubFactory(VariantCollectionFactory)
    name = factory.Sequence(lambda n: f"Variant {n}")
    identifier = factory.Sequence(lambda n: f"variant_{n}")
    description = factory.Faker("sentence")
    html = "<div>{{ value.title }}</div>"
    css = ""
    javascript = ""
