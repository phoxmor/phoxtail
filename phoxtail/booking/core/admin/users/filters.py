import django_filters
from django.contrib.auth import get_user_model
from wagtail.search.backends import get_search_backend

search_backend = get_search_backend()


class UserFilter(django_filters.FilterSet):
    """Filter for User queryset with search, is_active, and pagination."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "filter")
        super().__init__(*args, **kwargs)

    is_active = django_filters.BooleanFilter(
        field_name="is_active",
        label="Active",
    )

    search = django_filters.CharFilter(
        method="filter_search",
        label="Search",
    )

    page = django_filters.NumberFilter(
        method="filter_page",
        label="Page",
    )

    class Meta:
        model = get_user_model()
        fields = ["search", "is_active", "page"]

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        return search_backend.autocomplete(value, queryset).get_queryset().order_by("-date_joined")

    def filter_page(self, queryset, name, value):
        """This filter doesn't affect the queryset - it's used for pagination state only."""
        return queryset
