"""HTMX views for the access-tokens admin.

Follows the booking admin pattern: FBVs decorated with a policy-aware
``permission_required`` helper, partials rendered for HTMX modal swaps,
OOB swaps for the list + messages, and dedicated ``form_response``
templates so the same view works on both success and validation failure.

Security-relevant details, inlined where they matter:

- The raw token is only ever returned in the direct HTTP response to the
  creating POST. It is never stored in Django messages, never cached by
  proxies (``Cache-Control: no-store``), and never indexed
  (``X-Robots-Tag: noindex``).
- Revoke authorization is enforced *per token* in :func:`can_user_revoke`
  — having ``revoke_access_tokens`` lets you revoke your own tokens;
  revoking someone else's additionally requires ``manage_all_tokens``.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from ..models import AccessToken
from ..permissions import (
    access_tokens_permission_policy,
    access_tokens_permission_required,
)
from ..services import AccessTokenService
from .forms import AccessTokenCreateForm
from .utils import AccessTokensContextBuilder, can_user_revoke

_TEMPLATE_ROOT = "phoxtail_tokens/admin"


# ─────────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────────
@access_tokens_permission_required("access_tokens_management")
def admin_tokens_list_view(request):
    context = AccessTokensContextBuilder.get_full_context(request)
    context["is_htmx_request"] = bool(request.htmx)

    if context["is_htmx_request"]:
        return render(request, f"{_TEMPLATE_ROOT}/partials/tokens.html", context)

    return render(request, f"{_TEMPLATE_ROOT}/index.html", context)


# ─────────────────────────────────────────────────────────────────
# Filters / search (HTMX-driven list refresh)
# ─────────────────────────────────────────────────────────────────
@access_tokens_permission_required("access_tokens_management")
def admin_tokens_filters_form_view(request):
    """Render the filters modal (filter fields only)."""
    context = AccessTokensContextBuilder.get_filters_context(request)
    return render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/filters/form.html",
        context,
    )


@access_tokens_permission_required("access_tokens_management")
def admin_tokens_filters_view(request):
    """Apply filter changes and OOB-swap the list + filters form."""
    context = AccessTokensContextBuilder.get_full_context(request)
    return render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/filters/form_response.html",
        context,
    )


@access_tokens_permission_required("access_tokens_management")
def admin_tokens_search_view(request):
    """Apply a search-input change and OOB-swap the list."""
    context = AccessTokensContextBuilder.get_full_context(request)
    return render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/search/form_response.html",
        context,
    )


# ─────────────────────────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────────────────────────
@access_tokens_permission_required("access_tokens_management", "create_access_tokens")
def admin_token_create_form_view(request):
    """Return the create-token drawer (GET only)."""
    form = AccessTokenCreateForm()
    return render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/create/form.html",
        {"form": form},
    )


@access_tokens_permission_required("access_tokens_management", "create_access_tokens")
def admin_token_create_view(request):
    """Handle the create-token submission.

    On success: swap the drawer out for a one-shot **reveal** drawer that
    displays the raw token, and refresh the list OOB. On failure: swap
    the drawer back to the form with errors.
    """
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    form = AccessTokenCreateForm(request.POST)
    list_context = AccessTokensContextBuilder.get_full_context(request)
    created = False
    raw_token = None
    token = None

    if form.is_valid():
        try:
            token, raw_token = AccessTokenService().admin.create(
                user_id=request.user.id,
                name=form.cleaned_data["name"],
                description=form.cleaned_data["description"],
                scopes=form.cleaned_data["scopes"],
                unrestricted=form.cleaned_data["unrestricted"],
                expires_at=form.cleaned_data["expires_at"],
            )
            created = True
            messages.success(request, f"Token '{token.name}' created.")
            list_context = AccessTokensContextBuilder.get_full_context(request)
        except ValidationError as exc:
            for msg in exc.messages:
                messages.error(request, msg)
    else:
        for errs in form.errors.values():
            for err in errs:
                messages.error(request, err)

    context = {
        **list_context,
        "form": form,
        "created": created,
        "raw_token": raw_token,
        "token": token,
    }

    response = render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/create/form_response.html",
        context,
    )
    if created:
        # The response body contains the *only* copy of the raw token
        # that will ever leave the server. Block every caching surface we
        # can name — intermediate proxies, browser back/forward cache,
        # search indexers — so that copy does not outlive the page view.
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response["Pragma"] = "no-cache"
        response["X-Robots-Tag"] = "noindex, nofollow"
    return response


# ─────────────────────────────────────────────────────────────────
# Detail
# ─────────────────────────────────────────────────────────────────
@access_tokens_permission_required("access_tokens_management")
def admin_token_detail_form_view(request, token_id):
    """Return the token detail drawer (GET only)."""
    token = get_object_or_404(AccessToken, uuid=token_id)
    return render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/detail/form.html",
        {
            "token": token,
            "can_revoke": can_user_revoke(request, token),
            "can_manage_all": access_tokens_permission_policy.user_has_permission(request.user, "manage_all_tokens"),
        },
    )


# ─────────────────────────────────────────────────────────────────
# Revoke
# ─────────────────────────────────────────────────────────────────
@access_tokens_permission_required("access_tokens_management", "revoke_access_tokens")
def admin_token_revoke_form_view(request, token_id):
    """Return the revoke-confirmation modal (GET only)."""
    token = get_object_or_404(AccessToken, uuid=token_id)
    if not can_user_revoke(request, token):
        return HttpResponse("Forbidden", status=403)

    return render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/revoke/form.html",
        {"token": token},
    )


@access_tokens_permission_required("access_tokens_management", "revoke_access_tokens")
def admin_token_revoke_view(request, token_id):
    """Revoke the given token. POST only. Idempotent."""
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    token = get_object_or_404(AccessToken, uuid=token_id)
    if not can_user_revoke(request, token):
        return HttpResponse("Forbidden", status=403)

    AccessTokenService(token=token).admin.revoke()
    messages.success(request, f"Token '{token.name}' revoked.")

    context = AccessTokensContextBuilder.get_full_context(request)
    return render(
        request,
        f"{_TEMPLATE_ROOT}/partials/forms/revoke/form_response.html",
        context,
    )
