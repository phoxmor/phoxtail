"""Context builders for the access-tokens admin views.

Mirrors the billing context builder: extracts query params, builds a
filterset, counts active filters (excluding ``page``/``search``), then
paginates. Self-vs-org scoping is still enforced here — a caller sees
only their own tokens unless they hold ``manage_all_tokens``.
"""

from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest

from ..filters import TokenFilter
from ..models import AccessToken
from ..permissions import access_tokens_permission_policy

PAGE_SIZE = 12


class AccessTokensContextBuilder:
    """Builds context for the access-tokens list and filter views."""

    def __init__(self, request: HttpRequest):
        self.request = request
        self.query_params = None
        self.filterset = None
        self.filter_count = None

    # ── Permission helpers ──
    def _can_manage_all(self) -> bool:
        return access_tokens_permission_policy.user_has_permission(
            self.request.user, "manage_all_tokens"
        )

    def _can_create(self) -> bool:
        return access_tokens_permission_policy.user_has_permission(
            self.request.user, "create_access_tokens"
        )

    def _can_revoke(self) -> bool:
        return access_tokens_permission_policy.user_has_permission(
            self.request.user, "revoke_access_tokens"
        )

    # ── Filter / pagination pipeline ──
    def _extract_query_params(self):
        self.query_params = (
            self.request.GET.copy()
            if self.request.method == "GET"
            else self.request.POST.copy()
        )

    def _create_filterset(self, base_queryset):
        self.filterset = TokenFilter(
            self.query_params,
            queryset=base_queryset,
            can_manage_all=self._can_manage_all(),
        )

    def _calculate_filter_count(self):
        form = self.filterset.form
        form.is_valid()

        filter_keys = [k for k in form.cleaned_data if k not in ["page", "search"]]
        self.filter_count = sum(
            1
            for k, v in form.cleaned_data.items()
            if k in filter_keys and v not in ["", None]
        )

    def _prepare_base_context(self, base_queryset):
        self._extract_query_params()
        self._create_filterset(base_queryset)
        self._calculate_filter_count()

    def _build_token_queryset(self):
        qs = AccessToken.objects.select_related("user").order_by("-created_at")
        if not self._can_manage_all():
            qs = qs.filter(user=self.request.user)
        return qs

    def _extract_page_number(self):
        page = self.filterset.form.cleaned_data.get("page")
        return page if page else 1

    # ── Public builders ──
    def build_filters_context(self):
        """Lightweight context for the filters modal only."""
        self._prepare_base_context(base_queryset=AccessToken.objects.none())
        return {
            "filterset": self.filterset,
            "filter_count": self.filter_count,
            "can_manage_all": self._can_manage_all(),
        }

    def build_full_context(self):
        """Complete list context: filterset + paginated tokens + perms."""
        base_queryset = self._build_token_queryset()
        self._prepare_base_context(base_queryset)
        self.filterset.form.is_valid()

        tokens = self.filterset.qs
        page_number = self._extract_page_number()
        paginator = Paginator(tokens, PAGE_SIZE)

        return {
            "tokens": paginator.get_page(page_number),
            "filterset": self.filterset,
            "total_tokens": base_queryset.count(),
            "filter_count": self.filter_count,
            "can_manage_all": self._can_manage_all(),
            "can_create": self._can_create(),
            "can_revoke": self._can_revoke(),
        }

    @classmethod
    def get_filters_context(cls, request: HttpRequest):
        return cls(request).build_filters_context()

    @classmethod
    def get_full_context(cls, request: HttpRequest):
        return cls(request).build_full_context()


def can_user_revoke(request, token: AccessToken) -> bool:
    """Does ``request.user`` have authority to revoke ``token``?

    Rule: revoking *your own* token needs ``revoke_access_tokens``;
    revoking *someone else's* additionally needs ``manage_all_tokens``.
    """
    has_revoke = access_tokens_permission_policy.user_has_permission(
        request.user, "revoke_access_tokens"
    )
    if not has_revoke:
        return False
    if token.user_id == request.user.id:
        return True
    return access_tokens_permission_policy.user_has_permission(
        request.user, "manage_all_tokens"
    )
