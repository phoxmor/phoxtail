"""Data migration: create an 'Uncategorized' PaletteSet and assign all
existing Palette rows that have no set to it."""

from django.db import migrations


def assign_default_set(apps, schema_editor):
    PaletteSet = apps.get_model("phoxtail_design", "PaletteSet")
    Palette = apps.get_model("phoxtail_design", "Palette")

    default_set, _ = PaletteSet.objects.get_or_create(
        identifier="uncategorized",
        defaults={"name": "Uncategorized", "description": ""},
    )
    Palette.objects.filter(palette_set__isnull=True).update(palette_set=default_set)


def unassign_default_set(apps, schema_editor):
    PaletteSet = apps.get_model("phoxtail_design", "PaletteSet")
    Palette = apps.get_model("phoxtail_design", "Palette")

    try:
        default_set = PaletteSet.objects.get(identifier="uncategorized")
    except PaletteSet.DoesNotExist:
        return
    Palette.objects.filter(palette_set=default_set).update(palette_set=None)


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_design", "0002_palette_set"),
    ]

    operations = [
        migrations.RunPython(assign_default_set, reverse_code=unassign_default_set),
    ]
