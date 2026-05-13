import random
from datetime import timedelta
from decimal import Decimal

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_countries.fields import Country
from faker import Faker
from phonenumber_field.phonenumber import PhoneNumber

from phoxtail.booking.core.models import BookingGroup, Location, Space, Staff
from phoxtail.booking.events.models import Event
from phoxtail.booking.reservations.models import Reservation
from phoxtail.booking.services.models import Service
from phoxtail.booking.subscriptions.models import (
    Subscription,
    SubscriptionCreditBalance,
    SubscriptionType,
    SubscriptionTypeCreditAllocation,
)
from phoxtail.booking.subscriptions.services import SubscriptionService
from phoxtail.design.models import Palette
from phoxtail.users.models import Gender

User = get_user_model()


class PilatesStudioDataGenerator:
    """Advanced data generator for a realistic pilates studio"""

    def __init__(self, locale="en_US"):
        self.fake = Faker(locale)
        Faker.seed(42)  # For reproducible data

        # Pilates-specific data
        self.pilates_services = [
            {
                "name": "Reformer Pilates",
                "palette": "blue",
            },
            {
                "name": "Reformer Athletic Flow",
                "palette": "orange",
            },
            {
                "name": "Reformer Recovery Flow",
                "palette": "emerald",
            },
            {
                "name": "Prenatal Reformer Pilates",
                "palette": "pink",
            },
            {
                "name": "Personal",
                "palette": "purple",
            },
        ]

    def generate_users(self, count):
        """Generate realistic pilates studio clients"""
        users_data = []

        # Age distribution realistic for pilates studios
        age_weights = {
            (25, 35): 0.25,  # Young professionals
            (35, 45): 0.30,  # Peak demographic
            (45, 55): 0.25,  # Mature clients
            (55, 70): 0.20,  # Active seniors
        }

        # Gender distribution (pilates tends to skew female)
        gender_distribution = ["F"] * 70 + ["M"] * 25 + ["NB"] * 5

        for i in range(count):
            # Select age range
            age_range = random.choices(list(age_weights.keys()), weights=list(age_weights.values()))[0]
            age = random.randint(*age_range)

            gender = random.choice(gender_distribution)
            first_name = (
                self.fake.first_name_female()
                if gender == "F"
                else (self.fake.first_name_male() if gender == "M" else self.fake.first_name())
            )

            birth_date = self.fake.date_of_birth(minimum_age=age, maximum_age=age)

            # Focus primarily on Greek users for Athens location
            country = random.choices(["GR", "US", "GB", "DE"], weights=[0.7, 0.15, 0.1, 0.05])[0]

            # Generate realistic phone number for the country
            if country == "GR":
                # Greek mobile format
                prefix = random.choice([694, 695, 697, 698, 699])  # Greek mobile prefixes
                number = random.randint(1000000, 9999999)
                phone = f"+30{prefix}{number}"
            elif country in ["US", "CA"]:
                # North American format
                area_code = random.randint(200, 999)
                exchange = random.randint(200, 999)
                number = random.randint(1000, 9999)
                phone = f"+1{area_code}{exchange}{number}"
            elif country == "GB":
                # UK mobile format
                prefix = random.choice([7400, 7500, 7600, 7700, 7800, 7900])
                number = random.randint(100000, 999999)
                phone = f"+44{prefix}{number}"
            elif country == "DE":
                # German mobile format
                prefix = random.choice([151, 152, 157, 159, 170, 171, 172, 173, 174, 175])
                number = random.randint(1000000, 9999999)
                phone = f"+49{prefix}{number}"
            else:
                # Fallback to Greek format
                prefix = random.choice([694, 695, 697, 698, 699])
                number = random.randint(1000000, 9999999)
                phone = f"+30{prefix}{number}"

            users_data.append(
                {
                    "first_name": first_name,
                    "last_name": self.fake.last_name(),
                    "email": f"{first_name.lower()}.{self.fake.last_name().lower()}{i}@{self.fake.domain_name()}",
                    "username": f"{first_name.lower()}{self.fake.last_name().lower()}{i}",
                    "birth_date": birth_date,
                    "gender": gender,
                    "country": country,
                    "phone": phone,
                }
            )

        return users_data

    def generate_studio_locations(self):
        """Generate single pilates studio location in Athens, Greece"""
        # Athens, Greece location data
        athens_data = {
            "city": "Athens",
            "state": "Attica",
            "country": "GR",
            "timezone": "Europe/Athens",
            "lat": 37.9838,
            "lon": 23.7275,
        }

        # Generate Greek phone number
        area_code = random.choice([210, 211])
        number = random.randint(1000000, 9999999)
        phone = f"+30{area_code}{number}"

        return [
            {
                "name": "Pilates Studio",
                "description": (
                    "A premier Pilates studio offering transformative movement experiences"
                    " in the heart of Athens. Our expert instructors guide you through"
                    " mindful, precise movements that build strength, flexibility, and body awareness."
                ),
                "street_address_1": f"{self.fake.building_number()} {self.fake.street_name()}",
                "street_address_2": f"Suite {random.randint(100, 999)}" if random.random() < 0.3 else "",
                "city": athens_data["city"],
                "state": athens_data["state"],
                "country": athens_data["country"],
                "postal_code": self.fake.postcode(),
                "timezone": athens_data["timezone"],
                "lat": athens_data["lat"] + random.uniform(-0.1, 0.1),
                "lon": athens_data["lon"] + random.uniform(-0.1, 0.1),
                "phone": phone,
                "email": "info@pilatesstudio.com",
                "website": "https://www.pilatesstudio.com",
            }
        ]

    def generate_studio_spaces(self, locations):
        """Generate simple studio spaces - Room A and Room B for each location"""
        spaces_data = []
        for location in locations:
            spaces_data.extend(
                [
                    {
                        "location": location,
                        "name": "Room A",
                        "description": "Main studio room for pilates classes",
                        "capacity": 12,
                    },
                    {
                        "location": location,
                        "name": "Room B",
                        "description": "Secondary studio room for pilates classes",
                        "capacity": 8,
                    },
                ]
            )
        return spaces_data

    def generate_subscription_types(self):
        """Generate pilates subscription packages"""
        return [
            {
                "name": "4 Classes",
                "description": (
                    "Participation in small group classes up to 4 people."
                    " Online reservation management platform. Duration 1 month"
                ),
                "price": Decimal("55.00"),
                "duration": 30,
                "credits": 4,
                "unpaid_reservation_limit": 1,
                "type": "group",
            },
            {
                "name": "8 Classes",
                "description": (
                    "Participation in small group classes up to 4 people."
                    " Online reservation management platform. Duration 1 month"
                ),
                "price": Decimal("99.00"),
                "duration": 30,
                "credits": 8,
                "unpaid_reservation_limit": 1,
                "type": "group",
            },
            {
                "name": "12 Classes",
                "description": (
                    "Participation in small group classes up to 4 people."
                    " Online reservation management platform. Duration 1 month."
                ),
                "price": Decimal("130.00"),
                "duration": 30,
                "credits": 12,
                "unpaid_reservation_limit": 1,
                "type": "group",
            },
            {
                "name": "20 Classes",
                "description": (
                    "Participation in small group classes up to 4 people."
                    " Online reservation management platform. Duration 3 months"
                ),
                "price": Decimal("240.00"),
                "duration": 90,
                "credits": 20,
                "unpaid_reservation_limit": 1,
                "type": "group",
            },
            {
                "name": "Drop In",
                "description": "Single class participation in small group class up to 4 people. No time limit",
                "price": Decimal("15.00"),
                "duration": None,
                "credits": 1,
                "unpaid_reservation_limit": 1,
                "type": "group",
            },
            {
                "name": "Personal - Drop In",
                "description": "Single personal training session with dedicated instructor. No time limit",
                "price": Decimal("30.00"),
                "duration": None,
                "credits": 1,
                "unpaid_reservation_limit": 1,
                "type": "personal",
            },
            {
                "name": "Personal - 10 Classes",
                "description": "10 personal training sessions with dedicated instructor. Duration 2 months",
                "price": Decimal("250.00"),
                "duration": 60,
                "credits": 10,
                "unpaid_reservation_limit": 1,
                "type": "personal",
            },
        ]


class Command(BaseCommand):
    help = "Generate comprehensive sample data for a pilates studio reservation system"

    def add_arguments(self, parser):
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
            default=100,
            help="Percentage of users with subscriptions (default: 100)",
        )
        parser.add_argument(
            "--reservation-percentage",
            type=int,
            default=100,
            help="Percentage of future events with reservations (default: 100)",
        )
        parser.add_argument(
            "--locale",
            type=str,
            default="en_US",
            help="Faker locale for generating data (default: en_US)",
        )
        parser.add_argument(
            "--clear-data",
            action="store_true",
            help="Clear existing data before generating new data",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible data (default: 42)",
        )

    def handle(self, *args, **options):
        # Set random seed for reproducible results
        random.seed(options["seed"])

        generator = PilatesStudioDataGenerator(options["locale"])

        self.stdout.write(self.style.SUCCESS(f"🧘‍♀️ Generating pilates studio data with {options['users']} users..."))

        if options["clear_data"]:
            self._clear_existing_data()

        # Generate base data
        genders = self._create_genders()
        users_data = generator.generate_users(options["users"])
        locations_data = generator.generate_studio_locations()

        # Create database objects
        booking_groups = self._create_booking_groups()
        self.stdout.write(f"✅ Created {len(booking_groups)} booking groups")

        users = self._create_users(users_data, genders)
        self.stdout.write(f"✅ Created {len(users)} realistic pilates clients")

        staff = self._create_staff(users, options["staff_percentage"])
        self.stdout.write(f"✅ Created {len(staff)} qualified instructors")

        locations = self._create_locations(locations_data)
        self.stdout.write(f"✅ Created {len(locations)} beautiful studio location")

        spaces_data = generator.generate_studio_spaces(locations)
        spaces = self._create_spaces(spaces_data)
        self.stdout.write(f"✅ Created {len(spaces)} diverse studio spaces")

        services = self._create_services(generator.pilates_services)
        self.stdout.write(f"✅ Created {len(services)} pilates class offerings")

        # Get all non-template events for reservation creation
        events = Event.objects.filter(is_recurrence_template=False).order_by("start_datetime")

        # Create subscription system
        subscription_packages = generator.generate_subscription_types()
        subscription_types = self._create_subscription_types(subscription_packages, locations[0])
        self.stdout.write(f"✅ Created {len(subscription_types)} membership packages")

        subscriptions = self._create_subscriptions(users, subscription_types, options["subscription_percentage"])
        self.stdout.write(f"✅ Created {len(subscriptions)} active memberships")

        # Create realistic reservations
        reservations = self._create_reservations(users, events, subscriptions, options["reservation_percentage"])
        self.stdout.write(f"✅ Created {len(reservations)} class reservations")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🎉 Successfully populated pilates studio with comprehensive sample data!\n"
                f"📊 Summary: {len(users)} users, {len(locations)} locations, {len(spaces)} spaces, "
                f"{len(services)} services, {len(events)} events, {len(subscriptions)} subscriptions, "
                f"{len(reservations)} reservations"
            )
        )

    def _clear_existing_data(self):
        """Clear existing data while preserving superusers"""
        self.stdout.write("🧹 Clearing existing data (preserving superusers)...")

        Reservation.objects.all().delete()
        SubscriptionCreditBalance.objects.all().delete()
        Subscription.objects.all().delete()
        SubscriptionTypeCreditAllocation.objects.all().delete()
        SubscriptionType.objects.all().delete()
        Event.objects.all().delete()
        Service.objects.all().delete()
        Space.objects.all().delete()
        Location.objects.all().delete()
        Staff.objects.all().delete()
        BookingGroup.objects.all().delete()
        EmailAddress.objects.filter(user__is_superuser=False).delete()
        User.objects.filter(is_superuser=False).delete()
        Gender.objects.all().delete()

    def _create_genders(self):
        """Create or get existing gender options"""
        genders_data = [
            {"name": "Female", "symbol": "F"},
            {"name": "Male", "symbol": "M"},
            {"name": "Non-Binary", "symbol": "NB"},
        ]
        genders = []
        for data in genders_data:
            gender, created = Gender.objects.get_or_create(**data)
            genders.append(gender)
        return genders

    def _create_booking_groups(self):
        """Create or get skill-level booking groups."""
        groups_data = [
            {
                "name": "Beginner",
                "slug": "beginner",
                "description": "Open to new members and those just starting their Pilates journey.",
            },
            {
                "name": "Intermediate",
                "slug": "intermediate",
                "description": "For members who have completed a foundation programme and are building on core skills.",
            },
            {
                "name": "Advanced",
                "slug": "advanced",
                "description": "Reserved for experienced members with strong technique and instructor approval.",
            },
        ]
        groups = []
        for data in groups_data:
            group, _ = BookingGroup.objects.get_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_active": True,
                },
            )
            groups.append(group)
        return groups

    def _create_users(self, users_data, genders):
        """Create user accounts"""
        users = []
        gender_map = {g.symbol: g for g in genders}

        for user_data in users_data:
            user = User.objects.create(
                email=user_data["email"],
                username=user_data["username"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                born_at=user_data["birth_date"],
                gender=gender_map[user_data["gender"]],
                country=Country(code=user_data["country"]),
                phone_number=PhoneNumber.from_string(user_data["phone"]),
                is_active=True,
            )
            user.set_password("pilates123")
            user.save()

            EmailAddress.objects.create(
                user=user,
                email=user.email,
                verified=True,
                primary=True,
            )
            users.append(user)

        return users

    def _create_staff(self, users, staff_percentage):
        """Create staff profiles"""
        staff_count = max(1, int(len(users) * staff_percentage / 100))
        staff_users = random.sample(users, staff_count)

        bio_templates = [
            "Certified Pilates instructor with {} years of experience specializing in {}.",
            "Former {} turned passionate Pilates teacher, bringing {} expertise to every class.",
            "Dedicated movement professional with background in {} and {} years teaching experience.",
            "Experienced instructor specializing in {} with certifications in {}.",
        ]

        specialties = [
            "rehabilitation and therapeutic movement",
            "athletic performance",
            "prenatal and postnatal care",
            "classical Pilates",
            "contemporary fusion",
            "injury prevention",
            "mind-body connection",
            "spinal alignment",
            "core stability",
            "flexibility and mobility",
        ]

        backgrounds = [
            "dance",
            "physiotherapy",
            "yoga",
            "fitness training",
            "sports medicine",
            "kinesiology",
        ]
        certifications = [
            "BASI",
            "Romana's Pilates",
            "Peak Pilates",
            "Balanced Body",
            "Stott Pilates",
        ]

        staff = []
        for user in staff_users:
            experience_years = random.randint(2, 15)
            specialty = random.choice(specialties)
            background = random.choice(backgrounds)
            certification = random.choice(certifications)

            bio_template = random.choice(bio_templates)
            bio = bio_template.format(experience_years, specialty, background, certification)

            staff_obj = Staff.objects.create(user=user, bio=bio)
            staff.append(staff_obj)

        return staff

    def _create_locations(self, locations_data):
        """Create or get existing studio locations"""
        locations = []
        for data in locations_data:
            location, created = Location.objects.get_or_create(
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "street_address_line1": data["street_address_1"],
                    "street_address_line2": data["street_address_2"],
                    "city": data["city"],
                    "state_province": data["state"],
                    "country": Country(code=data["country"]),
                    "postal_code": data["postal_code"],
                    "timezone": data["timezone"],
                    "latitude": data["lat"],
                    "longitude": data["lon"],
                    "phone_number": PhoneNumber.from_string(data["phone"]),
                    "email": data["email"],
                    "website": data["website"],
                    "is_active": True,
                },
            )
            locations.append(location)

        return locations

    def _create_spaces(self, spaces_data):
        """Create or get existing studio spaces"""
        spaces = []
        for data in spaces_data:
            space, created = Space.objects.get_or_create(
                location=data["location"],
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "capacity": data["capacity"],
                    "is_active": True,
                },
            )
            spaces.append(space)
        return spaces

    def _get_or_create_services(self):
        """Get or create all required services"""
        services_config = {
            "Reformer Pilates": (
                "Professional Reformer Pilates instruction focusing on precision, control, and mindful movement."
            ),
            "Reformer Athletic Flow": "Athletic flow reformer class for building strength and endurance.",
            "Reformer Recovery Flow": "Recovery-focused reformer class for gentle movement and restoration.",
            "Prenatal Reformer Pilates": "Prenatal-safe reformer class designed for expecting mothers.",
            "Personal": "One-on-one personal training session with dedicated instructor.",
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

    def _create_services(self, services_data):
        """Create pilates services with palette configuration"""
        services = []

        for data in services_data:
            # Look up palette if specified
            palette = None
            if "palette" in data:
                palette = Palette.objects.filter(title=data["palette"]).first()
                if not palette:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Palette '{data['palette']}' not found for service '{data['name']}'. "
                            f"Ensure the palette exists in the Design section of the admin."
                        )
                    )

            _goals = ["build strength", "improve flexibility", "enhance body awareness", "develop core stability"]
            service, created = Service.objects.get_or_create(
                name=data["name"],
                defaults={
                    "description": (
                        f"Professional {data['name']} instruction focusing on"
                        f" precision, control, and mindful movement."
                        f" Suitable for practitioners looking to {random.choice(_goals)}."
                    ),
                    "is_active": True,
                    "palette": palette,
                },
            )
            if not created and palette:
                # Update palette if service already exists
                service.palette = palette
                service.save(update_fields=["palette"])

            services.append(service)

        return services

    def _create_subscription_types(self, packages_data, location):
        """Create or get existing subscription packages with credit allocations"""
        subscription_types = []

        # Get or create all services
        services_dict = self._get_or_create_services()
        personal_service = services_dict.get("Personal")
        non_personal_services = [service for name, service in services_dict.items() if name != "Personal"]

        for data in packages_data:
            sub_type, created = SubscriptionType.objects.get_or_create(
                location=location,
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "price": data["price"],
                    "duration": data.get("duration"),
                    "credits": data.get("credits"),
                    "unpaid_reservation_limit": data.get("unpaid_reservation_limit", 1),
                    "is_active": True,
                },
            )

            # Create credit allocations if this is a new subscription type
            if created:
                # Create credit allocations based on subscription type
                if data.get("type") == "personal":
                    # Personal subscriptions: only allow Personal service with per-service credits
                    if personal_service:
                        SubscriptionTypeCreditAllocation.objects.create(
                            subscription_type=sub_type,
                            service=personal_service,
                            credits=0,
                        )
                else:
                    # Group subscriptions: whitelist non-personal services with 0 credits (use shared pool)
                    for service in non_personal_services:
                        SubscriptionTypeCreditAllocation.objects.create(
                            subscription_type=sub_type,
                            service=service,
                            credits=0,  # 0 means use shared credits pool
                        )

            subscription_types.append(sub_type)

        return subscription_types

    def _create_subscriptions(self, users, subscription_types, subscription_percentage):
        """Create user subscriptions"""
        subscription_count = int(len(users) * subscription_percentage / 100)
        subscribed_users = random.sample(users, subscription_count)

        subscriptions = []
        for user in subscribed_users:
            # Bias towards more popular packages
            weights = [
                15,  # 4 Classes
                25,  # 8 Classes
                35,  # 12 Classes (Popular)
                20,  # 20 Classes
                3,  # Drop In
                1,  # Personal - Drop In
                1,  # Personal - 4 Classes
            ]
            sub_type = random.choices(subscription_types, weights=weights[: len(subscription_types)])[0]

            # Random start date within last 3 months
            start_date = timezone.now().date() - timedelta(days=random.randint(0, 90))

            # Use SubscriptionService to properly create subscription with business logic
            subscription = SubscriptionService().admin.create(
                user=user,
                subscription_type=sub_type,
                start_date=start_date,
            )
            subscriptions.append(subscription)

        return subscriptions

    def _create_reservations(self, users, events, subscriptions, reservation_percentage):
        """Create realistic reservations"""
        future_events = [e for e in events if e.start_datetime.date() >= timezone.now().date()]
        target_reservations = int(len(future_events) * reservation_percentage / 100)

        reservations = []
        user_subscriptions = {sub.user_id: sub for sub in subscriptions}

        # Create reservations with realistic patterns
        for _ in range(target_reservations):
            event = random.choice(future_events)

            # Bias towards users with subscriptions for this service
            eligible_users = []
            for user in users:
                subscription = user_subscriptions.get(user.id)
                if subscription and subscription.can_access_service(event.service):
                    eligible_users.extend([user] * 3)  # 3x weight for subscription holders
                else:
                    eligible_users.append(user)

            user = random.choice(eligible_users)

            # Check if user already has reservation for this event
            existing = any(r for r in reservations if r["user"] == user and r["event"] == event)
            if existing:
                continue

            # Determine subscription usage
            subscription = user_subscriptions.get(user.id)
            if subscription and subscription.can_access_service(event.service):
                # Try to use credit
                if subscription.subscription_type.credit_allocations.exists():
                    if not subscription.use_credit(event.service):
                        continue  # Skip this reservation - credit exhausted
            else:
                # User doesn't have a valid subscription for this service
                continue

            # Realistic status distribution
            status_weights = {
                "CONFIRMED": 0.85,
                "WAITLISTED": 0.10,
                "CANCELLED": 0.05,
            }
            status = random.choices(list(status_weights.keys()), weights=list(status_weights.values()))[0]

            reservation_data = {
                "user": user,
                "event": event,
                "subscription": subscription,
                "status": status,
                "notes": f"Booked for {event.service.name}" if random.random() < 0.2 else "",
            }

            Reservation.objects.create(**reservation_data)
            reservations.append(reservation_data)

        return reservations
