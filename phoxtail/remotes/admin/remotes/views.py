"""HTMX views for the Remotes settings admin.

Manages connection objects (Remote) — add, edit, disconnect, search. No
browse or install here; those live in phoxtail.streams (sync). Each drawer is
a core modal drawer. An action that went through answers with events
(:func:`phoxtail.core.htmx.changed`): the list listens for a change to
:class:`Remote` and redraws itself. A refused save redraws its fields out of
band.
"""

from __future__ import annotations

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from wagtail.search.backends import get_search_backend

from phoxtail.core.htmx import changed
from phoxtail.remotes.models import Remote
from phoxtail.remotes.permissions import remotes_permission_required

from .forms import RemoteAddForm, RemoteEditForm, RemoteSearchForm

_T = "phoxtail_remotes/admin/remotes"

PAGE_SIZE = 12


def _list_context(request):
    """The list: the search, and the page of remotes it matches."""
    form = RemoteSearchForm(request.GET)
    form.is_valid()
    q = form.cleaned_data.get("search", "").strip()
    qs = Remote.objects.all()
    if q:
        qs = get_search_backend().autocomplete(q, qs)
    page = Paginator(qs, PAGE_SIZE).get_page(form.cleaned_data.get("page"))
    return {"search_form": form, "remotes": page, "q": q}


# ─────────────────────────────────────────────────────────────────
# List
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_remotes_index(request):
    context = _list_context(request)
    if request.htmx:
        return render(request, f"{_T}/partials/remotes.html", context)
    return render(request, f"{_T}/index.html", context)


@remotes_permission_required("manage_remotes")
def admin_remotes_search(request):
    """A search or a page: the list redrawn out of band."""
    return render(request, f"{_T}/partials/forms/search/form_response.html", _list_context(request))


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
    if form.is_valid():
        remote = form.save()
        return changed(Remote, f"Remote '{remote.name}' connected.")

    for error in form.non_field_errors():
        messages.error(request, error)
    return render(request, f"{_T}/partials/forms/add/form_response.html", {"form": form})


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
    if form.is_valid():
        form.save()
        return changed(Remote, f"Remote '{remote.name}' updated.")

    return render(request, f"{_T}/partials/forms/edit/form_response.html", {"form": form, "remote": remote})


# ─────────────────────────────────────────────────────────────────
# Disconnect
# ─────────────────────────────────────────────────────────────────


@remotes_permission_required("manage_remotes")
def admin_remote_delete(request, remote_id):
    if request.method != "POST":
        return HttpResponse(status=405)
    remote = get_object_or_404(Remote, pk=remote_id)
    name = remote.name
    remote.delete()
    return changed(Remote, f"Remote '{name}' disconnected.")
