"""Mark user email addresses as verified in allauth."""

import sys

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Verify a user's email address in allauth. "
        "Pass an email address or --all-superusers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "email",
            nargs="?",
            help="Email address to verify.",
        )
        parser.add_argument(
            "--all-superusers",
            action="store_true",
            help="Verify all superuser email addresses.",
        )

    def handle(self, *args, **options):
        email = options["email"]
        all_superusers = options["all_superusers"]

        if all_superusers:
            self._verify_superusers()
            return

        if not email:
            self.stderr.write(
                self.style.ERROR("Provide an email address or use --all-superusers.")
            )
            sys.exit(1)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"No user found with email: {email}"))
            sys.exit(1)

        self._verify_user(user)

    def _verify_superusers(self):
        """Verify all superuser emails."""
        superusers = User.objects.filter(is_superuser=True).exclude(email="")
        if not superusers.exists():
            self.stderr.write(
                self.style.WARNING("No superusers with email addresses found.")
            )
            return

        for user in superusers:
            self._verify_user(user)

    def _verify_user(self, user):
        """Verify a single user's email address."""
        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=user.email,
            defaults={"verified": True, "primary": True},
        )
        if not created and not email_address.verified:
            email_address.verified = True
            email_address.primary = True
            email_address.save(update_fields=["verified", "primary"])
            self.stdout.write(self.style.SUCCESS(f"Verified: {user.email}"))
        elif created:
            self.stdout.write(self.style.SUCCESS(f"Verified: {user.email}"))
        else:
            self.stdout.write(f"Already verified: {user.email}")
