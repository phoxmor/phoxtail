"""HTMX views for the Streams Sync admin.

Capability: sync block variants from a connected Remote.
Uses phoxtail.remotes.Remote for the connection; all writes go to phoxtail.streams models.
"""

from __future__ import annotations

import httpx
from django.apps import apps as django_apps
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext_lazy as _

from phoxtail.core.htmx import changed
from phoxtail.core.paging import ListChanged, NotAPagedList, every_item
from phoxtail.core.views import SingleSelectSearchView
from phoxtail.remotes.models import Remote
from phoxtail.remotes.permissions import RemotesPermissionMixin, remotes_permission_required
from phoxtail.streams.api.v1._helpers import (
    build_variant_envelope,
    canonical_content_parts,
    schema_fingerprint,
    variant_content_hash,
)
from phoxtail.streams.models import BlockVariant
from phoxtail.streams.services.sync import StreamsSyncService
from phoxtail.streams.utils import _image_url

from .forms import DEVICES, PreviewForm, RemoteSelectForm, SyncModeForm, SyncSearchForm

_T = "phoxtail_streams/admin/sync"
_DEFAULT_LIMIT = 12
# How a variant stands against the remote, in the words of the list's cards.
_STATES = {
    "not_local": _("New"),
    "not_remote": _("New"),
    "in_sync": _("Synced"),
    "differs": _("Unsynced"),
    "unknown": _("Unreachable"),
}
_PREVIEWS = tuple(
    f"preview_image_{device}{suffix}" for device in ("desktop", "tablet", "mobile") for suffix in ("", "_dark")
)


def _remote_variants(remote: Remote, **filters) -> list[dict]:
    """Every variant *remote* lists under *filters*, read page by page.

    Raises on anything short of the whole list — a failed request, a list
    that moved while it was read, an answer that is not a paged list — so
    no sync state is ever decided from part of it.
    """

    def fetch(params: dict) -> dict:
        response = httpx.get(
            f"{remote.base_url}/api/streams/v1/variants/",
            headers={"Authorization": f"Bearer {remote.token}"},
            params={key: value for key, value in params.items() if value is not None},
            timeout=15,
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.json()

    return every_item(fetch, **filters)


def _unreadable(exc: Exception) -> str:
    """Why a remote's variants could not be read, in words for the page."""
    if isinstance(exc, NotAPagedList):
        return "The remote runs an older phoxtail that does not page its lists; upgrade it to sync with it."
    if isinstance(exc, ListChanged):
        return "The remote's variants changed while they were being read; try again."
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Remote returned {exc.response.status_code}."
    return f"Could not reach remote: {exc}"


def _remote_select_field(remotes_qs=None):
    if remotes_qs is None:
        remotes_qs = Remote.objects.all()
    remotes_list = list(remotes_qs)
    auto_select = remotes_list[0] if len(remotes_list) == 1 else None
    form = RemoteSelectForm({"remote": str(auto_select.pk) if auto_select else ""})
    field = form["remote"]
    field._auto_select = auto_select
    return field


def _mode_field(mode: str, locked: bool):
    form = SyncModeForm(initial={"mode": mode})
    form.fields["mode"].disabled = locked
    return form["mode"]


def _previews(variant: dict) -> tuple[list[dict], PreviewForm | None]:
    """A variant's preview pictures, device by device, and the form that picks one; none, None."""
    images = [
        {"device": device, "theme": theme, "url": variant[f"preview_{device}_{theme}_url"]}
        for device in DEVICES
        for theme in ("light", "dark")
        if variant.get(f"preview_{device}_{theme}_url")
    ]
    if not images:
        return [], None
    devices = list(dict.fromkeys(image["device"] for image in images))
    return images, PreviewForm(devices, images[0]["theme"])


def _local_variant(pk) -> BlockVariant:
    """A local variant with what its install envelope reads."""
    return get_object_or_404(
        BlockVariant.objects.select_related("block", "collection", *_PREVIEWS).prefetch_related("block__page_types"),
        pk=pk,
    )


def _render_detail(request, install: dict, remote=None, sync_state=None, **context):
    """The variant drawer: the variant, its block, how it stands, its previews, Pull and Push."""
    variant = install.get("variant") or {}
    context["preview_list"], context["preview_form"] = _previews(variant)
    context |= {
        "variant": variant,
        # Not "block": the {% block %} tag puts its own name there.
        "variant_block": install.get("block") or {},
        "collection": install.get("collection") or {},
        "remote": remote,
        "remote_id": remote.pk if remote else "",
        "sync_state": sync_state,
        "state": _STATES.get(sync_state, ""),
    }
    return render(request, f"{_T}/partials/variant_detail.html", context)


def _detail_error(request, error: str):
    """The variant drawer when the remote could not answer for it."""
    return render(request, f"{_T}/partials/variant_detail.html", {"error": error})


def _variant_differs(local_v, remote_variant_data: dict, remote_block_data: dict) -> bool:
    """Binary content diff between a local variant and a remote pull-envelope dict."""
    local_schema_json = schema_fingerprint(local_v.block.schema.get_prep_value())
    remote_schema_json = schema_fingerprint(remote_block_data.get("schema_json") or [])
    local_parts = canonical_content_parts(
        local_v.name,
        local_v.description,
        local_v.is_default,
        local_v.html,
        local_v.css,
        local_v.javascript,
        local_schema_json,
    )
    remote_parts = canonical_content_parts(
        remote_variant_data.get("name") or "",
        remote_variant_data.get("description") or "",
        bool(remote_variant_data.get("is_default", False)),
        remote_variant_data.get("html") or "",
        remote_variant_data.get("css") or "",
        remote_variant_data.get("js") or "",
        remote_schema_json,
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
    default_mode = "local" if locked_local else "remote"
    mode = request.GET.get("mode", default_mode)
    if not SyncModeForm.base_fields["mode"].valid_value(mode):
        mode = default_mode
    context = {
        "remotes": remotes,
        "remote_select_field": remote_select_field,
        "mode_field": _mode_field(mode, locked_local),
        "mode": mode,
        "no_remotes": no_remotes,
        "locked_local": locked_local,
        "has_selected_remote": has_selected_remote,
        "search_form": SyncSearchForm(),
        "skeleton_range": range(_DEFAULT_LIMIT),
    }
    if getattr(request, "htmx", None):
        return render(request, f"{_T}/partials/page.html", context)
    return render(request, f"{_T}/index.html", context)


# ─────────────────────────────────────────────────────────────────
# Remote select (HTMX widget)
# ─────────────────────────────────────────────────────────────────


class RemoteSelectView(RemotesPermissionMixin, SingleSelectSearchView):
    required_permissions = ["manage_remotes"]
    form_class = RemoteSelectForm
    field_name = "remote"
    search_url_name = "streams-sync:remote_select"
    oob_response_template = f"{_T}/partials/remote_select_oob.html"

    def get_extra_context(self, form):
        selected = form["remote"].selected_item
        return {
            "search_placeholder": "Search remotes",
            "trigger_placeholder": "Select remote",
            "selected_remote": selected,
            "mode_field": _mode_field("remote" if selected else "local", not selected),
            "locked_local": not selected,
            "skeleton_range": range(_DEFAULT_LIMIT),
        }


# ─────────────────────────────────────────────────────────────────
# Streams
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_streams(request):
    from wagtail.search.backends import get_search_backend

    remote_id = request.GET.get("remote")
    mode = request.GET.get("mode", "remote")
    search_form = SyncSearchForm(request.GET)
    search_form.is_valid()
    q = search_form.cleaned_data.get("search", "").strip()
    page_number = search_form.cleaned_data.get("page")

    def answer(items=(), **context):
        """The list redrawn out of band, its search box (with the count) too."""
        page = Paginator(list(items), _DEFAULT_LIMIT).get_page(page_number)
        context |= {"page": page, "search_form": search_form, "remote_id": remote_id or "", "q": q, "mode": mode}
        return render(request, f"{_T}/partials/streams_response.html", context)

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
                for rv in _remote_variants(remote):
                    rb = rv["block"]
                    rc = rv.get("collection") or {}
                    rkey = (rb["identifier"], rc.get("identifier"), rv["identifier"])
                    remote_hash_map[rkey] = rv.get("content_hash") or ""
            except (ListChanged, NotAPagedList) as exc:
                remote_error = f"{_unreadable(exc)} Sync states unavailable."
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

        mode = "local"
        return answer(all_items, remote_warning=remote_error)

    # mode == "remote" — browse remote variants.
    remote = get_object_or_404(Remote, pk=remote_id)
    # Every page of the remote's list, then this project's own filter, then
    # this page's slice: the filter runs here, so the remote cannot page it.
    try:
        remote_variants = _remote_variants(remote, search=q or None)
    except Exception as exc:
        return answer(error=_unreadable(exc))

    local_app_labels = {ac.label for ac in django_apps.get_app_configs()}
    local_hash_map = {
        (v.block.identifier, v.collection.identifier if v.collection_id else None, v.identifier): variant_content_hash(
            v
        )
        for v in BlockVariant.objects.select_related("block", "collection").all()
    }
    all_items = []
    for v in remote_variants:
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

    return answer(all_items)


# ─────────────────────────────────────────────────────────────────
# Pull
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_pull(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    remote = get_object_or_404(Remote, pk=request.POST.get("remote_id"))
    try:
        result = StreamsSyncService(remote).pull(variant_id=int(request.POST.get("variant_id")))
    except ValidationError as exc:
        return _refused(request, exc.messages)
    except Exception as exc:
        return _refused(request, [f"Pull failed: {exc}"])
    return changed(BlockVariant, f"Pulled '{result.variant.name}'.")


# ─────────────────────────────────────────────────────────────────
# Push
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_sync_push(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    remote = get_object_or_404(Remote, pk=request.POST.get("remote_id"))
    try:
        result = StreamsSyncService(remote).push(variant_id=int(request.POST.get("variant_id")))
    except ValidationError as exc:
        return _refused(request, exc.messages)
    except Exception as exc:
        return _refused(request, [f"Push failed: {exc}"])
    return changed(BlockVariant, f"Pushed '{result.variant_name}' to remote.")


def _refused(request, reasons):
    """A pull or push that did not go through: the drawer stays open and says why."""
    for reason in reasons:
        messages.error(request, reason)
    return render(request, f"{_T}/partials/action_refused.html")


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
        v = _local_variant(variant_id)
        return _render_detail(request, build_variant_envelope(v), local_variant_id=v.pk)

    if not remote_id:
        return HttpResponseBadRequest("Missing remote_id")

    remote = get_object_or_404(Remote, pk=remote_id)

    if mode == "local":
        # variant_id is a local BlockVariant PK.
        v = _local_variant(variant_id)
        remote_variant_id = None
        sync_state = "not_remote"

        try:
            _params: dict = {"block": v.block.identifier}
            if v.collection_id:
                _params["collection"] = v.collection.identifier
            for rv in _remote_variants(remote, **_params):
                if rv["identifier"] == v.identifier:
                    remote_variant_id = rv["id"]
                    break

            if remote_variant_id is not None:
                pull_resp = httpx.get(
                    f"{remote.base_url}/api/streams/v1/variants/{remote_variant_id}/pull/",
                    headers={"Authorization": f"Bearer {remote.token}"},
                    timeout=15,
                    follow_redirects=True,
                )
                if pull_resp.is_success:
                    remote_install = pull_resp.json().get("install") or {}
                    remote_variant_data = remote_install.get("variant") or {}
                    remote_block_data = remote_install.get("block") or {}
                    sync_state = "differs" if _variant_differs(v, remote_variant_data, remote_block_data) else "in_sync"
                else:
                    sync_state = "unknown"
        except Exception:
            sync_state = "unknown"
            remote_variant_id = None

        return _render_detail(
            request,
            build_variant_envelope(v),
            remote,
            sync_state,
            remote_variant_id=remote_variant_id,
            local_variant_id=v.pk,
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
        return _detail_error(request, f"Could not reach remote: {exc}")

    if not resp.is_success:
        return _detail_error(request, f"Remote returned {resp.status_code}.")

    install = resp.json().get("install") or {}
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
        sync_state = "differs" if _variant_differs(local_v, variant_data, block_data) else "in_sync"

    return _render_detail(
        request,
        install,
        remote,
        sync_state,
        remote_variant_id=int(variant_id),
        local_variant_id=local_variant_id,
    )
