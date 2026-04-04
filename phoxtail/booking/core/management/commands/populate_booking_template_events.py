from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.utils import timezone

from phoxtail.booking.core.models import Location, Space
from phoxtail.booking.events.constants import EventStatus, RecurrenceFrequency
from phoxtail.booking.events.models import Event
from phoxtail.booking.events.services import EventService
from phoxtail.booking.services.models import Service


class Command(BaseCommand):
    help = "Populate the complete weekly schedule with recurring events"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear all existing events before populating",
        )
        parser.add_argument(
            "--location",
            type=str,
            help="ID (UUID) of the location (will use first location if not specified)",
        )
        parser.add_argument(
            "--start-date",
            type=str,
            help="Start date for events in YYYY-MM-DD format (defaults to Monday of current week)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Number of days to generate recurring events (default: 365)",
        )

    def handle(self, *args, **options):
        # Clear existing events if requested
        if options["clear"]:
            count = Event.objects.all().count()
            Event.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {count} existing events"))

        # Get or create location
        location = self._get_location(options.get("location"))
        if not location:
            self.stdout.write(
                self.style.ERROR("No location found. Please create a location first.")
            )
            return

        # Get or create spaces
        room_a = self._get_or_create_space(location, "Room A", capacity=4)
        room_b = self._get_or_create_space(location, "Room B", capacity=4)

        # Get or create services
        services = self._get_or_create_services()

        # Calculate start date (next Monday if not specified)
        start_date = self._get_start_date(options.get("start_date"), location.timezone)

        # Calculate until date based on days
        days = options["days"]
        until_date = start_date + timezone.timedelta(days=days)

        self.stdout.write(
            self.style.SUCCESS(f"\nPopulating schedule for {location.name}")
        )
        self.stdout.write(f"Start date: {start_date.date()}")
        self.stdout.write(f"Until date: {until_date.date()}\n")

        # Define all recurring events
        events_data = self._get_events_data(
            services, room_a, room_b, start_date, until_date
        )

        # Create events
        created_count = 0
        skipped_count = 0
        for event_data in events_data:
            # Check if template already exists with same pattern
            # (service + space + time + weekdays defines uniqueness for templates)
            existing = Event.objects.filter(
                service=event_data["service"],
                start_datetime=event_data["start_datetime"],
                space=event_data["space"],
                recurrence_byweekday=event_data["recurrence_byweekday"],
                is_recurrence_template=True,
            ).exists()

            if existing:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipped (template exists): {event_data['service'].name} - "
                        f"{event_data['start_datetime'].strftime('%H:%M')}-{event_data['end_datetime'].strftime('%H:%M')} "
                        f"in {event_data['space'].name}"
                    )
                )
                continue

            # Use admin gateway for proper event creation with validation
            EventService().admin.create(**event_data)
            created_count += 1
            self.stdout.write(
                f"Created template: {event_data['service'].name} - "
                f"{event_data['start_datetime'].strftime('%H:%M')}-{event_data['end_datetime'].strftime('%H:%M')} "
                f"in {event_data['space'].name} "
                f"(Days: {self._format_weekdays(event_data['recurrence_byweekday'])})"
            )

        self.stdout.write(
            self.style.SUCCESS(f"\n✓ Created {created_count} recurring event templates")
        )
        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(f"⊘ Skipped {skipped_count} existing events")
            )
        self.stdout.write(
            self.style.SUCCESS(
                "\nRun 'python manage.py populate_recurrence_template_events' to create event instances"
            )
        )

    def _get_location(self, location_id):
        """Get location by ID or return first active location"""
        if location_id:
            return Location.objects.filter(id=location_id, is_active=True).first()
        return Location.objects.filter(is_active=True).first()

    def _get_or_create_space(self, location, name, capacity):
        """Get or create a space"""
        space, created = Space.objects.get_or_create(
            location=location,
            name=name,
            defaults={
                "capacity": capacity,
                "is_active": True,
                "description": f"Reservable space: {name}",
            },
        )
        if created:
            self.stdout.write(f"Created space: {name}")
        return space

    def _get_or_create_services(self):
        """Get or create all required services"""
        services_config = {
            "Reformer Pilates": "Core reformer pilates class",
            "Reformer Athletic Flow": "Athletic flow reformer class",
            "Reformer Recovery Flow": "Recovery-focused reformer class",
            "Prenatal Reformer Pilates": "Prenatal-safe reformer class",
            "Personal": "One-on-one personal training session",
        }

        services = {}
        for name, description in services_config.items():
            service, created = Service.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(f"Created service: {name}")
            services[name] = service

        return services

    def _get_start_date(self, date_str, tz):
        """Get start date, defaulting to Monday of current week"""
        if date_str:
            naive_date = datetime.strptime(date_str, "%Y-%m-%d")
            return timezone.make_aware(
                datetime.combine(naive_date, time(9, 0)), timezone=tz
            )

        # Default to Monday of current week at 9:00 AM
        now = timezone.now().astimezone(tz)
        days_back = now.weekday()  # Monday is 0, so this is how many days since Monday
        current_monday = now - timezone.timedelta(days=days_back)
        return timezone.make_aware(
            datetime.combine(current_monday.date(), time(9, 0)), timezone=tz
        )

    def _format_weekdays(self, weekdays):
        """Format weekday list for display"""
        day_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        return ", ".join([day_map[d] for d in sorted(weekdays)])

    def _get_events_data(self, services, room_a, room_b, start_date, until_date):
        """Define all recurring events configuration"""

        # Helper to create datetime with specific time for a given weekday
        def make_time(hour, minute=0, weekday=None):
            """
            Create a timezone-aware datetime for the given hour/minute.
            If weekday is specified, finds the next occurrence of that weekday from start_date.

            Args:
                hour: Hour of the day (0-23)
                minute: Minute of the hour (0-59)
                weekday: Day of week (0=Mon, 6=Sun). If None, uses start_date.
            """
            base_date = start_date.date()

            if weekday is not None:
                # Calculate days until the target weekday
                current_weekday = base_date.weekday()
                days_ahead = weekday - current_weekday
                if days_ahead < 0:  # Target day already happened this week
                    days_ahead += 7
                base_date = base_date + timezone.timedelta(days=days_ahead)

            return timezone.make_aware(
                datetime.combine(base_date, time(hour, minute)),
                timezone=start_date.tzinfo,
            )

        return [
            # ===== REFORMER PILATES - ROOM A =====
            # 09:00-10:00 Mon-Sat
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(9, 0, weekday=0),
                "end_datetime": make_time(10, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4, 5],
                "recurrence_until": until_date,
            },
            # 10:00-11:00 Mon, Tue, Wed, Thu, Fri, Sat
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(10, 0, weekday=0),
                "end_datetime": make_time(11, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4, 5],
                "recurrence_until": until_date,
            },
            # 11:00-12:00 Mon-Sat
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(11, 0, weekday=0),
                "end_datetime": make_time(12, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4, 5],
                "recurrence_until": until_date,
            },
            # 12:00-13:00 Mon-Sat
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(12, 0, weekday=0),
                "end_datetime": make_time(13, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4, 5],
                "recurrence_until": until_date,
            },
            # 13:00-14:00 Mon-Sat
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(13, 0, weekday=0),
                "end_datetime": make_time(14, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4, 5],
                "recurrence_until": until_date,
            },
            # 16:00-17:00 Mon, Tue, Thu, Fri
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(16, 0, weekday=0),
                "end_datetime": make_time(17, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 3, 4],
                "recurrence_until": until_date,
            },
            # 17:00-18:00 Mon-Fri
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(17, 0, weekday=0),
                "end_datetime": make_time(18, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4],
                "recurrence_until": until_date,
            },
            # 18:00-19:00 Mon-Fri
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(18, 0, weekday=0),
                "end_datetime": make_time(19, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4],
                "recurrence_until": until_date,
            },
            # 19:00-20:00 Mon-Fri
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(19, 0, weekday=0),
                "end_datetime": make_time(20, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4],
                "recurrence_until": until_date,
            },
            # 20:00-21:00 Mon-Fri
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(20, 0, weekday=0),
                "end_datetime": make_time(21, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4],
                "recurrence_until": until_date,
            },
            # 21:00-22:00 Mon-Fri Room A
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(21, 0, weekday=0),
                "end_datetime": make_time(22, 0, weekday=0),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4],
                "recurrence_until": until_date,
            },
            # ===== REFORMER PILATES - ROOM B =====
            # 10:00-11:00 Sat
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(10, 0, weekday=5),
                "end_datetime": make_time(11, 0, weekday=5),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [5],
                "recurrence_until": until_date,
            },
            # 12:00-13:00 Sat
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(12, 0, weekday=5),
                "end_datetime": make_time(13, 0, weekday=5),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [5],
                "recurrence_until": until_date,
            },
            # 18:00-19:00 Fri
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(18, 0, weekday=4),
                "end_datetime": make_time(19, 0, weekday=4),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [4],
                "recurrence_until": until_date,
            },
            # 18:00-19:00 Mon-Thu (Personal)
            {
                "service": services["Personal"],
                "start_datetime": make_time(18, 0, weekday=0),
                "end_datetime": make_time(19, 0, weekday=0),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3],
                "recurrence_until": until_date,
            },
            # 19:00-20:00 Tue, Fri (Reformer Pilates)
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(19, 0, weekday=1),
                "end_datetime": make_time(20, 0, weekday=1),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [1, 4],
                "recurrence_until": until_date,
            },
            # 20:00-21:00 Mon, Wed, Thu, Fri (Reformer Pilates)
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(20, 0, weekday=0),
                "end_datetime": make_time(21, 0, weekday=0),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 2, 3, 4],
                "recurrence_until": until_date,
            },
            # 21:00-22:00 Tue, Fri Room B (Reformer Pilates)
            {
                "service": services["Reformer Pilates"],
                "start_datetime": make_time(21, 0, weekday=1),
                "end_datetime": make_time(22, 0, weekday=1),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [1, 4],
                "recurrence_until": until_date,
            },
            # ===== REFORMER ATHLETIC FLOW =====
            # 10:00-11:00 Tue, Room A
            {
                "service": services["Reformer Athletic Flow"],
                "start_datetime": make_time(10, 0, weekday=1),
                "end_datetime": make_time(11, 0, weekday=1),
                "space": room_b,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [1],
                "recurrence_until": until_date,
            },
            # 09:00-10:00 Sat, Room B
            {
                "service": services["Reformer Athletic Flow"],
                "start_datetime": make_time(9, 0, weekday=5),
                "end_datetime": make_time(10, 0, weekday=5),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [5],
                "recurrence_until": until_date,
            },
            # 19:00-20:00 Mon, Wed, Room B (Reformer Athletic Flow)
            {
                "service": services["Reformer Athletic Flow"],
                "start_datetime": make_time(19, 0, weekday=0),
                "end_datetime": make_time(20, 0, weekday=0),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 2],
                "recurrence_until": until_date,
            },
            # 21:00-22:00 Mon, Wed, Thu Room B (Reformer Athletic Flow)
            {
                "service": services["Reformer Athletic Flow"],
                "start_datetime": make_time(21, 0, weekday=0),
                "end_datetime": make_time(22, 0, weekday=0),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 2, 3],
                "recurrence_until": until_date,
            },
            # ===== REFORMER RECOVERY FLOW =====
            # 16:00-17:00 Wed, Room A
            {
                "service": services["Reformer Recovery Flow"],
                "start_datetime": make_time(16, 0, weekday=2),
                "end_datetime": make_time(17, 0, weekday=2),
                "space": room_a,
                "capacity": 12,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [2],
                "recurrence_until": until_date,
            },
            # 19:00-20:00 Thu, Room B (Reformer Recovery Flow)
            {
                "service": services["Reformer Recovery Flow"],
                "start_datetime": make_time(19, 0, weekday=3),
                "end_datetime": make_time(20, 0, weekday=3),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [3],
                "recurrence_until": until_date,
            },
            # 20:00-21:00 Tue, Room B (Reformer Recovery Flow)
            {
                "service": services["Reformer Recovery Flow"],
                "start_datetime": make_time(20, 0, weekday=1),
                "end_datetime": make_time(21, 0, weekday=1),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [1],
                "recurrence_until": until_date,
            },
            # ===== PRENATAL REFORMER PILATES =====
            # 12:00-13:00 Tue, Thu, Room B
            {
                "service": services["Prenatal Reformer Pilates"],
                "start_datetime": make_time(12, 0, weekday=1),
                "end_datetime": make_time(13, 0, weekday=1),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [1, 3],
                "recurrence_until": until_date,
            },
            # 13:00-14:00 Thu, Room B
            {
                "service": services["Prenatal Reformer Pilates"],
                "start_datetime": make_time(13, 0, weekday=3),
                "end_datetime": make_time(14, 0, weekday=3),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [3],
                "recurrence_until": until_date,
            },
            # ===== PERSONAL SESSIONS - ROOM B =====
            # 09:00-10:00 Thu
            {
                "service": services["Personal"],
                "start_datetime": make_time(9, 0, weekday=3),
                "end_datetime": make_time(10, 0, weekday=3),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [3],
                "recurrence_until": until_date,
            },
            # 11:00-12:00 Mon-Sat
            {
                "service": services["Personal"],
                "start_datetime": make_time(11, 0, weekday=0),
                "end_datetime": make_time(12, 0, weekday=0),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [0, 1, 2, 3, 4, 5],
                "recurrence_until": until_date,
            },
            # 14:00-15:00 Sat
            {
                "service": services["Personal"],
                "start_datetime": make_time(14, 0, weekday=5),
                "end_datetime": make_time(15, 0, weekday=5),
                "space": room_b,
                "capacity": 1,
                "status": EventStatus.CONFIRMED,
                "recurrence_freq": RecurrenceFrequency.WEEKLY,
                "recurrence_interval": 1,
                "recurrence_byweekday": [5],
                "recurrence_until": until_date,
            },
        ]
