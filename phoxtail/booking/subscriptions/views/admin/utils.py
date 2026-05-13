from django.core.paginator import Paginator
from django.http import HttpRequest

from phoxtail.booking.subscriptions.filters import BillingFilter
from phoxtail.booking.subscriptions.models import Subscription


class BillingContextBuilder:
    """Builds billing context for filters and subscription list views."""

    def __init__(self, request: HttpRequest):
        self.request = request
        self.query_params = None
        self.filterset = None
        self.filter_count = None

    def _extract_query_params(self):
        """Extract query parameters from GET or POST request."""
        self.query_params = self.request.GET.copy() if self.request.method == "GET" else self.request.POST.copy()

    def _create_filterset(self, base_queryset):
        """Create and configure filterset."""
        self.filterset = BillingFilter(self.query_params, queryset=base_queryset)

    def _calculate_filter_count(self):
        """Calculate number of active filters (excluding page and search)."""
        form = self.filterset.form
        form.is_valid()

        filter_keys = [k for k in form.cleaned_data if k not in ["page", "search"]]
        self.filter_count = sum(1 for k, v in form.cleaned_data.items() if k in filter_keys and v not in ["", None])

    def _prepare_base_context(self, base_queryset):
        """Prepare common context for both lightweight and full builders."""
        self._extract_query_params()
        self._create_filterset(base_queryset)
        self._calculate_filter_count()

    def build_filters_context(self):
        """Build lightweight context for filter form only."""
        self._prepare_base_context(base_queryset=Subscription.objects.none())
        return {
            "filterset": self.filterset,
            "filter_count": self.filter_count,
        }

    def _build_subscription_queryset(self):
        """Build subscription queryset with optimizations."""
        return (
            Subscription.objects.select_related(
                "user",
                "subscription_type",
            )
            .prefetch_related(
                "credit_balances__service",
            )
            .order_by("-start_date")
        )

    def _extract_page_number(self):
        """Extract page number from validated form."""
        page = self.filterset.form.cleaned_data.get("page")
        return page if page else 1

    def build_full_context(self):
        """Build complete billing context with subscriptions list."""
        # Step 1: Build queryset
        base_queryset = self._build_subscription_queryset()

        # Step 2: Prepare base context with filters
        self._prepare_base_context(base_queryset)

        # Step 3: Validate form to access cleaned_data
        self.filterset.form.is_valid()

        # Step 4: Get filtered subscriptions
        subscriptions = self.filterset.qs

        # Step 5: Pagination
        page_number = self._extract_page_number()
        paginator = Paginator(subscriptions, 12)

        return {
            "subscriptions": paginator.get_page(page_number),
            "filterset": self.filterset,
            "total_subscriptions": base_queryset.count(),
            "filter_count": self.filter_count,
        }

    @classmethod
    def get_filters_context(cls, request: HttpRequest):
        """Public API: Get lightweight filter context."""
        return cls(request).build_filters_context()

    @classmethod
    def get_full_context(cls, request: HttpRequest):
        """Public API: Get complete billing context."""
        return cls(request).build_full_context()
