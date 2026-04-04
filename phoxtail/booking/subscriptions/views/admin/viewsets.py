from django.urls import path
from django.utils.translation import gettext_lazy as _
from wagtail.snippets.views.snippets import SnippetViewSet

from phoxtail.booking.core.permissions import BookingViewSet

from ...models import (
    Subscription,
    SubscriptionCreditBalance,
    SubscriptionType,
    SubscriptionTypeCreditAllocation,
)
from .views import (
    SubscriptionCreateSearchSubscriptionTypeView,
    SubscriptionCreateSearchUserView,
    admin_billing_filters_form_view,
    admin_billing_filters_view,
    admin_billing_search_view,
    admin_subscription_create_form_view,
    admin_subscription_create_view,
    admin_subscription_list_view,
    admin_subscription_renew_form_view,
    admin_subscription_update_form_view,
)


class BillingManagementViewSet(BookingViewSet):
    name = "billing_management"
    menu_label = _("Billing")
    icon = "payment-card"
    menu_order = 50
    required_permissions = ["access_billing_management"]

    def get_urlpatterns(self):
        return [
            path("", admin_subscription_list_view, name="index"),
            path(
                "admin-subscription-update-form/<uuid:subscription_id>/",
                admin_subscription_update_form_view,
                name="admin_subscription_update_form",
            ),
            path(
                "admin-subscription-renew-form/<uuid:subscription_id>/",
                admin_subscription_renew_form_view,
                name="admin_subscription_renew_form",
            ),
            path(
                "admin-subscription-create-form/",
                admin_subscription_create_form_view,
                name="admin_subscription_create_form",
            ),
            path(
                "admin-subscription-create-action/",
                admin_subscription_create_view,
                name="admin_subscription_create",
            ),
            path(
                "admin-subscription-create-search-user/",
                SubscriptionCreateSearchUserView.as_view(),
                name="admin_subscription_create_search_user",
            ),
            path(
                "admin-subscription-create-search-subscription-type/",
                SubscriptionCreateSearchSubscriptionTypeView.as_view(),
                name="admin_subscription_create_search_subscription_type",
            ),
            path(
                "billing-filters-form/",
                admin_billing_filters_form_view,
                name="admin_billing_filters_form",
            ),
            path(
                "billing-filters/",
                admin_billing_filters_view,
                name="admin_billing_filters",
            ),
            path(
                "billing-search/",
                admin_billing_search_view,
                name="admin_billing_search",
            ),
        ]


class SubscriptionTypeViewSet(SnippetViewSet):
    model = SubscriptionType
    icon = "doc-full"
    menu_label = _("Subscription Types")
    menu_name = _("Subscription Types")
    menu_order = 100
    list_display = [
        "name",
        "price",
        "duration",
        "unpaid_reservation_limit",
        "is_active",
        "is_public",
    ]


class SubscriptionTypeCreditAllocationViewSet(SnippetViewSet):
    model = SubscriptionTypeCreditAllocation
    icon = "plus-inverse"
    menu_label = _("Credit Allocations")
    menu_name = _("Credit Allocations")
    menu_order = 200
    list_display = ["subscription_type", "service", "credits"]


class SubscriptionViewSet(SnippetViewSet):
    model = Subscription
    icon = "payment-card"
    menu_label = _("Subscriptions")
    menu_name = _("Subscriptions")
    menu_order = 300
    list_display = [
        "user",
        "subscription_type",
        "status",
        "is_paid",
        "start_date",
        "end_date",
        "unpaid_reservation_limit",
    ]


class SubscriptionCreditBalanceViewSet(SnippetViewSet):
    model = SubscriptionCreditBalance
    icon = "tick-inverse"
    menu_label = _("Credit Balances")
    menu_name = _("Credit Balances")
    menu_order = 400
    list_display = ["subscription", "service", "credits"]
