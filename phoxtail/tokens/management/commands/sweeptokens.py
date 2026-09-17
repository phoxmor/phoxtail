from django.core.management.base import BaseCommand

from phoxtail.tokens.sweep import RETENTION_DAYS, sweep


class Command(BaseCommand):
    help = "Remove token rows that can no longer open anything and are past their retention."

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days",
            type=int,
            default=RETENTION_DAYS,
            help=f"Keep dead rows this many days (default {RETENTION_DAYS}).",
        )

    def handle(self, *args, **options):
        removed = sweep(options["retention_days"])
        self.stdout.write(
            f"Removed {removed['phoxtail']} of phoxtail's dead token rows "
            f"and {removed['server']} of the authorization server's."
        )
