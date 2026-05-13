from decimal import Decimal

from django.core.management.base import BaseCommand

from phoxtail.booking.core.models import Location
from phoxtail.booking.services.models import Service
from phoxtail.booking.subscriptions.models import (
    SubscriptionType,
    SubscriptionTypeCreditAllocation,
)


class Command(BaseCommand):
    help = "Create the default subscription types with credit allocations. Requires Location and Services to exist."

    SUBSCRIPTION_TYPES = [
        {
            "name": "4 Classes",
            "description": (
                "Participation in small group classes up to 4 people."
                " Online reservation management platform. Duration 1 month"
            ),
            "price": Decimal("55.00"),
            "duration": 30,
            "credits": 4,
            "unpaid_reservation_limit": 1,
            "type": "group",
        },
        {
            "name": "8 Classes",
            "description": (
                "Participation in small group classes up to 4 people."
                " Online reservation management platform. Duration 1 month"
            ),
            "price": Decimal("99.00"),
            "duration": 30,
            "credits": 8,
            "unpaid_reservation_limit": 1,
            "type": "group",
        },
        {
            "name": "12 Classes",
            "description": (
                "Participation in small group classes up to 4 people."
                " Online reservation management platform. Duration 1 month."
            ),
            "price": Decimal("130.00"),
            "duration": 30,
            "credits": 12,
            "unpaid_reservation_limit": 1,
            "type": "group",
        },
        {
            "name": "20 Classes",
            "description": (
                "Participation in small group classes up to 4 people."
                " Online reservation management platform. Duration 3 months"
            ),
            "price": Decimal("240.00"),
            "duration": 90,
            "credits": 20,
            "unpaid_reservation_limit": 1,
            "type": "group",
        },
        {
            "name": "Drop In",
            "description": "Single class participation in small group class up to 4 people. No time limit",
            "price": Decimal("15.00"),
            "duration": None,
            "credits": 1,
            "unpaid_reservation_limit": 1,
            "type": "group",
        },
        {
            "name": "Personal - Drop In",
            "description": "Single personal training session with dedicated instructor. No time limit",
            "price": Decimal("30.00"),
            "duration": None,
            "credits": 1,
            "unpaid_reservation_limit": 1,
            "type": "personal",
        },
        {
            "name": "Personal - 10 Classes",
            "description": "10 personal training sessions with dedicated instructor. Duration 2 months",
            "price": Decimal("250.00"),
            "duration": 60,
            "credits": 10,
            "unpaid_reservation_limit": 1,
            "type": "personal",
        },
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--location",
            type=str,
            help="Location ID (UUID) to assign subscription types to (uses first active location if not specified)",
        )

    def handle(self, *args, **options):
        location = self._get_location(options.get("location"))
        if not location:
            self.stdout.write(self.style.ERROR("No active location found. Run populate_booking_locations first."))
            return

        personal_service = Service.objects.filter(name="Personal", is_active=True).first()
        non_personal_services = list(Service.objects.filter(is_active=True).exclude(name="Personal"))

        if not personal_service and not non_personal_services:
            self.stdout.write(
                self.style.ERROR("No services found. Run populate_booking_template_events first (it creates services).")
            )
            return

        for data in self.SUBSCRIPTION_TYPES:
            sub_type, created = SubscriptionType.objects.get_or_create(
                location=location,
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "price": data["price"],
                    "duration": data.get("duration"),
                    "credits": data.get("credits"),
                    "unpaid_reservation_limit": data.get("unpaid_reservation_limit", 1),
                    "is_active": True,
                },
            )

            if created:
                if data["type"] == "personal":
                    if personal_service:
                        SubscriptionTypeCreditAllocation.objects.create(
                            subscription_type=sub_type,
                            service=personal_service,
                            credits=0,
                        )
                else:
                    for service in non_personal_services:
                        SubscriptionTypeCreditAllocation.objects.create(
                            subscription_type=sub_type,
                            service=service,
                            credits=0,
                        )

            status = "Created" if created else "Already exists"
            self.stdout.write(f"{status}: {sub_type.name}")

        self.stdout.write(self.style.SUCCESS("Done."))

    def _get_location(self, location_id):
        if location_id:
            return Location.objects.filter(id=location_id, is_active=True).first()
        return Location.objects.filter(is_active=True).first()
