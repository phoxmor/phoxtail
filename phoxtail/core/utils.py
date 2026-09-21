from django.core.paginator import Paginator

OBJECTS_PER_PAGE = 5


def paginate_queryset(queryset, request, search_query="", objects_per_page=OBJECTS_PER_PAGE):
    """Helper function to handle pagination."""
    page = request.GET.get("page", 1)
    paginator = Paginator(queryset, objects_per_page)
    return paginator.get_page(page), search_query


def page_range_entries(current, num_pages, url_fn, window=2):
    """Build a windowed page-range list for the shared paginator partial.

    Returns a list of dicts: {num, url, active, ellipsis}.
    Always shows first/last page and a window of ``window`` pages around the
    current page (default 2, matching prior behavior), inserting ellipsis
    dicts for gaps.
    """
    if num_pages <= 1:
        return []
    in_range = {1, num_pages}
    for p in range(max(1, current - window), min(num_pages + 1, current + window + 1)):
        in_range.add(p)
    result = []
    prev = None
    for p in sorted(in_range):
        if prev is not None and p - prev > 1:
            result.append({"num": "…", "url": None, "active": False, "ellipsis": True})
        result.append({"num": p, "url": None if p == current else url_fn(p), "active": p == current, "ellipsis": False})
        prev = p
    return result


def public_url(url: str | None) -> str | None:
    """Return ``url`` as the outside world can reach it.

    A storage gives back a site-relative path such as ``/media/…``. The
    request that asked for it is no guide to the origin: the MCP server
    reaches the API at ``http://web`` inside the compose network, and the
    original ``Host`` header is what ``build_absolute_uri`` would echo.
    ``WAGTAILADMIN_BASE_URL`` is the address the project is configured to
    be known by, so that is what a relative path is joined to. Absolute
    URLs (a remote storage backend) pass through untouched.
    """
    if not url:
        return None
    if url.startswith("/"):
        from django.conf import settings

        base = getattr(settings, "WAGTAILADMIN_BASE_URL", "").rstrip("/")
        return base + url
    return url
