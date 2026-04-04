from django.urls import include, path

from phoxtail.booking.subscriptions.constants import SubscriptionStatus
from phoxtail.dashboard.registry import DashboardModule, registry

module = DashboardModule(
    app_name="booking",
    url_prefix="booking/",
    url_patterns=[
        path("events/", include("phoxtail.booking.events.urls")),
        path("services/", include("phoxtail.booking.services.urls")),
        path("reservations/", include("phoxtail.booking.reservations.urls")),
        path(
            "subscriptions/",
            include("phoxtail.booking.subscriptions.urls"),
        ),
    ],
)

module.add_nav_item(
    label="Bookings",
    url_name="dashboard:booking:reservations:list",
    icon="event",
    order=10,
)

# Nav items
module.add_nav_item(
    label="Book",
    url_name="dashboard:booking:events:list",
    icon="calendar_add_on",
    order=20,
)


module.add_nav_item(
    label="Plans",
    url_name="dashboard:booking:subscriptions:subscription-list",
    icon="payment_card",
    order=30,
)

module.add_nav_item(
    label="Buy Plan",
    url_name="dashboard:booking:subscriptions:subscription-type-list",
    icon="add_shopping_cart",
    order=40,
)


module.add_nav_item(
    label="Classes",
    url_name="dashboard:booking:services:list",
    icon="view_apps",
    order=50,
)


# Widgets
def get_upcoming_reservations(request):
    from phoxtail.booking.reservations.constants import ReservationStatus
    from phoxtail.booking.reservations.models import Reservation

    reservations = (
        Reservation.objects.filter(user=request.user)
        .exclude(status__in=[ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW])
        .select_related(
            "event", "event__service", "event__space", "event__service__palette"
        )
        .order_by("event__start_datetime")[:5]
    )
    return {"reservations": reservations}


def get_active_subscriptions(request):
    from phoxtail.booking.subscriptions.models import Subscription

    subscriptions = (
        Subscription.objects.filter(user=request.user)
        .exclude(status=SubscriptionStatus.ARCHIVED)
        .select_related("subscription_type")
        .prefetch_related("credit_balances", "credit_balances__service")
        .order_by("-start_date")[:5]
    )
    return {"subscriptions": subscriptions}


module.add_widget(
    template_name="phoxtail_booking_core/dashboard/widgets/upcoming_reservations.html",
    context_function=get_upcoming_reservations,
    order=10,
    css_files=["phoxtail_booking_reservations/css/public.css"],
)

module.add_widget(
    template_name="phoxtail_booking_core/dashboard/widgets/active_subscriptions.html",
    context_function=get_active_subscriptions,
    order=20,
    css_files=["phoxtail_booking_subscriptions/css/public.css"],
)

registry.register(module)
