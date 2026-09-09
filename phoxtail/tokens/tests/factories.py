import hashlib

import factory
from django.contrib.auth import get_user_model

from phoxtail.tokens.constants import TokenType
from phoxtail.tokens.models import AccessToken

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "testpass123")


class AccessTokenFactory(factory.django.DjangoModelFactory):
    """Builds an AccessToken row with a known raw token recoverable as
    ``instance._raw_token`` so tests that need to authenticate can reuse it.
    """

    class Meta:
        model = AccessToken

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Token {n}")
    description = ""
    token_type = TokenType.PERSONAL
    unrestricted = True
    scopes = factory.LazyFunction(list)
    expires_at = None
    revoked_at = None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        raw = kwargs.pop("raw_token", None) or _make_raw_token(kwargs.get("name", "tok"))
        kwargs["prefix"] = raw[:8]
        kwargs["suffix"] = raw[-4:]
        kwargs["digest"] = hashlib.sha256(raw.encode()).hexdigest()
        instance = super()._create(model_class, *args, **kwargs)
        instance._raw_token = raw
        return instance


def _make_raw_token(seed: str) -> str:
    # Deterministic-but-unique raw token — only used in tests.
    body = hashlib.sha256(seed.encode()).hexdigest()[:32]
    return f"phxt_AAA{body}"
