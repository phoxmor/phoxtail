"""Make BlockVariant.collection a nullable optional label FK.

- Removes VariantCollection.template (ad-hoc label model no longer
  serves as a design-system briefing document).
- Changes BlockVariant.collection to null=True, on_delete=SET_NULL so
  variants can exist without any collection affiliation.
- Adds a partial unique constraint covering null-collection variants
  (Postgres treats NULLs as distinct in standard unique constraints, so
  the existing (block, collection, identifier) constraint does not
  protect the null case).
- Data step: retires sentinel/package-bucket collections
  (general_unsorted, material_design_3, phoxtail_blog,
  phoxtail_templates, phoxtail_registry, phoxtail_booking) by nulling
  out their variants and deleting the collection rows.
"""

from django.db import migrations, models


_RETIRED_IDENTIFIERS = {
    "general_unsorted",
    "material_design_3",
    "phoxtail_blog",
    "phoxtail_templates",
    "phoxtail_registry",
    "phoxtail_booking",
}


def _retire_sentinel_collections(apps, schema_editor):
    from django.db.models import Count, Min

    VariantCollection = apps.get_model("phoxtail_streams", "VariantCollection")
    BlockVariant = apps.get_model("phoxtail_streams", "BlockVariant")

    to_retire = VariantCollection.objects.filter(identifier__in=_RETIRED_IDENTIFIERS)
    BlockVariant.objects.filter(collection__in=to_retire).update(collection=None)

    # If two retired collections shared the same (block, identifier), nulling
    # both produces duplicates that would violate the partial constraint below.
    # Keep the lowest-pk row and delete the rest.
    dupes = (
        BlockVariant.objects.filter(collection__isnull=True)
        .values("block_id", "identifier")
        .annotate(cnt=Count("id"), min_id=Min("id"))
        .filter(cnt__gt=1)
    )
    for dupe in dupes:
        BlockVariant.objects.filter(
            block_id=dupe["block_id"],
            identifier=dupe["identifier"],
            collection__isnull=True,
        ).exclude(id=dupe["min_id"]).delete()

    to_retire.delete()


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("phoxtail_streams", "0008_restore_streamsadminpermission"),
    ]

    operations = [
        # 1. Drop the template column from VariantCollection.
        migrations.RemoveField(
            model_name="variantcollection",
            name="template",
        ),
        # 2. Make BlockVariant.collection nullable with SET_NULL.
        migrations.AlterField(
            model_name="blockvariant",
            name="collection",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional design-system label for this variant (e.g. 'Material Design 3').",
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="variants",
                to="phoxtail_streams.variantcollection",
            ),
        ),
        # 3. Retire sentinel/package-bucket collections before constraining.
        #    Runs first so the partial constraint below is never violated by
        #    duplicate (block, identifier) pairs that collapse to NULL.
        migrations.RunPython(_retire_sentinel_collections, _noop),
        # 4. Add partial unique constraint for null-collection variants.
        migrations.AddConstraint(
            model_name="blockvariant",
            constraint=models.UniqueConstraint(
                condition=models.Q(collection=None),
                fields=["block", "identifier"],
                name="unique_variant_identifier_per_block_no_collection",
            ),
        ),
    ]
