"""
Unified management command to populate all stream entities from data files.

Discovers ``management/data/`` directories across all installed Django
apps, so each phoxtail app (streams, blog, booking, ...) can ship its
own blocks, variants, and collections alongside its models.

Auto-discovers and imports:
- Collections from data/collections/*.md (YAML frontmatter only — name,
  identifier, description; the markdown body is ignored)
- Blocks from data/blocks/<block-identifier>/ (directory with block.yaml,
  schema.json)
- Variants from data/blocks/<block-identifier>/variants/<variant-identifier>/
  (flat — no collection subdirectory level)

Variants are imported with collection=None. A collection can be assigned
manually in the admin or via the studio API after import.

Usage:
    python manage.py populate_streams              # Import all entities
    python manage.py populate_streams --only=collections
    python manage.py populate_streams --only=blocks
    python manage.py populate_streams --only=variants
    python manage.py populate_streams --app=phoxtail_blog  # Single app only
    python manage.py populate_streams --verbose    # Per-entity detail
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from phoxtail.streams.models import (
    Block,
    BlockVariant,
    VariantCollection,
)

console = Console()

_ICONS = {
    "ok": "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
}


def _parse_description(text: str) -> str:
    """Strip a leading Markdown heading line from description.md content."""
    lines = text.splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


@dataclass
class _Counts:
    created: int = 0
    patched: int = 0  # blocks only: source_app backfilled on existing records
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _get_data_dirs(app_filter: str | None = None) -> list[tuple[str, Path]]:
    """Discover management/data/ directories from all installed apps.

    Returns ``(app_label, path)`` pairs.  The streams app's own directory is
    always listed first so its collections exist before other apps reference
    them in blocks or variants.

    If ``app_filter`` is given, only that app's directory is returned (useful
    when populating a single newly-installed app).
    """
    streams_app = apps.get_app_config("phoxtail_streams")
    streams_dir = Path(__file__).resolve().parent.parent / "data"
    dirs: list[tuple[str, Path]] = []
    if streams_dir.is_dir():
        dirs.append((streams_app.label, streams_dir))

    for app_config in apps.get_app_configs():
        data_dir = Path(app_config.path) / "management" / "data"
        if data_dir.is_dir() and data_dir != streams_dir:
            dirs.append((app_config.label, data_dir))

    if app_filter:
        dirs = [(label, path) for label, path in dirs if label == app_filter]

    return dirs


def _check_app_references(page_types_config: list, schema: list) -> list[str]:
    """
    Validate that all app_label references in page_types and schema fields
    resolve to installed Django apps.

    Returns a list of missing app labels (empty if all are valid).
    """
    missing = set()

    for app_model in page_types_config:
        try:
            app_label = app_model.rsplit(".", 1)[0]
            apps.get_app_config(app_label)
        except (LookupError, IndexError):
            missing.add(app_label)

    def _scan_schema(fields):
        for field_item in fields:
            value = field_item.get("value", {}) if isinstance(field_item, dict) else {}
            for key in ("page_type", "target_model"):
                ref = value.get(key)
                if ref and "." in ref:
                    app_label = ref.rsplit(".", 1)[0]
                    try:
                        apps.get_app_config(app_label)
                    except LookupError:
                        missing.add(app_label)

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


@dataclass
class _VariantItem:
    block_dir: Path
    block_identifier: str
    variant_dir: Path


def _print_summary(
    *,
    coll_counts: _Counts | None,
    block_counts: _Counts | None,
    variant_counts: _Counts | None,
    verbose: bool = False,
) -> None:
    table = Table(box=None, show_header=True, pad_edge=False, show_edge=False)
    table.add_column("", no_wrap=True, min_width=2)
    table.add_column("Type", style="bold", min_width=14)
    table.add_column("Created", justify="right", style="green")
    table.add_column("Patched", justify="right", style="cyan")
    table.add_column("Skipped", justify="right", style="yellow")

    rows: list[tuple[str, _Counts]] = []
    if coll_counts is not None:
        rows.append(("Collections", coll_counts))
    if block_counts is not None:
        rows.append(("Blocks", block_counts))
    if variant_counts is not None:
        rows.append(("Variants", variant_counts))

    all_warnings: list[str] = []
    for label, counts in rows:
        icon = _ICONS["warn"] if counts.warnings else _ICONS["ok"]
        table.add_row(
            icon,
            label,
            str(counts.created),
            str(counts.patched) if counts.patched else "[dim]—[/dim]",
            str(counts.skipped),
        )
        all_warnings.extend(counts.warnings)

    extra_lines: list[str] = []

    if verbose:
        for label, counts in rows:
            if counts.details:
                extra_lines.append(f"  [dim]{label}:[/dim]")
                for line in counts.details:
                    extra_lines.append(f"  [dim]  · {line}[/dim]")

        # Source-app breakdown (only in verbose mode)
        groups: dict[str, list[str]] = defaultdict(list)
        for block in Block.objects.order_by("source_app", "identifier"):
            groups[block.source_app or ""].append(block.identifier)

        if groups:
            extra_lines.append("  [dim]Blocks by source app:[/dim]")
            for app_label, identifiers in sorted(groups.items(), key=lambda x: (x[0] == "", x[0])):
                label_text = app_label if app_label else "(no source_app — manually created)"
                extra_lines.append(f"  [dim]  {label_text} ({len(identifiers)})[/dim]")
                for ident in identifiers:
                    extra_lines.append(f"  [dim]    · {ident}[/dim]")

    if all_warnings:
        extra_lines.append("  [bold yellow]Warnings[/bold yellow]")
        for w in all_warnings:
            extra_lines.append(f"  [yellow]⚠[/yellow]  {w}")

    renderables: list = [table]
    if extra_lines:
        renderables.append("\n" + "\n".join(extra_lines))

    console.print()
    console.print(
        Panel(
            Group(*renderables),
            title="[bold cyan]Populate Streams[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()


class Command(BaseCommand):
    help = "Populates all stream entities from data files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=["collections", "blocks", "variants", "all"],
            default="all",
            help="Import only specific entity type",
        )
        parser.add_argument(
            "--app",
            default=None,
            metavar="APP_LABEL",
            help="Restrict import to a single Django app label (e.g. phoxtail_blog)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show per-entity detail in the summary",
        )

    def handle(self, *args, **options):
        only = options["only"]
        app_filter: str | None = options["app"]
        verbose = options["verbose"]

        if app_filter and not _get_data_dirs(app_filter):
            console.print(
                f"[yellow]Warning:[/yellow] --app '{app_filter}' matched no data directories. "
                "Check the app label and that the package ships stream data files."
            )
            return

        coll_counts: _Counts | None = None
        block_counts: _Counts | None = None
        variant_counts: _Counts | None = None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            transient=True,
            console=console,
            disable=not console.is_terminal,
        ) as progress:
            if only in ("all", "collections"):
                coll_counts = self._import_collections(progress, app_filter=app_filter)

            if only in ("all", "blocks"):
                block_counts = self._import_blocks(progress, app_filter=app_filter)

            if only in ("all", "variants"):
                variant_counts = self._import_variants(progress, app_filter=app_filter)

        _print_summary(
            coll_counts=coll_counts,
            block_counts=block_counts,
            variant_counts=variant_counts,
            verbose=verbose,
        )

    def _import_collections(self, progress: Progress, *, app_filter: str | None = None) -> _Counts:
        counts = _Counts()

        md_files: list[Path] = []
        for _app_label, data_dir in _get_data_dirs(app_filter):
            collections_dir = data_dir / "collections"
            if collections_dir.exists():
                md_files.extend(collections_dir.glob("*.md"))

        task_id = progress.add_task("[dim]Collections[/dim]", total=len(md_files))

        for md_file in md_files:
            content = md_file.read_text()
            metadata, body = parse_frontmatter(content)

            name = metadata.get("name")
            if not name:
                counts.warnings.append(f"{md_file.name}: missing 'name' in frontmatter")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            identifier = metadata.get("identifier", md_file.stem)
            description = metadata.get("description", "")

            if VariantCollection.objects.filter(identifier=identifier).exists():
                counts.skipped += 1
                counts.details.append(f"skipped {identifier} — already exists")
                progress.advance(task_id)
                continue

            collection = VariantCollection.objects.create(
                name=name,
                identifier=identifier,
                description=description,
            )
            counts.created += 1
            counts.details.append(f"created {collection.name} ({identifier})")

            progress.advance(task_id)

        return counts

    def _import_blocks(self, progress: Progress, *, app_filter: str | None = None) -> _Counts:
        counts = _Counts()

        block_dirs: list[tuple[str, Path]] = []
        for app_label, data_dir in _get_data_dirs(app_filter):
            blocks_dir = data_dir / "blocks"
            if blocks_dir.exists():
                block_dirs.extend((app_label, d) for d in blocks_dir.iterdir() if d.is_dir())

        task_id = progress.add_task("[dim]Blocks[/dim]", total=len(block_dirs))

        for app_label, block_dir in block_dirs:
            metadata_file = block_dir / "block.yaml"
            if not metadata_file.exists():
                counts.warnings.append(f"{block_dir.name}: missing block.yaml")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            try:
                metadata = yaml.safe_load(metadata_file.read_text())
            except yaml.YAMLError as e:
                counts.warnings.append(f"{block_dir.name}: invalid block.yaml — {e}")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            identifier = metadata.get("identifier", block_dir.name)

            existing = Block.objects.filter(identifier=identifier).first()
            if existing is not None:
                if not existing.source_app:
                    existing.source_app = app_label
                    existing.save(update_fields=["source_app"])
                    counts.patched += 1
                    counts.details.append(f"stamped {identifier} source_app={app_label}")
                else:
                    counts.details.append(f"skipped {identifier} — already exists")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            schema_file = block_dir / "schema.json"
            if not schema_file.exists():
                counts.warnings.append(f"{block_dir.name}: missing schema.json")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            try:
                schema = json.loads(schema_file.read_text())
            except json.JSONDecodeError as e:
                counts.warnings.append(f"{block_dir.name}: invalid schema.json — {e}")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            page_types_config = metadata.get("page_types", [])
            missing_apps = _check_app_references(page_types_config, schema)
            if missing_apps:
                counts.warnings.append(f"{identifier}: references uninstalled app(s): {', '.join(missing_apps)}")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            block = Block.objects.create(
                name=metadata.get("name", identifier),
                identifier=identifier,
                description=metadata.get("description", ""),
                icon=metadata.get("icon", ""),
                group=metadata.get("group", ""),
                is_shared=metadata.get("is_shared", False),
                source_app=app_label,
                schema=schema,
            )

            if page_types_config:
                from django.contrib.contenttypes.models import ContentType

                for app_model in page_types_config:
                    try:
                        app_label_pt, model_name = app_model.rsplit(".", 1)
                        ct = ContentType.objects.get(app_label=app_label_pt, model=model_name.lower())
                        block.page_types.add(ct)
                    except (ValueError, ContentType.DoesNotExist) as e:
                        counts.warnings.append(f"{identifier}: could not add page_type '{app_model}' — {e}")

            counts.created += 1
            counts.details.append(f"created {block.name} ({identifier})")

            progress.advance(task_id)

        return counts

    def _import_variants(self, progress: Progress, *, app_filter: str | None = None) -> _Counts:
        counts = _Counts()

        block_dirs: list[Path] = []
        for _app_label, data_dir in _get_data_dirs(app_filter):
            blocks_dir = data_dir / "blocks"
            if blocks_dir.exists():
                block_dirs.extend(d for d in blocks_dir.iterdir() if d.is_dir())

        # Collect all variant work items upfront so total is known before we start.
        work_items: list[_VariantItem] = []
        for block_dir in block_dirs:
            variants_dir = block_dir / "variants"
            if not variants_dir.exists():
                continue
            for variant_dir in variants_dir.iterdir():
                if variant_dir.is_dir():
                    work_items.append(
                        _VariantItem(
                            block_dir=block_dir,
                            block_identifier=block_dir.name,
                            variant_dir=variant_dir,
                        )
                    )

        task_id = progress.add_task("[dim]Variants[/dim]", total=len(work_items))

        block_cache: dict[str, Block | None] = {}
        seen_missing_blocks: set[str] = set()

        for item in work_items:
            if item.block_identifier not in block_cache:
                block_cache[item.block_identifier] = Block.objects.filter(identifier=item.block_identifier).first()
            block = block_cache[item.block_identifier]
            if not block:
                if item.block_identifier not in seen_missing_blocks:
                    seen_missing_blocks.add(item.block_identifier)
                    counts.warnings.append(f"block {item.block_identifier}: not found, skipping its variants")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            variant_dir = item.variant_dir
            metadata_file = variant_dir / "variant.yaml"
            if not metadata_file.exists():
                counts.warnings.append(f"{variant_dir.name}: missing variant.yaml")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            try:
                metadata = yaml.safe_load(metadata_file.read_text())
            except yaml.YAMLError as e:
                counts.warnings.append(f"{variant_dir.name}: invalid variant.yaml — {e}")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            name = metadata.get("name", variant_dir.name)
            identifier = metadata.get("identifier", variant_dir.name)

            if BlockVariant.objects.filter(block=block, collection=None, identifier=identifier).exists():
                counts.skipped += 1
                counts.details.append(f"skipped {identifier} — already exists")
                progress.advance(task_id)
                continue

            description_file = variant_dir / "description.md"
            if not description_file.exists():
                counts.warnings.append(f"{variant_dir.name}: missing description.md")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            html_file = variant_dir / "template.html"
            if not html_file.exists():
                counts.warnings.append(f"{variant_dir.name}: missing template.html")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            css_file = variant_dir / "styles.css"
            js_file = variant_dir / "script.js"
            is_default = metadata.get("is_default", False)

            try:
                with transaction.atomic():
                    if is_default:
                        BlockVariant.objects.filter(block=block, is_default=True).update(is_default=False)
                    variant = BlockVariant.objects.create(
                        block=block,
                        collection=None,
                        name=name,
                        identifier=identifier,
                        description=_parse_description(description_file.read_text()),
                        is_default=is_default,
                        html=html_file.read_text(),
                        css=css_file.read_text() if css_file.exists() else "",
                        javascript=js_file.read_text() if js_file.exists() else "",
                    )
            except IntegrityError:
                counts.warnings.append(f"{identifier}: integrity error (likely concurrent run or stale default)")
                counts.skipped += 1
                progress.advance(task_id)
                continue

            counts.created += 1
            counts.details.append(f"created {variant.name} ({item.block_identifier})")

            progress.advance(task_id)

        return counts
