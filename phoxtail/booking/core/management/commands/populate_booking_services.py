from django.core.management.base import BaseCommand

from phoxtail.booking.services.models import Service
from phoxtail.design.models import Palette


class Command(BaseCommand):
    help = "Create the default pilates services."

    SERVICES = [
        {"name": "Reformer Pilates", "palette": "blue"},
        {"name": "Reformer Athletic Flow", "palette": "orange"},
        {"name": "Reformer Recovery Flow", "palette": "emerald"},
        {"name": "Prenatal Reformer Pilates", "palette": "pink"},
        {"name": "Personal", "palette": "purple"},
    ]

    DESCRIPTIONS = {
        "Reformer Pilates": "Core reformer pilates class focusing on precision, control, and mindful movement.",
        "Reformer Athletic Flow": "Athletic flow reformer class for building strength and endurance.",
        "Reformer Recovery Flow": "Recovery-focused reformer class for gentle movement and restoration.",
        "Prenatal Reformer Pilates": "Prenatal-safe reformer class designed for expecting mothers.",
        "Personal": "One-on-one personal training session with dedicated instructor.",
    }

    def handle(self, *args, **options):
        for data in self.SERVICES:
            palette = Palette.objects.filter(title=data["palette"]).first()
            if not palette:
                self.stdout.write(
                    self.style.WARNING(
                        f"Palette '{data['palette']}' not found for '{data['name']}'. "
                        f"Ensure the palette exists in the Design section of the admin."
                    )
                )

            service, created = Service.objects.get_or_create(
                name=data["name"],
                defaults={
                    "description": self.DESCRIPTIONS[data["name"]],
                    "is_active": True,
                    "palette": palette,
                },
            )
            if not created and palette and service.palette != palette:
                service.palette = palette
                service.save(update_fields=["palette"])

            status = "Created" if created else "Already exists"
            self.stdout.write(f"{status}: {service.name}")

        self.stdout.write(self.style.SUCCESS("Done."))
