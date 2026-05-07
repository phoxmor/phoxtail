"""Reset PostgreSQL sequences for phoxtail_media tables.

bulk_create with explicit PKs (0002_copy_from_wagtail) does not advance
sequences, so the first real insert after migration collides with an
already-copied row. This one-shot migration corrects the sequences.
"""

from django.db import migrations


def reset_sequences(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for table in [
            "phoxtail_media_phoxtailimage",
            "phoxtail_media_phoxtailrendition",
            "phoxtail_media_phoxtaildocument",
            "phoxtail_media_phoxtailmedia",
        ]:
            cursor.execute(
                f"SELECT CASE WHEN MAX(id) IS NOT NULL"
                f" THEN setval(pg_get_serial_sequence('{table}', 'id'), MAX(id))"
                f" ELSE 1 END FROM {table}"
            )


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_media", "0002_copy_from_wagtail"),
    ]

    operations = [
        migrations.RunPython(reset_sequences, migrations.RunPython.noop),
    ]
