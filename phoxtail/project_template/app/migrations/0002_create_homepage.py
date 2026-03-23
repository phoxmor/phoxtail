"""Replace Wagtail's default welcome page with a SitePage containing the hatchling block."""

import json
import uuid
from pathlib import Path

from django.db import migrations

# Locate the data directory via the installed phoxtail package.
# This works regardless of where the project or package is installed.
import phoxtail.streams.management as _streams_mgmt

DATA_DIR = Path(_streams_mgmt.__file__).resolve().parent / "data"


def _parse_simple_yaml(text):
    """Parse flat key: value YAML without requiring pyyaml.

    Handles the simple format used in block.yaml / variant.yaml:
    single-level key-value pairs, booleans, and unquoted strings.
    """
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False
        result[key.strip()] = value
    return result


def _parse_frontmatter(text):
    """Extract YAML frontmatter from a markdown file."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return _parse_simple_yaml(parts[1])


def _read_file(path):
    """Read a file if it exists, return empty string otherwise."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _read_block_data(block_id):
    """Read block.yaml, schema.json, and variant files from the data directory."""
    block_dir = DATA_DIR / "blocks" / block_id

    if not block_dir.is_dir():
        raise FileNotFoundError(
            f"Block data directory not found: {block_dir}\n"
            f"Ensure phoxtail is installed with stream block data."
        )

    metadata = _parse_simple_yaml((block_dir / "block.yaml").read_text(encoding="utf-8"))
    schema = json.loads((block_dir / "schema.json").read_text(encoding="utf-8"))

    variants = []
    variants_dir = block_dir / "variants"
    if variants_dir.is_dir():
        for collection_dir in sorted(variants_dir.iterdir()):
            if not collection_dir.is_dir():
                continue
            for variant_dir in sorted(collection_dir.iterdir()):
                if not variant_dir.is_dir():
                    continue

                v_yaml = variant_dir / "variant.yaml"
                if not v_yaml.exists():
                    continue

                variants.append(
                    {
                        "collection_id": collection_dir.name,
                        "metadata": _parse_simple_yaml(v_yaml.read_text(encoding="utf-8")),
                        "description": _read_file(variant_dir / "description.md"),
                        "html": _read_file(variant_dir / "template.html"),
                        "css": _read_file(variant_dir / "styles.css"),
                        "javascript": _read_file(variant_dir / "script.js"),
                    }
                )

    return metadata, schema, variants


def _read_collection_data(collection_id):
    """Read collection metadata from data/collections/<id>.md."""
    md_file = DATA_DIR / "collections" / f"{collection_id}.md"
    if not md_file.exists():
        return None
    return _parse_frontmatter(md_file.read_text(encoding="utf-8"))


def create_homepage(apps, schema_editor):
    ContentType = apps.get_model("contenttypes.ContentType")
    Page = apps.get_model("wagtailcore.Page")
    Site = apps.get_model("wagtailcore.Site")
    SitePage = apps.get_model("app.SitePage")
    Block = apps.get_model("phoxtail_streams.Block")
    VariantCollection = apps.get_model("phoxtail_streams.VariantCollection")
    BlockVariant = apps.get_model("phoxtail_streams.BlockVariant")

    # --- Load hatchling block from data files ---

    metadata, schema, variants = _read_block_data("hatchling")

    block, _ = Block.objects.get_or_create(
        identifier=metadata["identifier"],
        defaults={
            "name": metadata.get("name", "Hatchling"),
            "description": metadata.get("description", ""),
            "icon": metadata.get("icon", ""),
            "group": metadata.get("group", ""),
            "is_shared": metadata.get("is_shared", False),
            "schema": schema,
        },
    )

    default_variant = None
    for v in variants:
        # Resolve collection from data files or create a fallback
        col_meta = _read_collection_data(v["collection_id"])
        if col_meta:
            collection, _ = VariantCollection.objects.get_or_create(
                identifier=col_meta["identifier"],
                defaults={
                    "name": col_meta["name"],
                    "description": col_meta.get("description", ""),
                    "template": "",
                },
            )
        else:
            collection, _ = VariantCollection.objects.get_or_create(
                identifier=v["collection_id"],
                defaults={
                    "name": v["collection_id"].replace("_", " ").title(),
                    "description": "",
                    "template": "",
                },
            )

        v_meta = v["metadata"]
        identifier = v_meta.get("identifier", "")

        bv, _ = BlockVariant.objects.get_or_create(
            block=block,
            collection=collection,
            identifier=identifier,
            defaults={
                "name": v_meta.get("name", identifier),
                "description": v["description"],
                "is_default": v_meta.get("is_default", False),
                "html": v["html"],
                "css": v["css"],
                "javascript": v["javascript"],
            },
        )

        if bv.is_default:
            default_variant = bv

    # --- Replace Wagtail's default page with a SitePage ---

    Locale = apps.get_model("wagtailcore.Locale")
    locale = Locale.objects.first()

    sitepage_ct, _ = ContentType.objects.get_or_create(
        model="sitepage", app_label="app"
    )

    root = Page.objects.get(depth=1)

    # Temporarily repoint the site to the tree root so deleting
    # the old homepage doesn't cascade-delete the Site.
    site = Site.objects.filter(is_default_site=True).first()
    if site:
        Site.objects.filter(pk=site.pk).update(root_page=root)

    # Now safe to remove Wagtail's default page
    Page.objects.filter(depth=2, slug="home").delete()

    homepage = SitePage.objects.create(
        title="Home",
        slug="home",
        content_type=sitepage_ct,
        path="00010001",
        depth=2,
        numchild=0,
        url_path="/home/",
        locale=locale,
        is_locked_for_references=False,
    )

    # Write the body JSON via raw SQL — SchemaStreamField.get_prep_value()
    # strips unknown block types during migration because the dynamic block
    # registry isn't available yet.
    body = [
        {
            "type": "hatchling",
            "value": {"variant": default_variant.pk if default_variant else None},
            "id": str(uuid.uuid4()),
        }
    ]
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE app_sitepage SET body = %s WHERE page_ptr_id = %s",
            [json.dumps(body), homepage.pk],
        )

    root.numchild = Page.objects.filter(depth=2).count()
    root.save()

    # Point the site to our homepage and set the project name
    if site:
        Site.objects.filter(pk=site.pk).update(
            root_page=homepage,
            site_name="{{ phoxtail_project_name }}",
        )
    else:
        Site.objects.create(
            hostname="localhost",
            root_page=homepage,
            is_default_site=True,
            site_name="{{ phoxtail_project_name }}",
        )


def remove_homepage(apps, schema_editor):
    """Reverse migration is intentionally a no-op — matches Wagtail convention."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0001_initial"),
        ("phoxtail_streams", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_homepage, remove_homepage),
    ]
