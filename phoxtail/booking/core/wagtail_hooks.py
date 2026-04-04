from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from wagtail import hooks
from wagtail.admin.viewsets.model import ModelViewSetGroup
from wagtail.snippets.models import register_snippet

from phoxtail.booking.reservations.viewsets import ReservationViewSet
from phoxtail.booking.services.viewsets import ServiceViewSet
from phoxtail.booking.subscriptions.views.admin.viewsets import (
    BillingManagementViewSet,
    SubscriptionCreditBalanceViewSet,
    SubscriptionTypeCreditAllocationViewSet,
    SubscriptionTypeViewSet,
    SubscriptionViewSet,
)

from ..events.viewsets import (
    BookingManagementViewSet,
    EventGenerationScheduleExclusionViewSet,
    EventGenerationScheduleViewSet,
    EventViewSet,
    SchedulingManagementViewSet,
)
from .admin.users.viewsets import UsersManagementViewSet
from .permissions import BookingAdminPermission
from .viewsets import (
    BookingGroupViewSet,
    BookingSettingsViewSet,
    LocationViewSet,
    SpaceViewSet,
    StaffViewSet,
)


@hooks.register("register_permissions")
def register_booking_permissions():
    content_type = ContentType.objects.get_for_model(BookingAdminPermission)
    return Permission.objects.filter(content_type=content_type)


@hooks.register("register_admin_viewset")
class BookingViewSetGroup(ModelViewSetGroup):
    menu_label = _("Booking")
    menu_icon = "calendar-month"
    show_in_menu = True
    menu_order = 000
    items = (
        BookingManagementViewSet,
        BillingManagementViewSet,
        SchedulingManagementViewSet,
        UsersManagementViewSet,
        BookingSettingsViewSet,
    )


# Register snippets
register_snippet(LocationViewSet)
register_snippet(StaffViewSet)
register_snippet(BookingGroupViewSet)
register_snippet(ServiceViewSet)
register_snippet(SubscriptionTypeViewSet)
register_snippet(SubscriptionViewSet)
register_snippet(EventViewSet)
register_snippet(EventGenerationScheduleViewSet)
register_snippet(EventGenerationScheduleExclusionViewSet)
register_snippet(ReservationViewSet)
register_snippet(SpaceViewSet)
register_snippet(SubscriptionCreditBalanceViewSet)
register_snippet(SubscriptionTypeCreditAllocationViewSet)
