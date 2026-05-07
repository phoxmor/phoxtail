"""Browser-facing HTML views for the Phoxtail Agent (chatbot)."""

from __future__ import annotations

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from wagtail.documents import get_document_model
from wagtail.images import get_image_model
from wagtail.search.backends import get_search_backend

from phoxtail.agent.models import Conversation
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


@agent_permission_required("access_chatbot")
def media_picker(request):
    tab = request.GET.get("tab", "images")
    query = request.GET.get("q", "").strip()
    s = get_search_backend()
    results = []

    if tab == "images":
        Image = get_image_model()
        qs = (
            Image.objects.all()
            .select_related("collection")
            .prefetch_related("tags")
            .order_by("-created_at")
        )
        if query:
            qs = s.autocomplete(query, qs)[:40]
        else:
            qs = qs[:40]
        results = list(qs)
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
            if query:
                qs = s.autocomplete(query, qs)[:40]
            else:
                qs = qs[:40]
            results = list(qs)
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
            if query:
                qs = s.autocomplete(query, qs)[:40]
            else:
                qs = qs[:40]
            results = list(qs)
        except ImportError:
            results = []
    elif tab == "documents":
        Document = get_document_model()
        qs = (
            Document.objects.all()
            .select_related("collection")
            .prefetch_related("tags")
            .order_by("-created_at")
        )
        if query:
            qs = s.autocomplete(query, qs)[:40]
        else:
            qs = qs[:40]
        results = list(qs)

    ctx = {"tab": tab, "query": query, "results": results}

    if request.htmx and request.htmx.target == "phoxtail-media-picker-results":
        return render(request, "phoxtail_agent/partials/media_picker_results.html", ctx)

    return render(request, "phoxtail_agent/media_picker.html", ctx)


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
