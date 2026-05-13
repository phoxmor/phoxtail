from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

# Snippet app labels that contain booking-related models
SNIPPET_APP_LABELS = [
    "phoxtail_booking_core",
    "phoxtail_booking_events",
    "phoxtail_booking_reservations",
    "phoxtail_booking_services",
    "phoxtail_booking_subscriptions",
]

# Config models — settings-tier, managed via the settings page
CONFIG_MODELS = [
    "location",
    "staff",
    "space",
    "bookinggroup",
    "service",
    "subscriptiontype",
    "eventgenerationschedule",
]

# Operational models — day-to-day transactional data
OPERATIONAL_MODELS = [
    "event",
    "reservation",
    "subscription",
    "subscriptioncreditbalance",
    "subscriptiontypecreditallocation",
]

# Staff-visible subset of config models (booking/scheduling relevant)
STAFF_CONFIG_MODELS = ["location", "staff", "service", "space"]

# Staff-visible subset of operational models (booking/scheduling relevant)
STAFF_OPERATIONAL_MODELS = ["event", "reservation"]


class Command(BaseCommand):
    help = "Create default booking permission groups. Safe to run multiple times."

    def _snippet_perm_ids(self, models, actions=None):
        """Get snippet permission IDs for given model names and optional action filter."""
        qs = Permission.objects.filter(
            content_type__app_label__in=SNIPPET_APP_LABELS,
            content_type__model__in=models,
        )
        if actions:
            prefixes = tuple(f"{a}_" for a in actions)
            qs = qs.filter(codename__regex=r"^(%s)" % "|".join(f"{a}_" for a in actions))
        return set(qs.values_list("pk", flat=True))

    def _set_group_perms(self, group_name, perm_ids):
        """Create or update a group with the given permission IDs."""
        group, _ = Group.objects.get_or_create(name=group_name)
        group.permissions.set(perm_ids)
        self.stdout.write(f"  {group_name}: {len(perm_ids)} permissions")

    def handle(self, *args, **options):
        custom_perms = Permission.objects.filter(
            content_type__app_label="phoxtail_booking_core",
            content_type__model="bookingadminpermission",
        )

        if not custom_perms.exists():
            self.stderr.write(self.style.ERROR("No booking permissions found. Run migrate first."))
            return

        all_custom_ids = set(custom_perms.values_list("pk", flat=True))
        all_snippet_models = CONFIG_MODELS + OPERATIONAL_MODELS

        # ── Booking Admin — full access to everything ──
        admin_ids = all_custom_ids | self._snippet_perm_ids(all_snippet_models)
        self._set_group_perms("Booking Admin", admin_ids)

        # ── Booking Manager — all custom except settings, full CRUD operational,
        #    view-only config ──
        manager_custom_ids = set(custom_perms.exclude(codename="access_booking_settings").values_list("pk", flat=True))
        manager_ids = (
            manager_custom_ids
            | self._snippet_perm_ids(OPERATIONAL_MODELS)
            | self._snippet_perm_ids(CONFIG_MODELS, actions=["view"])
        )
        self._set_group_perms("Booking Manager", manager_ids)

        # ── Booking Staff — booking + scheduling access, manage reservations,
        #    view config subset, view + change operational subset ──
        staff_custom_ids = set(
            custom_perms.filter(
                codename__in=[
                    "access_booking_management",
                    "manage_reservations",
                    "access_scheduling_management",
                ]
            ).values_list("pk", flat=True)
        )
        staff_ids = (
            staff_custom_ids
            | self._snippet_perm_ids(STAFF_CONFIG_MODELS, actions=["view"])
            | self._snippet_perm_ids(STAFF_OPERATIONAL_MODELS, actions=["view", "change"])
        )
        self._set_group_perms("Booking Staff", staff_ids)

        # ── Booking Viewer — read-only access to all views ──
        viewer_custom_ids = set(custom_perms.filter(codename__startswith="access_").values_list("pk", flat=True))
        viewer_ids = viewer_custom_ids | self._snippet_perm_ids(all_snippet_models, actions=["view"])
        self._set_group_perms("Booking Viewer", viewer_ids)

        self.stdout.write(self.style.SUCCESS("Booking groups ready."))
