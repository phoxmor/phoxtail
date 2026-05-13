"""Filters for the AccessToken admin list.

Mirrors the billing filter pattern:

- A ``"filter"`` prefix so query params don't collide with the Wagtail
  admin's own ``page`` param.
- A ``search`` method that defers to the Wagtail search backend's
  autocomplete (``AccessToken.search_fields`` declares what's indexed).
- A ``page`` no-op filter used purely to carry pagination state across
  HTMX swaps; the Paginator in the context builder consumes it.
- A dynamically-added ``user`` filter that only appears when the caller
  can manage all tokens — same self-vs-org rule that scopes the list.
"""

from __future__ import annotations

import django_filters
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from wagtail.search.backends import get_search_backend

from .models import AccessToken

User = get_user_model()
search_backend = get_search_backend()


class TokenStatus:
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"

    choices = (
        (ACTIVE, "Active"),
        (EXPIRED, "Expired"),
        (REVOKED, "Revoked"),
    )


class TokenFilter(django_filters.FilterSet):
    """Filter for AccessToken queryset with search, status, and pagination."""

    def __init__(self, *args, can_manage_all: bool = False, **kwargs):
        kwargs.setdefault("prefix", "filter")
        super().__init__(*args, **kwargs)
        # The "user" filter only makes sense when the caller can see
        # everyone's tokens. Drop it from self.form otherwise so it
        # neither renders nor counts toward filter_count.
        if not can_manage_all:
            self.filters.pop("user", None)
            self.form.fields.pop("user", None)

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search",
    )

    status = django_filters.ChoiceFilter(
        method="filter_status",
        choices=TokenStatus.choices,
        label="Status",
        empty_label="All",
    )

    user = django_filters.ModelChoiceFilter(
        field_name="user",
        queryset=User.objects.filter(access_tokens__isnull=False).distinct().order_by("email"),
        label="User",
        empty_label="All",
    )

    page = django_filters.NumberFilter(
        method="filter_page",
        label="Page",
    )

    class Meta:
        model = AccessToken
        fields = ["search", "status", "user", "page"]

    def filter_search(self, queryset, name, value):
        """Wagtail autocomplete across AccessToken.search_fields."""
        if not value:
            return queryset
        return search_backend.autocomplete(value, queryset).get_queryset().order_by("-created_at")

    def filter_status(self, queryset, name, value):
        now = timezone.now()
        if value == TokenStatus.REVOKED:
            return queryset.filter(revoked_at__isnull=False)
        if value == TokenStatus.EXPIRED:
            return queryset.filter(revoked_at__isnull=True, expires_at__lt=now)
        if value == TokenStatus.ACTIVE:
            return queryset.filter(revoked_at__isnull=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
        return queryset

    def filter_page(self, queryset, name, value):
        """No-op — pagination state only; Paginator consumes the value."""
        return queryset
