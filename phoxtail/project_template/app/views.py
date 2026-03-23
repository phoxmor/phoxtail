from django.http import HttpResponseBadRequest, QueryDict
from django.shortcuts import get_object_or_404, render
from wagtail.models import Page

from phoxtail.core.views import require_htmx


def get_page_for_preview(request, page_id, in_preview, page_is_live):
    """
    Get the page object, checking for preview data in the session.

    This handles three scenarios:
    1. Unsaved preview changes (from session)
    2. Saved draft (latest revision)
    3. Published page (live version)
    """
    page = get_object_or_404(Page, id=page_id)

    if not (in_preview or not page_is_live):
        return page.specific

    # Check for unsaved preview data in session
    session_key = f"wagtail-preview-{page_id}"
    preview_data = request.session.get(session_key)

    if preview_data and isinstance(preview_data, list) and len(preview_data) >= 1:
        try:
            # Parse URL-encoded form data from session
            query_dict = QueryDict(preview_data[0])

            # Get the page's form class and create form instance
            form_class = page.specific_class.get_edit_handler().get_form_class()
            form = form_class(query_dict, instance=page.specific)

            # Return the page instance with unsaved changes
            if form.is_valid():
                return form.save(commit=False)

        except Exception:
            pass

    # Try to get the latest revision for saved drafts
    latest_revision = page.get_latest_revision()
    if latest_revision:
        return latest_revision.as_object()

    return page.specific


@require_htmx
def get_image_gallery_block_modal_content_with_htmx(request):
    page_id = request.GET.get("page_id")
    streamfield_name = request.GET.get("streamfield_name", "body")
    block_index = request.GET.get("block_index")
    image_index = request.GET.get("image_index")
    in_preview = request.GET.get("in_preview") == "true"
    page_is_live = request.GET.get("page_is_live") == "true"

    if not all([page_id, block_index, image_index]):
        return HttpResponseBadRequest("Missing required parameters")

    try:
        block_index = int(block_index)
        int(image_index)
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Invalid index values")

    page = get_page_for_preview(request, page_id, in_preview, page_is_live)

    try:
        streamfield = getattr(page, streamfield_name)
        block = streamfield[block_index]
    except (AttributeError, IndexError):
        return HttpResponseBadRequest("Block not found")

    return render(
        request,
        "phoxtail_streams/partials/image_gallery_modal_content.html",
        context={"block": block, "image_index": image_index},
    )


@require_htmx
def get_customer_reviews_block_modal_content_with_htmx(request):
    page_id = request.GET.get("page_id")
    streamfield_name = request.GET.get("streamfield_name", "body")
    block_index = request.GET.get("block_index")
    review_index = request.GET.get("review_index")
    in_preview = request.GET.get("in_preview") == "true"
    page_is_live = request.GET.get("page_is_live") == "true"

    if not all([page_id, block_index, review_index]):
        return HttpResponseBadRequest("Missing required parameters")

    try:
        block_index = int(block_index)
        int(review_index)
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Invalid index values")

    page = get_page_for_preview(request, page_id, in_preview, page_is_live)

    try:
        streamfield = getattr(page, streamfield_name)
        block = streamfield[block_index]
    except (AttributeError, IndexError):
        return HttpResponseBadRequest("Block not found")

    return render(
        request,
        "phoxtail_streams/partials/customer_reviews_modal_content.html",
        context={"block": block, "review_index": review_index},
    )


@require_htmx
def get_team_members_block_modal_content_with_htmx(request):
    page_id = request.GET.get("page_id")
    streamfield_name = request.GET.get("streamfield_name", "body")
    block_index = request.GET.get("block_index")
    member_index = request.GET.get("member_index")
    in_preview = request.GET.get("in_preview") == "true"
    page_is_live = request.GET.get("page_is_live") == "true"

    if not all([page_id, block_index, member_index]):
        return HttpResponseBadRequest("Missing required parameters")

    try:
        block_index = int(block_index)
        int(member_index)
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Invalid index values")

    page = get_page_for_preview(request, page_id, in_preview, page_is_live)

    try:
        streamfield = getattr(page, streamfield_name)
        block = streamfield[block_index]
    except (AttributeError, IndexError):
        return HttpResponseBadRequest("Block not found")

    return render(
        request,
        "phoxtail_streams/partials/team_members_modal_content.html",
        context={"block": block, "member_index": member_index},
    )
