from django.core.management.base import BaseCommand

from phoxtail.booking.core.models import BookingGroup


class Command(BaseCommand):
    help = "Create the default skill-level booking groups (Beginner, Intermediate, Advanced)."

    GROUPS = [
        {
            "name": "Beginner",
            "slug": "beginner",
            "description": "Open to new members and those just starting their journey.",
        },
        {
            "name": "Intermediate",
            "slug": "intermediate",
            "description": "For members who have completed a foundation program and are developing basic skills.",
        },
        {
            "name": "Advanced",
            "slug": "advanced",
            "description": "Reserved for experienced members with strong technique and instructor approval.",
        },
    ]

    def handle(self, *args, **options):
        for data in self.GROUPS:
            group, created = BookingGroup.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_active": True,
                },
            )
            status = "Created" if created else "Already exists"
            self.stdout.write(f"{status}: {group.name}")

        self.stdout.write(self.style.SUCCESS("Done."))
