"""
Send account activation emails to migrated users.

This command generates a one-time password setup link for users who have
never logged in (migrated from a previous platform) and sends them a
welcome/activation email so they can set their own password.

Usage:
    # Test with superusers first
    python manage.py send_account_activation_emails --superusers

    # Send to all migrated users (never logged in, no usable password)
    python manage.py send_account_activation_emails

    # Dry run to see who would receive the email
    python manage.py send_account_activation_emails --dry-run
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


class Command(BaseCommand):
    help = "Send account activation emails to migrated users"

    def add_arguments(self, parser):
        parser.add_argument(
            "--superusers",
            action="store_true",
            help="Send only to superusers (for testing before the real send)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print who would receive the email without actually sending",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        superusers_only = options["superusers"]

        if superusers_only:
            users = User.objects.filter(is_superuser=True, is_active=True)
            label = "superusers"
        else:
            users = User.objects.filter(
                is_active=True,
                last_login=None,
                is_superuser=False,
            ).exclude(password__startswith="!")  # exclude unusable passwords already set
            label = "migrated users"

        count = users.count()

        if count == 0:
            self.stdout.write(self.style.WARNING(f"\nNo {label} found to email.\n"))
            return

        self.stdout.write(
            self.style.SUCCESS(f"\n{'DRY RUN — ' if dry_run else ''}Sending activation emails to {count} {label}...\n")
        )

        sent = 0
        failed = 0

        protocol = "https" if not settings.DEBUG else "http"
        domain = settings.WAGTAILADMIN_BASE_URL.replace("https://", "").replace("http://", "")

        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            activation_url = f"{protocol}://{domain}/en/accounts/password/reset/key/{uid}-{token}/"

            if dry_run:
                self.stdout.write(f"  Would email: {user.email} ({user.get_full_name()})")
                self.stdout.write(f"    Link: {activation_url}")
                continue

            try:
                subject = render_to_string(
                    "account/email/account_activation_subject.txt",
                    {"user": user},
                ).strip()

                body = render_to_string(
                    "account/email/account_activation_message.txt",
                    {
                        "user": user,
                        "activation_url": activation_url,
                        "domain": domain,
                    },
                )

                send_mail(
                    subject=subject,
                    message=body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )

                self.stdout.write(f"  Sent: {user.email}")
                sent += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Failed: {user.email} — {e}"))
                failed += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"\n{'=' * 50}\n  Sent:   {sent}\n  Failed: {failed}\n{'=' * 50}\n"))
