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

from phoxtail.api.streams.v1._helpers import (
    canonical_content_parts,
    variant_content_hash,
)
from phoxtail.core.utils import page_range_entries
from phoxtail.remotes.models import Remote
from phoxtail.remotes.permissions import remotes_permission_required
from phoxtail.streams.models import BlockVariant
from phoxtail.streams.services.sync import StreamsSyncService
from phoxtail.streams.utils import _image_url

from .forms import RemoteSelectForm, SyncModeForm

_T = "phoxtail_streams/admin/sync"
_DEFAULT_LIMIT = 12


def _build_streams_paginator_ctx(offset, limit, total, remote_id, q, mode="remote"):
    """Build paginator context for the offset-based streams list."""
    if limit <= 0 or total <= limit:
        return None
    num_pages = math.ceil(total / limit)
    current_page = offset // limit + 1
    streams_url = reverse("streams-sync:streams")

    def page_url(p):
        url = f"{streams_url}?remote={remote_id}&limit={limit}&offset={(p - 1) * limit}&mode={mode}"
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
    field = form["remote"]
    field._auto_select = auto_select
    return field


def _mode_field(mode: str):
    form = SyncModeForm({"sync_toggle": mode == "local"})
    return form["sync_toggle"]


def _variant_differs(local_v, remote_variant_data: dict) -> bool:
    """Binary content diff between a local variant and a remote pull-envelope dict."""
    local_parts = canonical_content_parts(
        local_v.name,
        local_v.description,
        local_v.is_default,
        local_v.html,
        local_v.css,
        local_v.javascript,
    )
    remote_parts = canonical_content_parts(
        remote_variant_data.get("name") or "",
        remote_variant_data.get("description") or "",
        bool(remote_variant_data.get("is_default", False)),
        remote_variant_data.get("html") or "",
        remote_variant_data.get("css") or "",
        remote_variant_data.get("js") or "",
    )
    return local_parts != remote_parts


# ─────────────────────────────────────────────────────────────────
# Index
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_index(request):
    remotes = Remote.objects.all()
    remote_select_field = _remote_select_field(remotes)
    has_selected_remote = bool(getattr(remote_select_field, "_auto_select", None))
    no_remotes = not remotes.exists()
    locked_local = not has_selected_remote
    mode = request.GET.get("mode", "local" if locked_local else "remote")
    context = {
        "remotes": remotes,
        "remote_select_field": remote_select_field,
        "mode_field": _mode_field(mode),
        "mode": mode,
        "no_remotes": no_remotes,
        "locked_local": locked_local,
        "has_selected_remote": has_selected_remote,
        "skeleton_range": range(_DEFAULT_LIMIT),
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
        "mode_field": _mode_field("remote" if selected_item else "local"),
        "locked_local": not bool(selected_item),
        "skeleton_range": range(_DEFAULT_LIMIT),
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
    from wagtail.search.backends import get_search_backend

    remote_id = request.GET.get("remote")
    q = request.GET.get("q", "")
    mode = request.GET.get("mode", "remote")
    limit = min(int(request.GET.get("limit", _DEFAULT_LIMIT)), 100)
    offset = max(int(request.GET.get("offset", 0)), 0)

    if not remote_id or mode == "local":
        # Browse local variants.
        qs = BlockVariant.objects.select_related(
            "block",
            "collection",
            "preview_image_desktop",
            "preview_image_desktop_dark",
        ).all()
        if q:
            qs = get_search_backend().autocomplete(q, qs)

        # When a remote is selected, fetch its variant list once to build a
        # hash map for card-level sync state — zero per-card calls.
        remote_hash_map: dict = {}
        remote_error = None
        if remote_id:
            try:
                remote = get_object_or_404(Remote, pk=remote_id)
                rresp = httpx.get(
                    f"{remote.base_url}/api/streams/v1/variants/",
                    headers={"Authorization": f"Bearer {remote.token}"},
                    timeout=15,
                    follow_redirects=True,
                )
                if rresp.is_success:
                    for rv in rresp.json().get("variants", []):
                        rb = rv["block"]
                        rc = rv.get("collection") or {}
                        rkey = (rb["identifier"], rc.get("identifier"), rv["identifier"])
                        remote_hash_map[rkey] = rv.get("content_hash") or ""
                else:
                    remote_error = "Could not reach remote — sync states unavailable."
            except Exception:
                remote_error = "Could not reach remote — sync states unavailable."

        all_items = []
        for v in qs:
            key = (v.block.identifier, v.collection.identifier if v.collection_id else None, v.identifier)
            if not remote_id or remote_error:
                sync_state = None
            else:
                remote_hash = remote_hash_map.get(key)
                local_hash = variant_content_hash(v)
                if key not in remote_hash_map:
                    sync_state = "not_remote"
                elif remote_hash and local_hash == remote_hash:
                    sync_state = "in_sync"
                elif remote_hash:
                    sync_state = "differs"
                else:
                    sync_state = None
            all_items.append(
                {
                    "id": v.id,
                    "title": v.name,
                    "block_name": v.block.name,
                    "sync_state": sync_state,
                    "preview_desktop_light_url": _image_url(v.preview_image_desktop) or "",
                    "preview_desktop_dark_url": _image_url(v.preview_image_desktop_dark) or "",
                }
            )

        total = len(all_items)
        items = all_items[offset : offset + limit]
        return render(
            request,
            f"{_T}/partials/streams_results.html",
            {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "remote_id": remote_id or "",
                "q": q,
                "mode": "local",
                "remote_warning": remote_error,
                "paginator_ctx": _build_streams_paginator_ctx(offset, limit, total, remote_id or "", q, mode="local"),
            },
        )

    # mode == "remote" — browse remote variants.
    remote = get_object_or_404(Remote, pk=remote_id)
    try:
        params = {"search": q} if q else {}
        resp = httpx.get(
            f"{remote.base_url}/api/streams/v1/variants/",
            headers={"Authorization": f"Bearer {remote.token}"},
            params=params,
            timeout=15,
            follow_redirects=True,
        )
    except Exception as exc:
        return render(
            request,
            f"{_T}/partials/streams_results.html",
            {"items": [], "error": f"Could not reach remote: {exc}", "remote_id": remote_id, "q": q, "mode": "remote"},
        )

    if not resp.is_success:
        return render(
            request,
            f"{_T}/partials/streams_results.html",
            {
                "items": [],
                "error": f"Remote returned {resp.status_code}.",
                "remote_id": remote_id,
                "q": q,
                "mode": "remote",
            },
        )

    data = resp.json()
    local_app_labels = {ac.label for ac in django_apps.get_app_configs()}
    local_hash_map = {
        (v.block.identifier, v.collection.identifier if v.collection_id else None, v.identifier): variant_content_hash(
            v
        )
        for v in BlockVariant.objects.select_related("block", "collection").all()
    }
    all_items = []
    for v in data.get("variants", []):
        block = v["block"]
        # Skip variants whose block requires apps not installed in this project.
        page_type_apps = {pt.rsplit(".", 1)[0] for pt in block.get("page_types", []) if "." in pt}
        source_app = block.get("source_app", "")
        required_apps = page_type_apps | ({source_app} if source_app else set())
        if required_apps - local_app_labels:
            continue
        coll = v.get("collection") or {}
        key = (block["identifier"], coll.get("identifier"), v["identifier"])
        local_hash = local_hash_map.get(key)
        remote_hash = v.get("content_hash")
        if local_hash is None:
            sync_state = "not_local"
        elif remote_hash and local_hash == remote_hash:
            sync_state = "in_sync"
        elif remote_hash:
            sync_state = "differs"
        else:
            sync_state = None
        all_items.append(
            {
                "id": v["id"],
                "title": v["name"],
                "block_name": block["name"],
                "sync_state": sync_state,
                "preview_desktop_light_url": v.get("preview_desktop_light_url") or "",
                "preview_desktop_dark_url": v.get("preview_desktop_dark_url") or "",
            }
        )

    total = len(all_items)
    items = all_items[offset : offset + limit]
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
            "mode": "remote",
            "error": None,
            "paginator_ctx": _build_streams_paginator_ctx(offset, limit, total, remote_id, q, mode="remote"),
        },
    )


# ─────────────────────────────────────────────────────────────────
# Pull
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_pull(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    remote_id = request.POST.get("remote_id")
    variant_id = request.POST.get("variant_id")
    local_variant_id = request.POST.get("local_variant_id")
    mode = request.POST.get("mode", "remote")

    remote = get_object_or_404(Remote, pk=remote_id)
    success = False
    variant_name = ""

    try:
        result = StreamsSyncService(remote).pull(variant_id=int(variant_id))
        variant_name = result.variant.name
        messages.success(request, f"Pulled '{variant_name}'.")
        success = True
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    except Exception as exc:
        messages.error(request, f"Pull failed: {exc}")

    # In local mode the card is keyed by the local PK; in remote mode by the remote PK.
    card_variant_id = local_variant_id if (mode == "local" and local_variant_id) else variant_id

    return render(
        request,
        f"{_T}/partials/sync_response.html",
        {
            "remote_id": remote_id,
            "variant_id": variant_id,
            "card_variant_id": card_variant_id,
            "variant_name": variant_name,
            "mode": mode,
            "success": success,
        },
    )


# ─────────────────────────────────────────────────────────────────
# Push
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_push(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    remote_id = request.POST.get("remote_id")
    variant_id = request.POST.get("variant_id")
    remote_variant_id = request.POST.get("remote_variant_id")
    mode = request.POST.get("mode", "remote")

    remote = get_object_or_404(Remote, pk=remote_id)
    success = False
    variant_name = ""

    try:
        result = StreamsSyncService(remote).push(variant_id=int(variant_id))
        variant_name = result.variant_name
        messages.success(request, f"Pushed '{variant_name}' to remote.")
        success = True
    except ValidationError as exc:
        for message in exc.messages:
            messages.error(request, message)
    except Exception as exc:
        messages.error(request, f"Push failed: {exc}")

    # In remote mode the card is keyed by the remote PK; in local mode by the local PK.
    card_variant_id = remote_variant_id if (mode == "remote" and remote_variant_id) else variant_id

    return render(
        request,
        f"{_T}/partials/push_response.html",
        {
            "remote_id": remote_id,
            "variant_id": variant_id,
            "card_variant_id": card_variant_id,
            "variant_name": variant_name,
            "mode": mode,
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
    mode = request.GET.get("mode", "remote")

    if not variant_id:
        return HttpResponseBadRequest("Missing variant_id")

    if mode == "local" and not remote_id:
        v = get_object_or_404(
            BlockVariant.objects.select_related(
                "block",
                "collection",
                "preview_image_desktop",
                "preview_image_desktop_dark",
                "preview_image_tablet",
                "preview_image_tablet_dark",
                "preview_image_mobile",
                "preview_image_mobile_dark",
            ),
            pk=variant_id,
        )
        return render(
            request,
            f"{_T}/partials/variant_detail.html",
            {
                "item": {"title": v.name, "description": v.description},
                "block": {"name": v.block.name, "identifier": v.block.identifier},
                "collection": {"name": v.collection.name} if v.collection_id else None,
                "variant_id": variant_id,
                "remote_id": "",
                "sync_state": None,
                "remote_variant_id": None,
                "local_variant_id": v.pk,
                "mode": mode,
                "preview_images": {
                    "desktop_light": _image_url(v.preview_image_desktop),
                    "desktop_dark": _image_url(v.preview_image_desktop_dark),
                    "tablet_light": _image_url(v.preview_image_tablet),
                    "tablet_dark": _image_url(v.preview_image_tablet_dark),
                    "mobile_light": _image_url(v.preview_image_mobile),
                    "mobile_dark": _image_url(v.preview_image_mobile_dark),
                },
            },
        )

    if not remote_id:
        return HttpResponseBadRequest("Missing remote_id")

    remote = get_object_or_404(Remote, pk=remote_id)

    if mode == "local":
        # variant_id is a local BlockVariant PK.
        v = get_object_or_404(
            BlockVariant.objects.select_related(
                "block",
                "collection",
                "preview_image_desktop",
                "preview_image_desktop_dark",
                "preview_image_tablet",
                "preview_image_tablet_dark",
                "preview_image_mobile",
                "preview_image_mobile_dark",
            ),
            pk=variant_id,
        )
        local_variant_id = v.pk
        remote_variant_id = None
        sync_state = "not_remote"

        try:
            _params: dict = {"block": v.block.identifier}
            if v.collection_id:
                _params["collection"] = v.collection.identifier
            list_resp = httpx.get(
                f"{remote.base_url}/api/streams/v1/variants/",
                headers={"Authorization": f"Bearer {remote.token}"},
                params=_params,
                timeout=15,
                follow_redirects=True,
            )
            if list_resp.is_success:
                for rv in list_resp.json().get("variants", []):
                    if rv["identifier"] == v.identifier:
                        remote_variant_id = rv["id"]
                        break
            else:
                sync_state = "unknown"

            if remote_variant_id is not None and sync_state != "unknown":
                pull_resp = httpx.get(
                    f"{remote.base_url}/api/streams/v1/variants/{remote_variant_id}/pull/",
                    headers={"Authorization": f"Bearer {remote.token}"},
                    timeout=15,
                    follow_redirects=True,
                )
                if pull_resp.is_success:
                    remote_variant_data = pull_resp.json().get("install", {}).get("variant") or {}
                    sync_state = "differs" if _variant_differs(v, remote_variant_data) else "in_sync"
                else:
                    sync_state = "unknown"
        except Exception:
            sync_state = "unknown"
            remote_variant_id = None

        return render(
            request,
            f"{_T}/partials/variant_detail.html",
            {
                "item": {"title": v.name, "description": v.description},
                "block": {"name": v.block.name, "identifier": v.block.identifier},
                "collection": {"name": v.collection.name} if v.collection_id else None,
                "variant_id": variant_id,
                "remote_id": remote_id,
                "sync_state": sync_state,
                "remote_variant_id": remote_variant_id,
                "local_variant_id": local_variant_id,
                "mode": mode,
                "preview_images": {
                    "desktop_light": _image_url(v.preview_image_desktop),
                    "desktop_dark": _image_url(v.preview_image_desktop_dark),
                    "tablet_light": _image_url(v.preview_image_tablet),
                    "tablet_dark": _image_url(v.preview_image_tablet_dark),
                    "mobile_light": _image_url(v.preview_image_mobile),
                    "mobile_dark": _image_url(v.preview_image_mobile_dark),
                },
            },
        )

    # mode == "remote" — variant_id is the remote's numeric PK.
    try:
        resp = httpx.get(
            f"{remote.base_url}/api/streams/v1/variants/{variant_id}/pull/",
            headers={"Authorization": f"Bearer {remote.token}"},
            timeout=15,
            follow_redirects=True,
        )
    except Exception as exc:
        return render(request, f"{_T}/partials/variant_detail.html", {"error": f"Could not reach remote: {exc}"})

    if not resp.is_success:
        return render(request, f"{_T}/partials/variant_detail.html", {"error": f"Remote returned {resp.status_code}."})

    data = resp.json()
    install = data.get("install") or {}
    block_data = install.get("block") or {}
    variant_data = install.get("variant") or {}
    collection_data = install.get("collection") or {}

    variant_identifier = variant_data.get("identifier")

    local_v = None
    if block_data.get("identifier") and variant_identifier:
        try:
            if collection_data and collection_data.get("identifier"):
                local_v = BlockVariant.objects.get(
                    block__identifier=block_data["identifier"],
                    collection__identifier=collection_data["identifier"],
                    identifier=variant_identifier,
                )
            else:
                local_v = BlockVariant.objects.get(
                    block__identifier=block_data["identifier"],
                    collection__isnull=True,
                    identifier=variant_identifier,
                )
        except BlockVariant.DoesNotExist:
            pass

    if local_v is None:
        sync_state = "not_local"
        local_variant_id = None
    else:
        local_variant_id = local_v.pk
        sync_state = "differs" if _variant_differs(local_v, variant_data) else "in_sync"

    return render(
        request,
        f"{_T}/partials/variant_detail.html",
        {
            "item": data,
            "block": block_data,
            "collection": collection_data,
            "variant_id": variant_id,
            "remote_id": remote_id,
            "sync_state": sync_state,
            "remote_variant_id": int(variant_id),
            "local_variant_id": local_variant_id,
            "mode": mode,
            "preview_images": {
                "desktop_light": variant_data.get("preview_desktop_light_url") or None,
                "desktop_dark": variant_data.get("preview_desktop_dark_url") or None,
                "tablet_light": variant_data.get("preview_tablet_light_url") or None,
                "tablet_dark": variant_data.get("preview_tablet_dark_url") or None,
                "mobile_light": variant_data.get("preview_mobile_light_url") or None,
                "mobile_dark": variant_data.get("preview_mobile_dark_url") or None,
            },
        },
    )
