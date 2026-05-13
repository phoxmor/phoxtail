"""
Unified command to populate all booking system data.

This command orchestrates the entire data population workflow:
1. Create booking groups
2. Create recurring event templates
3. Generate event instances from templates
4. Create users, subscriptions, and reservations

Each step can be controlled independently via command arguments.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from phoxtail.booking.core.models import BookingGroup
from phoxtail.booking.events.models import Event
from phoxtail.booking.reservations.models import Reservation
from phoxtail.booking.subscriptions.models import Subscription

User = get_user_model()


class Command(BaseCommand):
    help = "Unified command to populate all booking system data with granular control"

    def add_arguments(self, parser):
        # Data creation flags
        parser.add_argument(
            "--groups",
            action="store_true",
            help="Create default booking groups (Beginner, Intermediate, Advanced)",
        )
        parser.add_argument(
            "--locations",
            action="store_true",
            help="Create the default studio location",
        )
        parser.add_argument(
            "--templates",
            action="store_true",
            help="Create recurring event templates (also creates spaces and services)",
        )
        parser.add_argument(
            "--services",
            action="store_true",
            help="Create the default pilates services",
        )
        parser.add_argument(
            "--subscription-types",
            action="store_true",
            help="Create subscription types with credit allocations (requires services)",
        )
        parser.add_argument(
            "--events",
            action="store_true",
            help="Generate event instances from templates",
        )
        parser.add_argument(
            "--reservations",
            action="store_true",
            help="Create users, subscriptions, and reservations",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help=(
                "Run all steps (groups + locations + services + subscription-types + templates + events + reservations)"
            ),
        )

        # Event template options
        parser.add_argument(
            "--location",
            type=str,
            help="Location ID (UUID) for event templates",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date for event templates (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--template-days",
            type=int,
            default=365,
            help="Days to generate templates for (default: 365)",
        )

        # Event generation options
        parser.add_argument(
            "--days-ahead",
            type=int,
            default=14,
            help="Days ahead to generate event instances (default: 14)",
        )

        # Reservation data options
        parser.add_argument(
            "--users",
            type=int,
            default=50,
            help="Number of users to create (default: 50)",
        )
        parser.add_argument(
            "--staff-percentage",
            type=int,
            default=15,
            help="Percentage of users who are staff (default: 15)",
        )
        parser.add_argument(
            "--subscription-percentage",
            type=int,
            default=70,
            help="Percentage of users with subscriptions (default: 70)",
        )
        parser.add_argument(
            "--reservation-percentage",
            type=int,
            default=60,
            help="Percentage of future events with reservations (default: 60)",
        )

        # Utility options
        parser.add_argument(
            "--clear-templates",
            action="store_true",
            help="Clear existing event templates before creating new ones",
        )
        parser.add_argument(
            "--clear-reservations",
            action="store_true",
            help="Clear existing reservation data before creating new data",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible data (default: 42)",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("\n" + "=" * 70 + "\n  BOOKING SYSTEM DATA POPULATION\n" + "=" * 70 + "\n")
        )

        # Determine which steps to run
        run_groups = options["groups"] or options["all"]
        run_locations = options["locations"] or options["all"]
        run_services = options["services"] or options["all"]
        run_subscription_types = options["subscription_types"] or options["all"]
        run_templates = options["templates"] or options["all"]
        run_events = options["events"] or options["all"]
        run_reservations = options["reservations"] or options["all"]

        # Validate: at least one step must be selected
        if not (
            run_groups
            or run_locations
            or run_services
            or run_subscription_types
            or run_templates
            or run_events
            or run_reservations
        ):
            self.stdout.write(
                self.style.ERROR(
                    "\nError: You must specify at least one step to run.\n"
                    "Use --groups, --templates, --events, --reservations, or --all\n"
                )
            )
            return

        # Track statistics
        stats = {
            "groups_created": 0,
            "locations_created": 0,
            "services_created": 0,
            "subscription_types_created": 0,
            "templates_created": 0,
            "events_created": 0,
            "users_created": 0,
            "subscriptions_created": 0,
            "reservations_created": 0,
        }

        # Step 1: Create booking groups
        if run_groups:
            self._run_step(
                step_name="CREATING BOOKING GROUPS",
                command="populate_booking_groups",
                command_options={},
                stats=stats,
            )

        # Step 2: Create location
        if run_locations:
            self._run_step(
                step_name="CREATING LOCATION",
                command="populate_booking_locations",
                command_options={},
                stats=stats,
            )

        # Step 3: Create services
        if run_services:
            self._run_step(
                step_name="CREATING SERVICES",
                command="populate_booking_services",
                command_options={},
                stats=stats,
            )

        # Step 4: Create subscription types
        if run_subscription_types:
            self._run_step(
                step_name="CREATING SUBSCRIPTION TYPES",
                command="populate_booking_subscription_types",
                command_options={
                    "location": options.get("location"),
                },
                stats=stats,
            )

        # Step 5: Create event templates
        if run_templates:
            self._run_step(
                step_name="CREATING EVENT TEMPLATES",
                command="populate_booking_template_events",
                command_options={
                    "clear": options["clear_templates"],
                    "location": options.get("location"),
                    "start_date": options.get("start_date"),
                    "days": options["template_days"],
                },
                stats=stats,
            )

        # Step 5: Generate event instances
        if run_events:
            # Auto-run templates first if none exist and --templates wasn't already run
            template_count = Event.objects.filter(is_recurrence_template=True).count()
            if template_count == 0 and not run_templates:
                self.stdout.write(
                    self.style.WARNING("\n⚠ No event templates found. Running --templates automatically...\n")
                )
                self._run_step(
                    step_name="CREATING EVENT TEMPLATES (auto)",
                    command="populate_booking_template_events",
                    command_options={
                        "clear": options["clear_templates"],
                        "location": options.get("location"),
                        "start_date": options.get("start_date"),
                        "days": options["template_days"],
                    },
                    stats=stats,
                )

            self._run_step(
                step_name="GENERATING EVENT INSTANCES",
                command="populate_booking_events",
                command_options={
                    "days_ahead": options["days_ahead"],
                },
                stats=stats,
            )

        # Step 3: Create users, subscriptions, and reservations
        if run_reservations:
            # Check if events exist
            event_count = Event.objects.filter(is_recurrence_template=False).count()
            if event_count == 0:
                self.stdout.write(self.style.WARNING("\n⚠ No events found. Run with --events first or use --all\n"))
            else:
                # WARNING: populate_booking_system_data with clear_data=True
                # will delete ALL data including events, locations, services, etc.
                # When using --all, we want to clear user data but NOT events/locations/services
                # So we manually clear user-related data here
                if options["all"]:
                    self.stdout.write("\n🧹 Clearing user/reservation data (preserving events)...")
                    from allauth.account.models import EmailAddress

                    from phoxtail.booking.core.models import Staff
                    from phoxtail.booking.reservations.models import Reservation
                    from phoxtail.booking.subscriptions.models import (
                        Subscription,
                        SubscriptionCreditBalance,
                    )

                    User = get_user_model()

                    Reservation.objects.all().delete()
                    SubscriptionCreditBalance.objects.all().delete()
                    Subscription.objects.all().delete()
                    Staff.objects.all().delete()
                    EmailAddress.objects.filter(user__is_superuser=False).delete()
                    User.objects.filter(is_superuser=False).delete()

                    use_clear = False  # Already cleared what we need
                else:
                    use_clear = options["clear_reservations"]

                self._run_step(
                    step_name="CREATING USERS & RESERVATIONS",
                    command="populate_booking_system_data",
                    command_options={
                        "users": options["users"],
                        "staff_percentage": options["staff_percentage"],
                        "subscription_percentage": options["subscription_percentage"],
                        "reservation_percentage": options["reservation_percentage"],
                        "seed": options["seed"],
                        "clear_data": use_clear,
                    },
                    stats=stats,
                )

        # Print summary
        self._print_summary(
            stats,
            run_groups,
            run_locations,
            run_services,
            run_subscription_types,
            run_templates,
            run_events,
            run_reservations,
        )

    def _run_step(self, step_name, command, command_options, stats):
        """Run a management command step with proper formatting"""
        self.stdout.write(
            f"\n{self.style.SUCCESS('━' * 70)}\n"
            f"{self.style.SUCCESS(f'  {step_name}')}\n"
            f"{self.style.SUCCESS('━' * 70)}\n"
        )

        # Count before
        from phoxtail.booking.core.models import Location
        from phoxtail.booking.services.models import Service
        from phoxtail.booking.subscriptions.models import SubscriptionType

        groups_before = BookingGroup.objects.count()
        locations_before = Location.objects.count()
        services_before = Service.objects.count()
        subscription_types_before = SubscriptionType.objects.count()
        templates_before = Event.objects.filter(is_recurrence_template=True).count()
        events_before = Event.objects.filter(is_recurrence_template=False).count()
        users_before = User.objects.filter(is_superuser=False).count()
        subscriptions_before = Subscription.objects.count()
        reservations_before = Reservation.objects.count()

        # Run the command
        call_command(command, **command_options)

        # Count after and update stats
        groups_after = BookingGroup.objects.count()
        locations_after = Location.objects.count()
        services_after = Service.objects.count()
        subscription_types_after = SubscriptionType.objects.count()
        templates_after = Event.objects.filter(is_recurrence_template=True).count()
        events_after = Event.objects.filter(is_recurrence_template=False).count()
        users_after = User.objects.filter(is_superuser=False).count()
        subscriptions_after = Subscription.objects.count()
        reservations_after = Reservation.objects.count()

        # Update stats based on what changed
        stats["groups_created"] += groups_after - groups_before
        stats["locations_created"] += locations_after - locations_before
        stats["services_created"] += services_after - services_before
        stats["subscription_types_created"] += subscription_types_after - subscription_types_before
        stats["templates_created"] += templates_after - templates_before
        stats["events_created"] += events_after - events_before
        stats["users_created"] += users_after - users_before
        stats["subscriptions_created"] += subscriptions_after - subscriptions_before
        stats["reservations_created"] += reservations_after - reservations_before

    def _print_summary(
        self,
        stats,
        run_groups,
        run_locations,
        run_services,
        run_subscription_types,
        run_templates,
        run_events,
        run_reservations,
    ):
        """Print final summary of what was created"""
        self.stdout.write(
            f"\n{self.style.SUCCESS('=' * 70)}\n{self.style.SUCCESS('  SUMMARY')}\n{self.style.SUCCESS('=' * 70)}\n"
        )

        summary_lines = []

        if run_groups:
            summary_lines.append(f"  👥 Booking Groups:   {stats['groups_created']:>6}")

        if run_locations:
            summary_lines.append(f"  📍 Locations:        {stats['locations_created']:>6}")

        if run_services:
            summary_lines.append(f"  🏃 Services:         {stats['services_created']:>6}")

        if run_subscription_types:
            summary_lines.append(f"  🎫 Subscription Types:{stats['subscription_types_created']:>5}")

        if run_templates:
            summary_lines.append(f"  📅 Event Templates:  {stats['templates_created']:>6}")

        if run_events:
            summary_lines.append(f"  🗓️  Event Instances:   {stats['events_created']:>6}")

        if run_reservations:
            summary_lines.append(f"  👤 Users Created:    {stats['users_created']:>6}")
            summary_lines.append(f"  🎫 Subscriptions:    {stats['subscriptions_created']:>6}")
            summary_lines.append(f"  📝 Reservations:     {stats['reservations_created']:>6}")

        for line in summary_lines:
            self.stdout.write(line)

        self.stdout.write(f"{self.style.SUCCESS('=' * 70)}\n")
        self.stdout.write(self.style.SUCCESS("\n✅ Data population completed!\n"))
