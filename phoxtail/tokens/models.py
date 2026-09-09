from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from wagtail.search import index

from phoxtail.core.mixins import AdminURLMixin, UUIDMixin

from .constants import TokenType


class AccessToken(UUIDMixin, AdminURLMixin, index.Indexed, models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_tokens",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    token_type = models.CharField(
        max_length=20,
        choices=TokenType.choices,
        default=TokenType.PERSONAL,
    )

    # First 8 characters of the raw token ("phxt_" + 3 random). Stored
    # plaintext for display ("phxt_Xf9…wOo"). Not used to narrow the auth
    # lookup — `digest` has a unique index that already makes the lookup
    # O(log n). Prefix exists so users can identify a token in the admin
    # list without ever seeing the secret again.
    prefix = models.CharField(max_length=8)

    # Last 4 characters of the raw token, stored plaintext for the same
    # display reason — lets users distinguish tokens that share a prefix.
    suffix = models.CharField(max_length=4)

    # SHA-256 hex digest of the raw token. Fast hashing is correct here:
    # the token body carries 192 bits of entropy so brute force is
    # infeasible; slow KDFs (bcrypt/argon2) exist for low-entropy passwords.
    digest = models.CharField(max_length=64, unique=True)

    # A token is either unrestricted or carries an explicit ceiling; the
    # two are mutually exclusive and the service layer enforces that.
    # There is deliberately no wildcard scope: a "*" would keep granting
    # capabilities that did not exist when the token was issued, so every
    # app installed later would silently widen every old token. A ceiling
    # that rises on its own is not a ceiling.
    unrestricted = models.BooleanField(
        default=False,
        help_text=_(
            "Let this token do anything its owner can do, including "
            "capabilities added to this site in future. Convenient for your "
            "own machine; too broad for anything you hand to a service or "
            "connect from a phone. Leave off and choose scopes instead."
        ),
    )

    # Scope vocabulary is Django permission codenames
    # ("phoxtail_streams.change_blockvariant"), so there is one vocabulary
    # to learn and none to invent. Not enforced yet; the field exists so
    # tokens created today already carry the metadata enforcement needs.
    scopes = models.JSONField(
        default=list,
        help_text=_(
            "The permissions this token may use, as codenames such as "
            "phoxtail_streams.change_blockvariant. Scopes only ever narrow: "
            "a token can never do something its owner cannot. Required "
            "unless the token is unrestricted."
        ),
    )

    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    search_fields = [
        index.AutocompleteField("name", boost=10),
        index.AutocompleteField("prefix"),
        index.AutocompleteField("suffix"),
        index.SearchField("description"),
        index.AutocompleteField("user_email", boost=5),
        index.AutocompleteField("user_username"),
        index.AutocompleteField("user_first_name"),
        index.AutocompleteField("user_last_name"),
        index.FilterField("user"),
        index.FilterField("token_type"),
        index.FilterField("unrestricted"),
        index.FilterField("revoked_at"),
        index.FilterField("expires_at"),
        index.FilterField("created_at"),
    ]

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}…{self.suffix})"

    @property
    def token_fingerprint(self) -> str:
        return f"{self.prefix}…{self.suffix}"

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at < timezone.now():
            return False
        return True

    # ── Proxy attributes for autocomplete indexing ──
    # Wagtail indexes attributes on the model itself, not joins. These
    # expose the related user's fields so a token's owner shows up in
    # autocomplete results without a runtime SQL join.
    @property
    def user_email(self) -> str:
        return self.user.email

    @property
    def user_username(self) -> str:
        return self.user.username

    @property
    def user_first_name(self) -> str:
        return self.user.first_name

    @property
    def user_last_name(self) -> str:
        return self.user.last_name
