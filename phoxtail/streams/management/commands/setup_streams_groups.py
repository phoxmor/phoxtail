from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create default streams permission groups. Safe to run multiple times."

    def handle(self, *args, **options):
        all_perms = Permission.objects.filter(
            content_type__app_label="phoxtail_streams",
            content_type__model="streamsadminpermission",
        )

        if not all_perms.exists():
            self.stderr.write(
                self.style.ERROR("No streams permissions found. Run migrate first.")
            )
            return

        # Streams Admin — full access to everything
        admin_group, _ = Group.objects.get_or_create(name="Streams Admin")
        admin_group.permissions.set(all_perms)
        self.stdout.write(f"  Streams Admin: {all_perms.count()} permissions")

        self.stdout.write(self.style.SUCCESS("Streams groups ready."))
