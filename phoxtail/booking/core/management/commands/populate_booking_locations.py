from django.core.management.base import BaseCommand
from django_countries.fields import Country
from phonenumber_field.phonenumber import PhoneNumber

from phoxtail.booking.core.models import Location, Space


class Command(BaseCommand):
    help = "Create the default studio location and its spaces."

    LOCATION = {
        "name": "Pilates Studio",
        "description": (
            "A premier Pilates studio offering transformative movement experiences."
            " Our expert instructors guide you through mindful, precise movements"
            " that build strength, flexibility, and body awareness."
        ),
        "street_address_line1": "",
        "street_address_line2": "",
        "city": "Athens",
        "state_province": "Attica",
        "country": "GR",
        "postal_code": "",
        "timezone": "Europe/Athens",
        "latitude": 37.9838,
        "longitude": 23.7275,
        "phone_number": "+302101000000",
        "email": "info@pilatesstudio.com",
        "website": "https://www.pilatesstudio.com",
    }

    SPACES = [
        {
            "name": "Room A",
            "description": "Main studio room for pilates classes",
            "capacity": 4,
        },
        {
            "name": "Room B",
            "description": "Secondary studio room for pilates classes",
            "capacity": 4,
        },
    ]

    def handle(self, *args, **options):
        data = self.LOCATION
        location, created = Location.objects.get_or_create(
            name=data["name"],
            defaults={
                "description": data["description"],
                "street_address_line1": data["street_address_line1"],
                "street_address_line2": data["street_address_line2"],
                "city": data["city"],
                "state_province": data["state_province"],
                "country": Country(code=data["country"]),
                "postal_code": data["postal_code"],
                "timezone": data["timezone"],
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "phone_number": PhoneNumber.from_string(data["phone_number"]),
                "email": data["email"],
                "website": data["website"],
                "is_active": True,
            },
        )
        status = "Created" if created else "Already exists"
        self.stdout.write(f"{status}: {location.name}")

        for space_data in self.SPACES:
            space, space_created = Space.objects.get_or_create(
                location=location,
                name=space_data["name"],
                defaults={
                    "description": space_data["description"],
                    "capacity": space_data["capacity"],
                    "is_active": True,
                },
            )
            space_status = "Created" if space_created else "Already exists"
            self.stdout.write(f"  {space_status}: {space.name} (capacity {space.capacity})")

        self.stdout.write(self.style.SUCCESS("Done."))
