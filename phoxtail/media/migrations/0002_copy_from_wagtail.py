"""Data migration: copy all existing wagtail media rows into the phoxtail_media
tables while preserving PKs.

This must run before any AlterField migrations in cms/streams/blog retarget
their ForeignKeys from wagtailimages/wagtaildocs/wagtailmedia to this app.
Preserving PKs means all existing StreamField block JSON (which stores integer
IDs) continues to resolve correctly after the FK retarget.
"""

from django.db import migrations


def copy_forward(apps, schema_editor):
    Image = apps.get_model("wagtailimages", "Image")
    if not Image.objects.exists():
        return  # fresh install — nothing to bridge
    Rendition = apps.get_model("wagtailimages", "Rendition")
    Document = apps.get_model("wagtaildocs", "Document")
    Media = apps.get_model("wagtailmedia", "Media")

    PhoxtailImage = apps.get_model("phoxtail_media", "PhoxtailImage")
    PhoxtailRendition = apps.get_model("phoxtail_media", "PhoxtailRendition")
    PhoxtailDocument = apps.get_model("phoxtail_media", "PhoxtailDocument")
    PhoxtailMedia = apps.get_model("phoxtail_media", "PhoxtailMedia")

    PhoxtailImage.objects.bulk_create(
        [
            PhoxtailImage(
                id=img.id,
                title=img.title,
                file=img.file.name,
                description=img.description,
                width=img.width,
                height=img.height,
                created_at=img.created_at,
                uploaded_by_user_id=img.uploaded_by_user_id,
                focal_point_x=img.focal_point_x,
                focal_point_y=img.focal_point_y,
                focal_point_width=img.focal_point_width,
                focal_point_height=img.focal_point_height,
                file_size=img.file_size,
                file_hash=img.file_hash,
                collection_id=img.collection_id,
            )
            for img in Image.objects.all()
        ]
    )

    PhoxtailRendition.objects.bulk_create(
        [
            PhoxtailRendition(
                id=r.id,
                image_id=r.image_id,
                filter_spec=r.filter_spec,
                file=r.file.name,
                width=r.width,
                height=r.height,
                focal_point_key=r.focal_point_key,
            )
            for r in Rendition.objects.all()
        ]
    )

    PhoxtailDocument.objects.bulk_create(
        [
            PhoxtailDocument(
                id=doc.id,
                title=doc.title,
                file=doc.file.name,
                created_at=doc.created_at,
                file_size=doc.file_size,
                file_hash=doc.file_hash,
                collection_id=doc.collection_id,
                uploaded_by_user_id=doc.uploaded_by_user_id,
            )
            for doc in Document.objects.all()
        ]
    )

    PhoxtailMedia.objects.bulk_create(
        [
            PhoxtailMedia(
                id=m.id,
                title=m.title,
                file=m.file.name,
                type=m.type,
                duration=m.duration,
                width=m.width,
                height=m.height,
                thumbnail=m.thumbnail.name if m.thumbnail else "",
                created_at=m.created_at,
                uploaded_by_user_id=m.uploaded_by_user_id,
                collection_id=m.collection_id,
                description="",
            )
            for m in Media.objects.all()
        ]
    )

    # bulk_create with explicit PKs does not advance PostgreSQL sequences.
    # Reset each sequence to MAX(id) so subsequent inserts don't collide.
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


def copy_backward(apps, schema_editor):
    apps.get_model("phoxtail_media", "PhoxtailRendition").objects.all().delete()
    apps.get_model("phoxtail_media", "PhoxtailImage").objects.all().delete()
    apps.get_model("phoxtail_media", "PhoxtailDocument").objects.all().delete()
    apps.get_model("phoxtail_media", "PhoxtailMedia").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("phoxtail_media", "0001_initial"),
        ("wagtailimages", "0027_image_description"),
        ("wagtaildocs", "0014_alter_document_file_size"),
        ("wagtailmedia", "0005_alter_media_options"),
    ]

    operations = [
        migrations.RunPython(copy_forward, copy_backward),
    ]
