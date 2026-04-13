"""Bootstrap the site's homepage for a freshly hatched Phoxtail project.

Replaces Wagtail's default welcome page with a HomePage instance containing
the hatchling block, and wires the default Site to point at it.

This command is idempotent: if a non-welcome page already exists at depth 2
it exits cleanly without making changes.

Usage:
    python manage.py bootstrap_site --app-label myproject
    python manage.py bootstrap_site --app-label myproject --site-name "My Project"
"""

import json
import uuid

from django.apps import apps as django_apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = (
        "Replace Wagtail's welcome page with a project HomePage "
        "and wire the default Site."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--app-label",
            required=True,
            help="Django app label of the project (e.g. myproject)",
        )
        parser.add_argument(
            "--site-name",
            default=None,
            help="Human-readable site name (defaults to app label, titlecased)",
        )

    def handle(self, *args, **options):
        app_label = options["app_label"]
        site_name = options["site_name"] or app_label.replace("_", " ").title()

        try:
            HomePage = django_apps.get_model(app_label, "HomePage")
        except LookupError:
            raise CommandError(
                f"No model 'HomePage' found in app '{app_label}'. "
                "Ensure the app is in INSTALLED_APPS and migrations have been applied."
            )

        ContentType = django_apps.get_model("contenttypes.ContentType")
        Page = django_apps.get_model("wagtailcore.Page")
        Site = django_apps.get_model("wagtailcore.Site")
        Locale = django_apps.get_model("wagtailcore.Locale")
        BlockVariant = django_apps.get_model("phoxtail_streams.BlockVariant")

        # Idempotency check — if a non-welcome page exists at depth 2, bail out.
        existing = Page.objects.filter(depth=2).exclude(slug="home")
        if existing.exists():
            self.stdout.write(
                self.style.WARNING(
                    "A page already exists at depth 2 that is not the welcome page. "
                    "Skipping bootstrap_site."
                )
            )
            return

        # Find the default hatchling variant (populated by populate_streams).
        default_variant = BlockVariant.objects.filter(
            block__identifier="hatchling", is_default=True
        ).first()
        if default_variant is None:
            raise CommandError(
                "No default hatchling BlockVariant found. "
                "Run 'manage.py populate_streams' before bootstrap_site."
            )

        locale = Locale.objects.first()
        if locale is None:
            raise CommandError("No Locale found. Run migrations first.")

        root = Page.objects.get(depth=1)

        site = Site.objects.filter(is_default_site=True).first()
        # Point site at root temporarily so the welcome-page delete doesn't
        # leave the site pointing at a non-existent page.
        if site:
            Site.objects.filter(pk=site.pk).update(root_page=root)

        Page.objects.filter(depth=2, slug="home").delete()

        homepage_ct, _ = ContentType.objects.get_or_create(
            model="homepage", app_label=app_label
        )

        homepage = HomePage.objects.create(
            title="Home",
            slug="home",
            content_type=homepage_ct,
            path="00010001",
            depth=2,
            numchild=0,
            url_path="/home/",
            locale=locale,
            is_locked_for_references=False,
        )

        # Write body JSON via raw SQL — SchemaStreamField.get_prep_value()
        # may strip unknown block types if the dynamic block registry hasn't
        # been fully wired yet. body lives on phoxtail_cms_sitepage due to
        # multi-table inheritance.
        body = [
            {
                "type": "hatchling",
                "value": {"variant": default_variant.pk},
                "id": str(uuid.uuid4()),
            }
        ]
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE phoxtail_cms_sitepage SET body = %s WHERE page_ptr_id = %s",
                [json.dumps(body), homepage.pk],
            )

        root.numchild = Page.objects.filter(depth=2).count()
        root.save()

        if site:
            Site.objects.filter(pk=site.pk).update(
                root_page=homepage,
                site_name=site_name,
            )
        else:
            Site.objects.create(
                hostname="localhost",
                root_page=homepage,
                is_default_site=True,
                site_name=site_name,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Homepage created for '{app_label}' with hatchling block. "
                f"Site name set to '{site_name}'."
            )
        )
