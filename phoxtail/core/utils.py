from django.core.paginator import Paginator

OBJECTS_PER_PAGE = 5


def paginate_queryset(queryset, request, search_query="", objects_per_page=OBJECTS_PER_PAGE):
    """Helper function to handle pagination."""
    page = request.GET.get("page", 1)
    paginator = Paginator(queryset, objects_per_page)
    return paginator.get_page(page), search_query
