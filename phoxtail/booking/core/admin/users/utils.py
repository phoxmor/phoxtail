from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import HttpRequest

from phoxtail.booking.core.models import BookingGroup

from .filters import UserFilter


class UsersContextBuilder:
    """Builds context for the users management list and filter views."""

    def __init__(self, request: HttpRequest):
        self.request = request
        self.query_params = None
        self.filterset = None
        self.filter_count = None

    def _extract_query_params(self):
        self.query_params = (
            self.request.GET.copy()
            if self.request.method == "GET"
            else self.request.POST.copy()
        )

    def _create_filterset(self, base_queryset):
        self.filterset = UserFilter(self.query_params, queryset=base_queryset)

    def _calculate_filter_count(self):
        form = self.filterset.form
        form.is_valid()

        filter_keys = [k for k in form.cleaned_data if k not in ["page", "search"]]
        self.filter_count = sum(
            1
            for k, v in form.cleaned_data.items()
            if k in filter_keys and v not in ["", None]
        )

    def _prepare_base_context(self, base_queryset):
        self._extract_query_params()
        self._create_filterset(base_queryset)
        self._calculate_filter_count()

    def build_filters_context(self):
        User = get_user_model()
        self._prepare_base_context(base_queryset=User.objects.none())
        return {
            "filterset": self.filterset,
            "filter_count": self.filter_count,
        }

    def _build_user_queryset(self):
        User = get_user_model()
        return User.objects.select_related("gender").order_by("-date_joined")

    def _extract_page_number(self):
        page = self.filterset.form.cleaned_data.get("page")
        return page if page else 1

    def build_full_context(self):
        base_queryset = self._build_user_queryset()

        self._prepare_base_context(base_queryset)

        self.filterset.form.is_valid()

        users = self.filterset.qs

        page_number = self._extract_page_number()
        paginator = Paginator(users, 12)

        return {
            "users": paginator.get_page(page_number),
            "filterset": self.filterset,
            "total_users": base_queryset.count(),
            "filter_count": self.filter_count,
        }

    @classmethod
    def get_filters_context(cls, request: HttpRequest):
        return cls(request).build_filters_context()

    @classmethod
    def get_full_context(cls, request: HttpRequest):
        return cls(request).build_full_context()


def _sync_booking_groups(user, booking_groups):
    """Sync a user's BookingGroup membership to match the given queryset."""
    if booking_groups is None:
        return

    current_pks = set(user.booking_groups.values_list("pk", flat=True))
    new_pks = set(g.pk for g in booking_groups)

    for group in BookingGroup.objects.filter(pk__in=current_pks - new_pks):
        group.members.remove(user)
    for group in BookingGroup.objects.filter(pk__in=new_pks - current_pks):
        group.members.add(user)
