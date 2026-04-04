import django_filters
from wagtail.search.backends import get_search_backend

from phoxtail.booking.subscriptions.constants import SubscriptionStatus
from phoxtail.booking.subscriptions.models import Subscription, SubscriptionType

search_backend = get_search_backend()


class BillingFilter(django_filters.FilterSet):
    """Filter for Subscription queryset with search, is_paid, and pagination."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("prefix", "filter")
        super().__init__(*args, **kwargs)

    is_paid = django_filters.BooleanFilter(
        field_name="is_paid",
    )

    subscription_type = django_filters.ModelChoiceFilter(
        field_name="subscription_type",
        queryset=SubscriptionType.objects.filter(is_active=True),
        label="Subscription Type",
        empty_label="All",
    )

    status = django_filters.ChoiceFilter(
        field_name="status",
        choices=SubscriptionStatus.choices,
        label="Status",
        empty_label="All",
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
        model = Subscription
        fields = ["search", "is_paid", "subscription_type", "status", "page"]

    def filter_search(self, queryset, name, value):
        """
        Filter subscriptions by search query.
        Uses Wagtail search backend if available, falls back to database filtering.
        """
        if not value:
            return queryset

        return (
            search_backend.autocomplete(value, queryset)
            .get_queryset()
            .order_by("-start_date")
        )

    def filter_page(self, queryset, name, value):
        """This filter doesn't affect the queryset - it's used for pagination state only."""
        return queryset
