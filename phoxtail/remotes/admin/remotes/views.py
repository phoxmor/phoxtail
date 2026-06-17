"""HTMX views for the Remotes settings admin.

Manages connection objects (Remote) — add, edit, delete, search.
No browse or install here; those live in phoxtail.streams (sync).
"""

from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from wagtail.search.backends import get_search_backend

from phoxtail.core.utils import page_range_entries
from phoxtail.remotes.models import Remote
from phoxtail.remotes.permissions import remotes_permission_required

from .forms import RemoteAddForm, RemoteEditForm

_T = "phoxtail_remotes/admin/remotes"

PER_PAGE = 20


def _remotes_qs(request):
    q = request.GET.get("q", "").strip()
    qs = Remote.objects.all()
    if q:
        qs = get_search_backend().autocomplete(q, qs)
    return qs, q


def _build_remotes_paginator_ctx(page_obj, q):
    """Build paginator context from a Django Page object."""
    pag = page_obj.paginator
    num_pages = pag.num_pages
    current = page_obj.number
    search_url = reverse("remotes:search")

    def page_url(p):
        url = f"{search_url}?page={p}"
        if q:
            url += f"&q={q}"
        return url

    return {
        "has_prev": page_obj.has_previous(),
        "prev_url": page_url(page_obj.previous_page_number()) if page_obj.has_previous() else None,
        "has_next": page_obj.has_next(),
        "next_url": page_url(page_obj.next_page_number()) if page_obj.has_next() else None,
        "page_range": page_range_entries(current, num_pages, page_url),
        "current_page": current,
        "num_pages": num_pages,
        "hx_target": "#remotes-container",
    }


def _page_ctx(q="", page=1):
    """Paginate the remotes queryset; used after form mutations (always page 1)."""
    qs = Remote.objects.all()
    if q:
        qs = qs.filter(name__icontains=q)
    paginator = Paginator(qs, PER_PAGE)
    page_obj = paginator.get_page(page)
    return page_obj, _build_remotes_paginator_ctx(page_obj, q), paginator.count


# ─────────────────────────────────────────────────────────────────
# Index
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_remotes_index(request):
    qs, q = _remotes_qs(request)
    paginator = Paginator(qs, PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    paginator_ctx = _build_remotes_paginator_ctx(page_obj, q)
    context = {"remotes": page_obj, "q": q, "paginator_ctx": paginator_ctx, "total": paginator.count}
    if getattr(request, "htmx", None):
        return render(request, f"{_T}/partials/remotes_list.html", context)
    return render(request, f"{_T}/index.html", context)


@remotes_permission_required("manage_remotes")
def admin_remotes_search(request):
    qs, q = _remotes_qs(request)
    paginator = Paginator(qs, PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page", 1))
    paginator_ctx = _build_remotes_paginator_ctx(page_obj, q)
    return render(
        request,
        f"{_T}/partials/remotes_list.html",
        {"remotes": page_obj, "q": q, "paginator_ctx": paginator_ctx, "total": paginator.count},
    )


# ─────────────────────────────────────────────────────────────────
# Add
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_remote_add_form(request):
    return render(request, f"{_T}/partials/forms/add/form.html", {"form": RemoteAddForm()})


@remotes_permission_required("manage_remotes")
def admin_remote_add(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    form = RemoteAddForm(request.POST)
    created = False

    if form.is_valid():
        instance = form.save()
        created = True
        messages.success(request, f"Remote '{instance.name}' connected.")
    else:
        for error in form.non_field_errors():
            messages.error(request, error)

    page_obj, paginator_ctx, total = _page_ctx()
    return render(
        request,
        f"{_T}/partials/forms/add/form_response.html",
        {"form": form, "created": created, "remotes": page_obj, "paginator_ctx": paginator_ctx, "total": total},
    )


# ─────────────────────────────────────────────────────────────────
# Edit
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_remote_edit_form(request, remote_id):
    remote = get_object_or_404(Remote, pk=remote_id)
    form = RemoteEditForm(instance=remote)
    return render(request, f"{_T}/partials/forms/edit/form.html", {"form": form, "remote": remote})


@remotes_permission_required("manage_remotes")
def admin_remote_edit(request, remote_id):
    if request.method != "POST":
        return HttpResponse(status=405)

    remote = get_object_or_404(Remote, pk=remote_id)
    form = RemoteEditForm(request.POST, instance=remote)
    saved = False

    if form.is_valid():
        form.save()
        saved = True
        messages.success(request, f"Remote '{remote.name}' updated.")

    page_obj, paginator_ctx, total = _page_ctx()
    return render(
        request,
        f"{_T}/partials/forms/edit/form_response.html",
        {
            "form": form,
            "remote": remote,
            "saved": saved,
            "remotes": page_obj,
            "paginator_ctx": paginator_ctx,
            "total": total,
        },
    )


# ─────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_remote_delete_form(request, remote_id):
    remote = get_object_or_404(Remote, pk=remote_id)
    return render(request, f"{_T}/partials/forms/delete/form.html", {"remote": remote})


@remotes_permission_required("manage_remotes")
def admin_remote_delete(request, remote_id):
    if request.method != "POST":
        return HttpResponse(status=405)
    remote = get_object_or_404(Remote, pk=remote_id)
    name = remote.name
    remote.delete()
    messages.success(request, f"Remote '{name}' disconnected.")
    page_obj, paginator_ctx, total = _page_ctx()
    return render(
        request,
        f"{_T}/partials/forms/delete/form_response.html",
        {"remotes": page_obj, "paginator_ctx": paginator_ctx, "total": total},
    )
