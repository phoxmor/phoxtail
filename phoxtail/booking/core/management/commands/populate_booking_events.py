from django.core.management.base import BaseCommand

from phoxtail.booking.events.tasks import generate_recurring_events_task


class Command(BaseCommand):
    help = "Generate recurring event instances from active templates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days-ahead",
            type=int,
            default=7,
            help="Number of days ahead to generate events (default: 7)",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            help="Run the task asynchronously using Celery (returns immediately)",
        )

    def handle(self, *args, **options):
        days_ahead = options["days_ahead"]
        run_async = options["async"]

        self.stdout.write(self.style.SUCCESS(f"Generating recurring events ({days_ahead} days ahead)..."))

        if run_async:
            # Run asynchronously via Celery
            task = generate_recurring_events_task.delay(days_ahead=days_ahead)
            self.stdout.write(self.style.SUCCESS(f"Task queued for async execution! Task ID: {task.id}"))
            self.stdout.write("Check Celery worker logs for progress: docker compose logs celery-worker -f")
        else:
            # Run synchronously (blocking)
            self.stdout.write("Running synchronously (this may take a moment)...")
            total_created = generate_recurring_events_task(days_ahead=days_ahead)
            self.stdout.write(self.style.SUCCESS(f"\nTotal events created: {total_created}"))
