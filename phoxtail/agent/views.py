"""Browser-facing HTML views for the Phoxtail Agent (chatbot)."""

from __future__ import annotations

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
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
