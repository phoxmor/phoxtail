from django import template

register = template.Library()


@register.filter
def in_set(value, candidates):
    """``{% with on_trail=p.pk|in_set:active_ancestor_ids %}`` — ``{% with %}`` only
    accepts filter chains, not boolean ``in`` expressions, hence this filter."""
    return value in candidates


@register.simple_tag(takes_context=True)
def page_children(context, page, active_ancestor_ids):
    """First page of ``page``'s children, for eagerly rendering the menu-picker's
    active trail. Returns ``{"pages", "has_more", "next_offset", "exclude_id"}``
    so the template can chain a "Load more" into the lazy children endpoint.

    Capped so a node with an unusually large fan-out (hundreds of siblings)
    can't blow up the tree render when it sits on the active page's ancestor
    chain — everywhere else children are still loaded lazily on click. The
    on-trail child is always included even when it falls past the cap, and
    ``exclude_id`` then tells "Load more" pages to skip it.

    Filtered to what the viewing user is allowed to explore — this is on the
    active-trail path, which is the one place children get rendered without
    going through the (already permission-filtered) menu_picker_children view.
    Fails closed: no request in context means no pages, never unfiltered ones.
    """
    from phoxtail.agent.views import _MENU_CHILDREN_PAGE_SIZE, _explorable_pages

    empty = {"pages": [], "has_more": False, "next_offset": 0, "exclude_id": None}
    request = context.get("request")
    if request is None:
        return empty

    qs = _explorable_pages(page.get_children().select_related("content_type", "locale"), request.user).order_by("path")
    pages = list(qs[: _MENU_CHILDREN_PAGE_SIZE + 1])
    has_more = len(pages) > _MENU_CHILDREN_PAGE_SIZE
    if has_more:
        pages = pages[:_MENU_CHILDREN_PAGE_SIZE]

    # A node has at most one child on the trail (the trail is a single path);
    # if the cap pushed it out of the window, pull it back in so the expanded
    # branch always reaches the active page.
    exclude_id = None
    if has_more and active_ancestor_ids and not any(p.pk in active_ancestor_ids for p in pages):
        stray = qs.filter(pk__in=active_ancestor_ids).first()
        if stray is not None:
            pages.append(stray)
            exclude_id = stray.pk

    return {
        "pages": pages,
        "has_more": has_more,
        "next_offset": _MENU_CHILDREN_PAGE_SIZE,
        "exclude_id": exclude_id,
    }
