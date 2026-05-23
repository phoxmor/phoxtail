"""Browser-facing HTML views for the Phoxtail Agent (chatbot)."""

from __future__ import annotations

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.search.backends import get_search_backend

from phoxtail.agent.models import AgentSiteSetting, Conversation, ModelArtifact
from phoxtail.agent.permissions import agent_permission_required
from phoxtail.api.content.v1._helpers import body_field_name_for, resolve_page_for_read


@agent_permission_required("access_chatbot")
def chat_history(request):
    query = request.GET.get("q", "").strip()
    qs = Conversation.objects.filter(user=request.user)
    if query:
        s = get_search_backend()
        qs = s.autocomplete(query, qs)[:30]
    else:
        qs = qs.exclude(title="")[:30]

    template = "phoxtail_agent/chat_history.html"
    if request.htmx and request.htmx.target == "phoxtail-chat-history-list":
        template = "phoxtail_agent/partials/chat_history_list.html"

    return render(request, template, {"conversations": qs, "query": query})


_MEDIA_PICKER_PAGE_SIZE = 15


@agent_permission_required("access_chatbot")
def media_picker(request):
    tab = request.GET.get("tab", "images")
    query = request.GET.get("q", "").strip()
    offset = max(0, int(request.GET.get("offset", 0) or 0))
    collection_id = request.GET.get("collection_id", "").strip()
    if collection_id and not collection_id.isdigit():
        collection_id = ""
    s = get_search_backend()
    results = []

    fetch = _MEDIA_PICKER_PAGE_SIZE + 1  # one extra to detect has_more

    if tab == "images":
        Image = get_image_model()
        qs = (
            Image.objects.all()
            .select_related("collection")
            .prefetch_related("tags", "renditions")
            .order_by("-created_at")
        )
        if collection_id:
            qs = qs.filter(collection_id=collection_id)
        if query:
            qs = s.autocomplete(query, qs)
        results = list(qs[offset : offset + fetch])
    elif tab == "videos":
        try:
            from wagtailmedia.models import get_media_model

            Media = get_media_model()
            qs = (
                Media.objects.filter(type="video")
                .select_related("collection")
                .prefetch_related("tags")
                .order_by("-created_at")
            )
            if collection_id:
                qs = qs.filter(collection_id=collection_id)
            if query:
                qs = s.autocomplete(query, qs)
            results = list(qs[offset : offset + fetch])
        except ImportError:
            results = []
    elif tab == "audio":
        try:
            from wagtailmedia.models import get_media_model

            Media = get_media_model()
            qs = (
                Media.objects.filter(type="audio")
                .select_related("collection")
                .prefetch_related("tags")
                .order_by("-created_at")
            )
            if collection_id:
                qs = qs.filter(collection_id=collection_id)
            if query:
                qs = s.autocomplete(query, qs)
            results = list(qs[offset : offset + fetch])
        except ImportError:
            results = []
    elif tab == "documents":
        Document = get_document_model()
        qs = Document.objects.all().select_related("collection").prefetch_related("tags").order_by("-created_at")
        if collection_id:
            qs = qs.filter(collection_id=collection_id)
        if query:
            qs = s.autocomplete(query, qs)
        results = list(qs[offset : offset + fetch])

    has_more = len(results) > _MEDIA_PICKER_PAGE_SIZE
    if has_more:
        results = results[:_MEDIA_PICKER_PAGE_SIZE]

    ctx = {
        "tab": tab,
        "query": query,
        "results": results,
        "offset": offset,
        "has_more": has_more,
        "next_offset": offset + _MEDIA_PICKER_PAGE_SIZE,
        "collection_id": collection_id,
    }

    if request.htmx and (request.htmx.target == "phoxtail-media-picker-results" or offset > 0):
        return render(request, "phoxtail_agent/partials/media_picker_results.html", ctx)

    from wagtail.models import Collection

    collections = list(Collection.objects.filter(depth__gt=1).order_by("path"))
    selected_collection_name = ""
    if collection_id:
        for c in collections:
            if str(c.pk) == collection_id:
                selected_collection_name = c.name
                break
        else:
            collection_id = ""
            ctx["collection_id"] = ""

    ctx["collections"] = collections
    ctx["selected_collection_name"] = selected_collection_name
    return render(request, "phoxtail_agent/media_picker.html", ctx)


@agent_permission_required("access_chatbot")
def collection_picker(request):
    from wagtail.models import Collection

    q = request.GET.get("q", "").strip()
    collection_id = request.GET.get("collection_id", "").strip()
    if collection_id and not collection_id.isdigit():
        collection_id = ""

    qs = Collection.objects.filter(depth__gt=1)
    if q:
        qs = qs.filter(name__icontains=q).order_by("name")
        is_search = True
    else:
        qs = qs.order_by("path")
        is_search = False

    return render(
        request,
        "phoxtail_agent/partials/collection_picker_list.html",
        {"collections": list(qs), "collection_id": collection_id, "is_search": is_search},
    )


@agent_permission_required("access_chatbot")
def model_picker_panel(request):
    query = request.GET.get("q", "").strip()
    qs = (
        ModelArtifact.objects.filter(is_active=True, provider__is_active=True)
        .select_related("provider", "permission__content_type")
        .order_by("sort_order")
    )
    if query:
        s = get_search_backend()
        qs = s.autocomplete(query, qs)
    visible = []
    for artifact in qs:
        if artifact.permission is None:
            visible.append(artifact)
        else:
            ct = artifact.permission.content_type
            perm = f"{ct.app_label}.{artifact.permission.codename}"
            if request.user.has_perm(perm):
                visible.append(artifact)
    try:
        agent_settings = AgentSiteSetting.for_request(request)
    except Exception:
        agent_settings = None
    default_artifact_id = (
        agent_settings.default_artifact_id if agent_settings and agent_settings.default_artifact_id else None
    )
    return render(
        request,
        "phoxtail_agent/partials/model_picker_rows.html",
        {"artifacts": visible, "default_artifact_id": default_artifact_id},
    )


def _apply_page_site(request, draft) -> None:
    """Override all site state on the request to match the page's actual site.

    Screenshot endpoints are always served from localhost, so SiteMiddleware sets
    request.site / request._wagtail_site to the default site. This must be
    corrected before rendering so that SiteSetting (palette, fonts, branding) and
    shared-block lookups (navbar, footer) resolve to the correct per-site values.
    """
    from wagtail.models import Site

    page_site = (
        Site.objects.filter(root_page__in=draft.get_ancestors(inclusive=True)).order_by("-root_page__depth").first()
    )
    if page_site:
        request.site = page_site
        request._wagtail_site = page_site
        from phoxtail.cms.models import SiteSetting

        cache_attr = SiteSetting.get_cache_attr_name()
        if hasattr(request, cache_attr):
            delattr(request, cache_attr)


def _authenticate_screenshot_request(request):
    """Validate ?token= and return the user, or None on failure."""
    from phoxtail.agent.permissions import agent_permission_policy
    from phoxtail.tokens.auth import authenticate

    user = authenticate(request.GET.get("token", ""))
    if user is None or not agent_permission_policy.user_has_permission(user, "access_chatbot"):
        return None
    return user


def render_page_for_screenshot(request, page_id: int, block_uuid: str) -> HttpResponse:
    """Render the full page HTML so Playwright can screenshot a specific block.

    Auth is via ``?token=<bearer_token>`` — Playwright cannot set request
    headers during navigation, so we accept the token as a query param here.
    The token is validated with the same logic used by the Ninja API auth layer.
    """
    user = _authenticate_screenshot_request(request)
    if user is None:
        return HttpResponse(status=403)

    request.user = user
    draft = resolve_page_for_read(page_id)
    _apply_page_site(request, draft)

    return render(
        request, "phoxtail_cms/pages/page.html", {"page": draft, "self": draft, "phoxtail_screenshot_mode": True}
    )


def render_page_for_viewport_screenshot(request, page_id: int) -> HttpResponse:
    """Render the full page HTML so Playwright can take a viewport screenshot.

    Auth is via ``?token=<bearer_token>``. Identical auth and site-correction
    logic to render_page_for_screenshot but without the block_uuid constraint,
    intended for full-page viewport captures across breakpoints.
    """
    user = _authenticate_screenshot_request(request)
    if user is None:
        return HttpResponse(status=403)

    request.user = user
    draft = resolve_page_for_read(page_id)
    _apply_page_site(request, draft)

    return render(
        request, "phoxtail_cms/pages/page.html", {"page": draft, "self": draft, "phoxtail_screenshot_mode": True}
    )


@agent_permission_required("access_chatbot")
def render_block_fragment(request, page_id: int, block_uuid: str) -> HttpResponse:
    """Render a single block as an HTML fragment for HTMX outerHTML swap."""
    draft = resolve_page_for_read(page_id)

    field_name = body_field_name_for(draft)
    stream_value = getattr(draft, field_name, None)
    if stream_value is None:
        raise Http404(f"Page {page_id} has no StreamField.")

    bound_block = None
    for b in stream_value:
        if str(b.id) == block_uuid:
            bound_block = b
            break

    if bound_block is None:
        raise Http404(f"Block '{block_uuid}' not found on this page.")

    html = render_to_string(
        "phoxtail_cms/partials/block_fragment.html",
        {
            "bound_block": bound_block,
            "block": bound_block,
            "page_id": page_id,
            "page": draft,
        },
        request=request,
    )
    return HttpResponse(html, content_type="text/html")


@agent_permission_required("access_chatbot")
def render_body_fragment(request, page_id: int) -> HttpResponse:
    """Render all blocks as an HTML fragment for HTMX innerHTML swap."""
    draft = resolve_page_for_read(page_id)

    field_name = body_field_name_for(draft)
    stream_value = getattr(draft, field_name, None)
    if stream_value is None:
        raise Http404(f"Page {page_id} has no StreamField.")

    html = render_to_string(
        "phoxtail_cms/partials/body_container_inner.html",
        {"stream_value": stream_value, "page_id": page_id},
        request=request,
    )
    return HttpResponse(html, content_type="text/html")
