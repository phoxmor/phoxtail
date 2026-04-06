"""
Unified management command to populate all stream entities from data files.

Discovers ``management/data/`` directories across all installed Django
apps, so each phoxtail app (streams, blog, booking, ...) can ship its
own blocks, variants, prompts, and collections alongside its models.

Auto-discovers and imports:
- Collections from data/collections/*.md (YAML frontmatter + markdown body)
- Blocks from data/blocks/<block-identifier>/ (directory with block.yaml, schema.json)
- Variants from data/blocks/<block-identifier>/variants/
  <collection-identifier>/<variant-identifier>/

The variant folder structure mirrors the database constraint
(block, collection, identifier), ensuring each variant is
uniquely identified by its position in the hierarchy.

Usage:
    python manage.py populate_streams              # Import all entities
    python manage.py populate_streams --only=collections
    python manage.py populate_streams --only=blocks
    python manage.py populate_streams --only=variants
"""

import json
from pathlib import Path

import yaml
from django.apps import apps
from django.core.management.base import BaseCommand

from phoxtail.streams.models import (
    Block,
    BlockVariant,
    VariantCollection,
)


def _get_data_dirs() -> list[Path]:
    """Discover management/data/ directories from all installed apps.

    Any Django app that ships a ``management/data/`` directory is
    automatically included.  The streams app's own directory is
    always listed first so its prompts/collections exist before
    other apps try to reference them in their blocks or variants.
    """
    streams_dir = Path(__file__).resolve().parent.parent / "data"
    dirs: list[Path] = []
    if streams_dir.is_dir():
        dirs.append(streams_dir)

    for app_config in apps.get_app_configs():
        data_dir = Path(app_config.path) / "management" / "data"
        if data_dir.is_dir() and data_dir != streams_dir:
            dirs.append(data_dir)

    return dirs


def _check_app_references(page_types_config: list, schema: list) -> list[str]:
    """
    Validate that all app_label references in page_types and schema fields
    resolve to installed Django apps.

    Returns a list of missing app labels (empty if all are valid).
    """
    missing = set()

    # Check page_types (list of "app_label.model" strings)
    for app_model in page_types_config:
        try:
            app_label = app_model.rsplit(".", 1)[0]
            apps.get_app_config(app_label)
        except (LookupError, IndexError):
            missing.add(app_label)

    # Check schema for page_type / target_model references
    def _scan_schema(fields):
        for field in fields:
            value = field.get("value", {}) if isinstance(field, dict) else {}
            for key in ("page_type", "target_model"):
                ref = value.get(key)
                if ref and "." in ref:
                    app_label = ref.rsplit(".", 1)[0]
                    try:
                        apps.get_app_config(app_label)
                    except LookupError:
                        missing.add(app_label)

            # Recurse into nested blocks
            nested = value.get("blocks", [])
            if nested:
                _scan_schema(nested)

    _scan_schema(schema)
    return sorted(missing)


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """
    Parse YAML frontmatter from markdown content.

    Args:
        content: Raw markdown content with optional frontmatter

    Returns:
        Tuple of (metadata_dict, body_content)
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        metadata = {}

    body = parts[2].strip()
    return metadata, body


class Command(BaseCommand):
    help = "Populates all stream entities from data files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=["collections", "blocks", "variants", "all"],
            default="all",
            help="Import only specific entity type",
        )

    def handle(self, *args, **options):
        only = options["only"]

        if only in ("all", "collections"):
            self.import_collections()

        if only in ("all", "blocks"):
            self.import_blocks()

        if only in ("all", "variants"):
            self.import_variants()

        self.stdout.write(self.style.SUCCESS("Stream entities populated successfully!"))

    def import_collections(self):
        """Import collections from data/collections/*.md files."""
        self.stdout.write(self.style.SUCCESS("Importing collections..."))

        md_files = []
        for data_dir in _get_data_dirs():
            collections_dir = data_dir / "collections"
            if collections_dir.exists():
                md_files.extend(collections_dir.glob("*.md"))

        if not md_files:
            self.stdout.write(
                self.style.WARNING("No collection files found in any app")
            )
            return

        created_count = 0
        skipped_count = 0

        for md_file in md_files:
            content = md_file.read_text()
            metadata, body = parse_frontmatter(content)

            name = metadata.get("name")
            if not name:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {md_file.name}: missing 'name' in frontmatter"
                    )
                )
                continue

            identifier = metadata.get("identifier", md_file.stem)
            description = metadata.get("description", "")

            if VariantCollection.objects.filter(identifier=identifier).exists():
                self.stdout.write(
                    self.style.WARNING(f"  {identifier} already exists, skipping...")
                )
                skipped_count += 1
                continue

            collection = VariantCollection.objects.create(
                name=name,
                identifier=identifier,
                description=description,
                template=body,
            )
            self.stdout.write(
                self.style.SUCCESS(f"  Created collection: {collection.name}")
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Collections: {created_count} created, {skipped_count} skipped"
            )
        )

    def import_blocks(self):
        """Import blocks from data/blocks/<identifier>/ directories."""
        self.stdout.write(self.style.SUCCESS("Importing blocks..."))

        block_dirs = []
        for data_dir in _get_data_dirs():
            blocks_dir = data_dir / "blocks"
            if blocks_dir.exists():
                block_dirs.extend(d for d in blocks_dir.iterdir() if d.is_dir())

        if not block_dirs:
            self.stdout.write(
                self.style.WARNING("No block directories found in any app")
            )
            return

        created_count = 0
        skipped_count = 0

        for block_dir in block_dirs:
            # Load metadata from block.yaml
            metadata_file = block_dir / "block.yaml"
            if not metadata_file.exists():
                self.stdout.write(
                    self.style.WARNING(f"Skipping {block_dir.name}: missing block.yaml")
                )
                continue

            try:
                metadata = yaml.safe_load(metadata_file.read_text())
            except yaml.YAMLError as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {block_dir.name}: invalid block.yaml - {e}"
                    )
                )
                continue

            identifier = metadata.get("identifier", block_dir.name)

            if Block.objects.filter(identifier=identifier).exists():
                self.stdout.write(
                    self.style.WARNING(f"  {identifier} already exists, skipping...")
                )
                skipped_count += 1
                continue

            # Load schema from schema.json
            schema_file = block_dir / "schema.json"
            if not schema_file.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {block_dir.name}: missing schema.json"
                    )
                )
                continue

            try:
                schema = json.loads(schema_file.read_text())
            except json.JSONDecodeError as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {block_dir.name}: invalid schema.json - {e}"
                    )
                )
                continue

            # Validate that all app references are resolvable
            page_types_config = metadata.get("page_types", [])
            missing_apps = _check_app_references(page_types_config, schema)
            if missing_apps:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping {identifier}: references uninstalled "
                        f"app(s): {', '.join(missing_apps)}"
                    )
                )
                skipped_count += 1
                continue

            # Create the block
            block = Block.objects.create(
                name=metadata.get("name", identifier),
                identifier=identifier,
                description=metadata.get("description", ""),
                icon=metadata.get("icon", ""),
                group=metadata.get("group", ""),
                is_shared=metadata.get("is_shared", False),
                schema=schema,
            )

            # Set page_types (already validated above)
            if page_types_config:
                from django.contrib.contenttypes.models import ContentType

                for app_model in page_types_config:
                    try:
                        app_label, model_name = app_model.rsplit(".", 1)
                        ct = ContentType.objects.get(
                            app_label=app_label, model=model_name.lower()
                        )
                        block.page_types.add(ct)
                    except (ValueError, ContentType.DoesNotExist) as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  Could not add page_type '{app_model}': {e}"
                            )
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  Created block: {block.name} ({block.identifier})"
                )
            )
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Blocks: {created_count} created, {skipped_count} skipped"
            )
        )

    def import_variants(self):
        """
        Import variants from data/blocks/<block>/variants/
        <collection>/<variant>/ directories.

        Folder structure mirrors the database constraint
        (block, collection, identifier):
        - Block identifier: derived from block folder name
        - Collection identifier: derived from collection folder name
        - Variant identifier: derived from variant folder name or variant.yaml
        """
        self.stdout.write(self.style.SUCCESS("Importing variants..."))

        block_dirs = []
        for data_dir in _get_data_dirs():
            blocks_dir = data_dir / "blocks"
            if blocks_dir.exists():
                block_dirs.extend(d for d in blocks_dir.iterdir() if d.is_dir())

        if not block_dirs:
            self.stdout.write(
                self.style.WARNING("No block directories found in any app")
            )
            return

        created_count = 0
        skipped_count = 0

        for block_dir in block_dirs:
            variants_dir = block_dir / "variants"
            if not variants_dir.exists():
                continue

            # Get parent block
            block_identifier = block_dir.name
            block = Block.objects.filter(identifier=block_identifier).first()
            if not block:
                self.stdout.write(
                    self.style.WARNING(
                        f"Block {block_identifier} not found, skipping variants..."
                    )
                )
                continue

            # Iterate over collection folders within variants/
            for collection_dir in variants_dir.iterdir():
                if not collection_dir.is_dir():
                    continue

                # Get collection by identifier (folder name)
                collection_identifier = collection_dir.name
                collection = VariantCollection.objects.filter(
                    identifier=collection_identifier
                ).first()
                if not collection:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Collection '{collection_identifier}' not found, "
                            f"skipping variants in "
                            f"{block_identifier}/variants/{collection_identifier}/"
                        )
                    )
                    continue

                # Iterate over variant folders within the collection folder
                for variant_dir in collection_dir.iterdir():
                    if not variant_dir.is_dir():
                        continue

                    # Load variant.yaml
                    metadata_file = variant_dir / "variant.yaml"
                    if not metadata_file.exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping {variant_dir.name}: missing variant.yaml"
                            )
                        )
                        continue

                    try:
                        metadata = yaml.safe_load(metadata_file.read_text())
                    except yaml.YAMLError as e:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping {variant_dir.name}: "
                                f"invalid variant.yaml - {e}"
                            )
                        )
                        continue

                    name = metadata.get("name", variant_dir.name)
                    identifier = metadata.get("identifier", variant_dir.name)

                    # Check if variant already exists
                    if BlockVariant.objects.filter(
                        block=block, collection=collection, identifier=identifier
                    ).exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f"  {identifier} already exists, skipping..."
                            )
                        )
                        skipped_count += 1
                        continue

                    # Load required description.md
                    description_file = variant_dir / "description.md"
                    if not description_file.exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping {variant_dir.name}: missing description.md"
                            )
                        )
                        continue
                    description = description_file.read_text()

                    # Load required template.html
                    html_file = variant_dir / "template.html"
                    if not html_file.exists():
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skipping {variant_dir.name}: missing template.html"
                            )
                        )
                        continue
                    html = html_file.read_text()

                    # Load optional CSS
                    css_file = variant_dir / "styles.css"
                    css = css_file.read_text() if css_file.exists() else ""

                    # Load optional JavaScript
                    js_file = variant_dir / "script.js"
                    javascript = js_file.read_text() if js_file.exists() else ""

                    # Read is_default flag
                    is_default = metadata.get("is_default", False)

                    # Create the variant
                    variant = BlockVariant.objects.create(
                        block=block,
                        collection=collection,
                        name=name,
                        identifier=identifier,
                        description=description,
                        is_default=is_default,
                        html=html,
                        css=css,
                        javascript=javascript,
                    )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Created variant: {variant.name} "
                            f"({block.identifier}/{collection.identifier})"
                        )
                    )
                    created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Variants: {created_count} created, {skipped_count} skipped"
            )
        )
