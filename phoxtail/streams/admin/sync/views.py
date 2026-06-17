"""HTMX views for the Streams Sync admin.

Capability: sync block variants from a connected Remote.
Uses phoxtail.remotes.Remote for the connection; all writes go to phoxtail.streams models.
"""

from __future__ import annotations

import math

import httpx
from django.apps import apps as django_apps
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from phoxtail.core.utils import page_range_entries
from phoxtail.remotes.models import Remote
from phoxtail.remotes.permissions import remotes_permission_required
from phoxtail.streams.models import BlockVariant
from phoxtail.streams.services.sync import StreamsSyncService

from .forms import RemoteSelectForm

_T = "phoxtail_streams/admin/sync"


def _build_streams_paginator_ctx(offset, limit, total, remote_id, q):
    """Build paginator context for the offset-based streams list."""
    if limit <= 0 or total <= limit:
        return None
    num_pages = math.ceil(total / limit)
    current_page = offset // limit + 1
    streams_url = reverse("streams-sync:streams")

    def page_url(p):
        url = f"{streams_url}?remote={remote_id}&limit={limit}&offset={(p - 1) * limit}"
        if q:
            url += f"&q={q}"
        return url

    return {
        "has_prev": offset > 0,
        "prev_url": page_url(current_page - 1) if offset > 0 else None,
        "has_next": offset + limit < total,
        "next_url": page_url(current_page + 1) if offset + limit < total else None,
        "page_range": page_range_entries(current_page, num_pages, page_url),
        "current_page": current_page,
        "num_pages": num_pages,
        "hx_target": "#streams-results",
    }


def _remote_select_field(remotes_qs=None):
    if remotes_qs is None:
        remotes_qs = Remote.objects.all()
    remotes_list = list(remotes_qs)
    auto_select = remotes_list[0] if len(remotes_list) == 1 else None
    form = RemoteSelectForm({"remote": str(auto_select.pk) if auto_select else ""})
    return form["remote"]


# ─────────────────────────────────────────────────────────────────
# Index
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_index(request):
    remotes = Remote.objects.all()
    context = {
        "remotes": remotes,
        "remote_select_field": _remote_select_field(remotes),
    }
    if getattr(request, "htmx", None):
        return render(request, f"{_T}/partials/page.html", context)
    return render(request, f"{_T}/index.html", context)


# ─────────────────────────────────────────────────────────────────
# Remote select (HTMX widget)
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_remote_select(request):
    widget_id = "remote"
    current_value = request.GET.get("remote", "")
    selection_changed = False

    select_pk = request.GET.get(f"{widget_id}_select")
    if select_pk:
        current_value = select_pk
        selection_changed = True

    if request.GET.get(f"{widget_id}_clear"):
        current_value = ""
        selection_changed = True

    mutable = request.GET.copy()
    mutable["remote"] = current_value
    form = RemoteSelectForm(mutable)
    field = form["remote"]
    selected_item = field.selected_item
    available_items = field.available_items

    search_value = request.GET.get(f"{widget_id}_search", "").strip()
    if search_value and not selection_changed:
        available_items = available_items.filter(name__icontains=search_value)

    context = {
        "field": field,
        "widget_id": widget_id,
        "selected_item": selected_item,
        "available_items": available_items,
        "search_url": reverse("streams-sync:remote_select"),
        "search_value": search_value,
        "search_placeholder": "Search remotes",
        "selected_remote": selected_item,
    }

    if not selection_changed:
        return render(
            request,
            "phoxtail_core/forms/widgets/htmx/single_select_search/results_content.html",
            context,
        )
    return render(request, f"{_T}/partials/remote_select_oob.html", context)


# ─────────────────────────────────────────────────────────────────
# Streams
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_streams(request):
    remote_id = request.GET.get("remote")
    q = request.GET.get("q", "")
    limit = min(int(request.GET.get("limit", 20)), 100)
    offset = max(int(request.GET.get("offset", 0)), 0)

    if not remote_id:
        return render(request, f"{_T}/partials/streams_results.html", {"items": [], "error": None})

    remote = get_object_or_404(Remote, pk=remote_id)

    local_app_labels = {ac.label for ac in django_apps.get_app_configs()}

    try:
        resp = httpx.get(
            f"{remote.base_url}/api/registry/v1/streams/variants/",
            headers={"Authorization": f"Bearer {remote.token}"},
            params={"q": q, "limit": limit, "offset": offset, "apps": ",".join(sorted(local_app_labels))},
            timeout=15,
            follow_redirects=True,
        )
    except Exception as exc:
        return render(
            request,
            f"{_T}/partials/streams_results.html",
            {"items": [], "error": f"Could not reach remote: {exc}", "remote_id": remote_id, "q": q},
        )

    if not resp.is_success:
        return render(
            request,
            f"{_T}/partials/streams_results.html",
            {"items": [], "error": f"Remote returned {resp.status_code}.", "remote_id": remote_id, "q": q},
        )

    data = resp.json()
    installed = set(BlockVariant.objects.values_list("block__identifier", "collection__identifier", "identifier"))
    base = remote.base_url.rstrip("/")
    items = []
    for item in data.get("items", []):
        # Secondary check: filter blocks whose page_types span uninstalled apps.
        if any(a not in local_app_labels for a in (item.get("block_page_type_apps") or [])):
            continue
        key = (item.get("block_identifier"), item.get("collection_identifier"), item.get("variant_identifier"))
        item["installed"] = key in installed
        for img_key in ("preview_desktop_light_url", "preview_desktop_dark_url"):
            url = item.get(img_key) or ""
            if url and url.startswith("/"):
                url = f"{base}{url}"
            item[img_key] = url
        items.append(item)

    total = data.get("total", 0)
    return render(
        request,
        f"{_T}/partials/streams_results.html",
        {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "remote_id": remote_id,
            "q": q,
            "error": None,
            "paginator_ctx": _build_streams_paginator_ctx(offset, limit, total, remote_id, q),
        },
    )


# ─────────────────────────────────────────────────────────────────
# Install
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_install(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    remote_id = request.POST.get("remote_id")
    variant_id = request.POST.get("variant_id")
    variant_identifier = request.POST.get("variant_identifier", "")

    remote = get_object_or_404(Remote, pk=remote_id)
    success = False

    try:
        result = StreamsSyncService(remote).install(variant_id=int(variant_id))
        if result.created:
            messages.success(request, f"Installed '{result.variant}'.")
        else:
            messages.info(request, f"'{result.variant}' was already installed.")
        success = True
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    except Exception as exc:
        messages.error(request, f"Install failed: {exc}")

    return render(
        request,
        f"{_T}/partials/sync_response.html",
        {
            "remote_id": remote_id,
            "variant_id": variant_id,
            "variant_identifier": variant_identifier,
            "success": success,
        },
    )


# ─────────────────────────────────────────────────────────────────
# Variant detail (modal drawer)
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_variant_detail(request):
    variant_id = request.GET.get("variant_id")
    remote_id = request.GET.get("remote_id")

    if not variant_id or not remote_id:
        return HttpResponseBadRequest("Missing variant_id or remote_id")

    remote = get_object_or_404(Remote, pk=remote_id)

    try:
        resp = httpx.get(
            f"{remote.base_url}/api/registry/v1/streams/variants/{variant_id}/",
            headers={"Authorization": f"Bearer {remote.token}"},
            timeout=15,
            follow_redirects=True,
        )
    except Exception as exc:
        return render(
            request,
            f"{_T}/partials/variant_detail.html",
            {"error": f"Could not reach remote: {exc}"},
        )

    if not resp.is_success:
        return render(
            request,
            f"{_T}/partials/variant_detail.html",
            {"error": f"Remote returned {resp.status_code}."},
        )

    data = resp.json()
    install = data.get("install") or {}
    block_data = install.get("block") or {}
    variant_data = install.get("variant") or {}
    collection_data = install.get("collection") or {}

    variant_identifier = variant_data.get("identifier")
    installed = (
        BlockVariant.objects.filter(
            block__identifier=block_data.get("identifier"),
            collection__identifier=collection_data.get("identifier"),
            identifier=variant_identifier,
        ).exists()
        if all([block_data.get("identifier"), collection_data.get("identifier"), variant_identifier])
        else False
    )

    base = remote.base_url.rstrip("/")
    for img_key in (
        "preview_desktop_light_url",
        "preview_desktop_dark_url",
        "preview_tablet_light_url",
        "preview_tablet_dark_url",
        "preview_mobile_light_url",
        "preview_mobile_dark_url",
    ):
        url = data.get(img_key) or ""
        if url and url.startswith("/"):
            url = f"{base}{url}"
        data[img_key] = url

    return render(
        request,
        f"{_T}/partials/variant_detail.html",
        {
            "item": data,
            "block": block_data,
            "variant": variant_data,
            "collection": collection_data,
            "variant_id": variant_id,
            "remote_id": remote_id,
            "variant_identifier": variant_identifier,
            "installed": installed,
        },
    )
