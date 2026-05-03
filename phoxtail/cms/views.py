"""Browser-facing HTML fragment views for the Phoxtail CMS design bar.

These views are HTMX partials — they return HTML, not JSON.  They live
outside the Ninja API deliberately: the API uses Bearer-token auth for
machine consumers (CLI, MCP tools, agents); these views use Django's
standard session auth, which is what the browser's design bar carries.

Access is restricted to authenticated superusers (same gate as the
design bar itself).
"""

from __future__ import annotations

from functools import wraps

from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.template.loader import render_to_string

from phoxtail.api.content.v1._helpers import body_field_name_for, resolve_page_for_read


def _require_superuser_htmx(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return HttpResponseForbidden("Superuser access required.")
        return view_func(request, *args, **kwargs)

    return wrapper


@_require_superuser_htmx
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


@_require_superuser_htmx
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
