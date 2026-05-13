from functools import wraps
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, QueryDict
from django.shortcuts import render
from django.urls import Resolver404, resolve, reverse
from django.views import View
from wagtail.search.backends import get_search_backend

from phoxtail.core.permissions import PermissionMixin


def require_htmx(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.htmx:
            return HttpResponseBadRequest("This endpoint only accepts HTMX requests")
        return view_func(request, *args, **kwargs)

    return wrapper


def _build_content_url(request):
    """
    Extract content_url from request params and merge extra params into it.

    Returns (content_url, error_response). On success error_response is None.
    """
    params = {key: request.GET.getlist(key) for key in request.GET.keys()}
    content_url_list = params.pop("content_url", [None])
    content_url = content_url_list[0] if content_url_list else None

    if not content_url:
        return None, HttpResponseBadRequest("Missing required parameter: content_url")

    if params:
        parsed = urlparse(content_url)
        existing_params = parse_qs(parsed.query)
        for key, values in params.items():
            existing_params[key] = values
        new_query = urlencode(existing_params, doseq=True)
        content_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

    return content_url, None


def _fetch_modal_content(request, content_url):
    """
    Resolve content_url, call the view server-side, and return its response.

    This eliminates the two-request pattern — the modal shell and its content
    are fetched in a single client request.
    """
    parsed = urlparse(content_url)

    try:
        match = resolve(parsed.path)
    except Resolver404:
        return HttpResponseBadRequest("Invalid content URL")

    # Temporarily set request.GET to the content URL's query params
    # so the content view reads the correct parameters.
    original_get = request.GET
    request.GET = QueryDict(parsed.query)

    try:
        response = match.func(request, *match.args, **match.kwargs)
    except PermissionDenied:
        response = HttpResponse(status=403)
    finally:
        request.GET = original_get

    return response


@require_htmx
def get_core_modal_with_htmx(request):
    content_url, error = _build_content_url(request)
    if error:
        return error

    content_response = _fetch_modal_content(request, content_url)

    # If the content view returned an error or a 204 (e.g. permission
    # denied with a showToast event), propagate it directly.
    if content_response.status_code >= 400 or content_response.status_code == 204:
        return content_response

    # Render TemplateResponse if needed
    if hasattr(content_response, "render") and callable(content_response.render):
        content_response = content_response.render()

    context = {"content_html": content_response.content.decode()}
    return render(request, "phoxtail_core/modal.html", context)


@require_htmx
def get_core_modal_level_1_with_htmx(request):
    content_url, error = _build_content_url(request)
    if error:
        return error

    content_response = _fetch_modal_content(request, content_url)

    if content_response.status_code >= 400 or content_response.status_code == 204:
        return content_response

    if hasattr(content_response, "render") and callable(content_response.render):
        content_response = content_response.render()

    context = {"content_html": content_response.content.decode()}
    return render(request, "phoxtail_core/modal_level_1.html", context)


class MultiSelectChipsSearchView(PermissionMixin, View):
    """
    Generic CBV for the multi-select chips widget search endpoint.

    Handles search, add, and remove actions. Subclasses must set:
      - form_class: The form class to instantiate
      - field_name: Name of the MultiSelectChipsField on the form
      - search_url_name: URL name for reverse() (e.g. "studio:search_references")

    Optional attributes:
      - widget_id: Defaults to field_name
      - item_template: Path to rich item display template
      - hx_include: CSS selector for extra fields to include in HTMX requests
      - oob_response_template: Template for selection-change responses with OOB updates

    Override hooks:
      - get_form(data): Build form from mutated QueryDict
      - get_extra_context(form): Return dict of additional context for OOB template
      - get_selected_items_queryset(model): Return base queryset for selected items
    """

    http_method_names = ["get"]

    form_class = None
    field_name = None
    search_url_name = None
    widget_id = None
    item_template = None
    hx_include = None
    oob_response_template = None
    max_results = 20

    def get_form(self, data):
        return self.form_class(data)

    def get_extra_context(self, form):
        return {}

    def get_selected_items_queryset(self, model):
        return model.objects.all()

    def get_search_url(self):
        return reverse(self.search_url_name)

    def get(self, request, *args, **kwargs):
        widget_id = self.widget_id or self.field_name

        # Read current selections and handle add/remove mutations
        current_selections = list(request.GET.getlist(self.field_name))
        selection_changed = False

        add_pk = request.GET.get(f"{widget_id}_add")
        if add_pk and add_pk not in current_selections:
            current_selections.append(add_pk)
            selection_changed = True

        remove_pk = request.GET.get(f"{widget_id}_remove")
        if remove_pk and remove_pk in current_selections:
            current_selections.remove(remove_pk)
            selection_changed = True

        # Build form with updated selections
        mutable_get = request.GET.copy()
        mutable_get.setlist(self.field_name, current_selections)
        form = self.get_form(mutable_get)

        # Compute selected and available items
        search_value = request.GET.get(f"{widget_id}_search", "").strip()
        field = form[self.field_name]
        queryset = field.field.queryset
        value = field.value()

        if isinstance(value, (list, tuple)):
            selected_pks = [str(pk) for pk in value if pk]
        else:
            selected_pks = [str(value)] if value else []

        if selected_pks:
            selected_items = self.get_selected_items_queryset(queryset.model).filter(pk__in=selected_pks)
        else:
            selected_items = queryset.none()

        available_items = queryset.exclude(pk__in=selected_pks) if selected_pks else queryset

        if search_value:
            s = get_search_backend()
            available_items = s.autocomplete(search_value, available_items)

        available_items = available_items[: self.max_results]

        # Base context for widget
        context = {
            "field": field,
            "selected_items": selected_items,
            "available_items": available_items,
            "search_url": self.get_search_url(),
            "search_value": search_value,
            "widget_id": widget_id,
            "item_template": self.item_template,
            "hx_include": self.hx_include,
        }

        # Search-only: return just dropdown content (preserves input focus)
        if not selection_changed:
            return render(
                request,
                "phoxtail_core/forms/widgets/htmx/multi_select_chips/results_content.html",
                context,
            )

        # Selection changed: return full widget + optional OOB updates
        context.update(self.get_extra_context(form))

        template = (
            self.oob_response_template or "phoxtail_core/forms/widgets/htmx/multi_select_chips/compact_input.html"
        )
        return render(request, template, context)


class SingleSelectSearchView(PermissionMixin, View):
    """
    Generic CBV for the single-select search widget endpoint.

    Handles search, select, and clear actions. Subclasses must set:
      - form_class: The form class to instantiate
      - field_name: Name of the SingleSelectSearchField on the form
      - search_url_name: URL name for reverse() (e.g. "studio:search_collection")

    Optional attributes:
      - widget_id: Defaults to field_name
      - item_template: Path to rich item display template
      - hx_include: CSS selector for extra fields to include in HTMX requests
      - oob_response_template: Template for selection-change responses with OOB updates

    Override hooks:
      - get_form(data): Build form from mutated QueryDict
      - get_extra_context(form): Return dict of additional context for OOB template
    """

    http_method_names = ["get"]

    form_class = None
    field_name = None
    search_url_name = None
    widget_id = None
    item_template = None
    hx_include = None
    oob_response_template = None
    max_results = 20

    def get_form(self, data):
        return self.form_class(data)

    def get_extra_context(self, form):
        return {}

    def get_search_url(self):
        return reverse(self.search_url_name)

    def get(self, request, *args, **kwargs):
        widget_id = self.widget_id or self.field_name

        # Read current value and handle select/clear mutations
        current_value = request.GET.get(self.field_name, "")
        selection_changed = False

        select_pk = request.GET.get(f"{widget_id}_select")
        if select_pk:
            current_value = select_pk
            selection_changed = True

        clear_flag = request.GET.get(f"{widget_id}_clear")
        if clear_flag:
            current_value = ""
            selection_changed = True

        # Build form with updated value
        mutable_get = request.GET.copy()
        mutable_get[self.field_name] = current_value
        form = self.get_form(mutable_get)

        # Derive selected item and available items from field
        search_value = request.GET.get(f"{widget_id}_search", "").strip()
        field = form[self.field_name]

        selected_item = field.selected_item
        available_items = field.available_items

        # Only apply search filter for search-only requests (not select/clear).
        # The search input lives inside #context-parent-fields, so its value
        # leaks into select/clear requests via hx-include — skip it there.
        if search_value and not selection_changed:
            s = get_search_backend()
            available_items = s.autocomplete(search_value, available_items)

        available_items = available_items[: self.max_results]

        # Base context for widget
        context = {
            "field": field,
            "selected_item": selected_item,
            "available_items": available_items,
            "search_url": self.get_search_url(),
            "search_value": search_value,
            "widget_id": widget_id,
            "item_template": self.item_template,
            "hx_include": self.hx_include,
        }

        # Search-only: return just dropdown content (preserves input focus)
        if not selection_changed:
            return render(
                request,
                "phoxtail_core/forms/widgets/htmx/single_select_search/results_content.html",
                context,
            )

        # Selection changed: return full widget + optional OOB updates
        context.update(self.get_extra_context(form))

        template = self.oob_response_template or "phoxtail_core/forms/widgets/htmx/single_select_search/input.html"
        return render(request, template, context)
