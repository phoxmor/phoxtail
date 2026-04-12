"""``phoxtail studio load`` — load stream entities from a file archive into a project.

Reads the same directory layout produced by ``phoxtail studio dump`` (and
consumed by the ``populate_streams`` management command) and pushes each
entity to the target project's API.  Existing entities (409) are skipped
without error so the command is safe to run repeatedly.

Expected layout (directory or zip)::

    collections/
      <identifier>.md
    blocks/
      <identifier>/
        block.yaml
        schema.json
        variants/
          <collection>/
            <variant>/
              variant.yaml
              description.md
              template.html
              styles.css   (optional)
              script.js    (optional)

Usage::

    phoxtail studio load --path ./studio-dump
    phoxtail studio load --path ./studio-dump.zip
    phoxtail studio load --path ./studio-dump --only=collections
    phoxtail studio load --path ./studio-dump --peer https://other.example.com
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console

from phoxtail.cli.studio import client

console = Console()


class LoadScope(str, Enum):
    all = "all"
    collections = "collections"
    blocks = "blocks"
    variants = "variants"


def load(
    path: Annotated[
        Path,
        typer.Option(
            "--path",
            help="Path to the dump directory or zip file.",
            exists=True,
            show_default=False,
        ),
    ],
    only: Annotated[
        LoadScope,
        typer.Option(
            "--only",
            help="Load only a specific entity type.",
        ),
    ] = LoadScope.all,
    peer: Annotated[
        str | None,
        typer.Option(
            "--peer",
            help=(
                "Base URL of the Phoxtail project to load into "
                "(e.g. https://other.example.com). "
                "Defaults to the local project API."
            ),
            show_default=False,
        ),
    ] = None,
) -> None:
    """Load collections, blocks, and variants from a file archive into a project."""

    if peer:
        client.set_peer(peer)

    # Unzip to a temp dir if a zip was supplied; clean up afterwards.
    tmp_dir: Path | None = None
    data_root = path.resolve()

    if zipfile.is_zipfile(data_root):
        tmp_dir = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(data_root) as zf:
            zf.extractall(tmp_dir)
        # The zip was produced with paths relative to the *parent* of the
        # dump directory (e.g. studio-dump/collections/…), so look for
        # the single top-level subdirectory.
        subdirs = [d for d in tmp_dir.iterdir() if d.is_dir()]
        data_root = subdirs[0] if len(subdirs) == 1 else tmp_dir

    try:
        if only in (LoadScope.all, LoadScope.collections):
            _load_collections(data_root)

        if only in (LoadScope.all, LoadScope.blocks):
            _load_blocks(data_root)

        if only in (LoadScope.all, LoadScope.variants):
            _load_variants(data_root)
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    console.print("[green]Load complete.[/green]")


# ---------------------------------------------------------------------------
# Frontmatter helper (mirrors populate_streams.parse_frontmatter)
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        metadata = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, parts[2].strip()


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def _load_collections(root: Path) -> None:
    console.print("[dim]Loading collections…[/dim]")
    collections_dir = root / "collections"
    if not collections_dir.exists():
        console.print("[yellow]  No collections/ directory found, skipping.[/yellow]")
        return

    created = skipped = 0
    for md_file in sorted(collections_dir.glob("*.md")):
        metadata, body = _parse_frontmatter(md_file.read_text(encoding="utf-8"))
        name = metadata.get("name")
        if not name:
            console.print(
                f"[yellow]  Skipping {md_file.name}: missing 'name' in frontmatter[/yellow]"
            )
            continue

        identifier = metadata.get("identifier", md_file.stem)
        _, status = client.create_collection(
            identifier=identifier,
            name=name,
            description=metadata.get("description", ""),
            template=body,
        )
        if status == 409:
            console.print(f"  [dim]{identifier} already exists, skipping[/dim]")
            skipped += 1
        else:
            console.print(
                f"  [green]created[/green] collection [cyan]{identifier}[/cyan]"
            )
            created += 1

    console.print(f"  Collections: {created} created, {skipped} skipped")


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


def _load_blocks(root: Path) -> None:
    console.print("[dim]Loading blocks…[/dim]")
    blocks_dir = root / "blocks"
    if not blocks_dir.exists():
        console.print("[yellow]  No blocks/ directory found, skipping.[/yellow]")
        return

    created = skipped = 0
    for block_dir in sorted(d for d in blocks_dir.iterdir() if d.is_dir()):
        metadata_file = block_dir / "block.yaml"
        schema_file = block_dir / "schema.json"

        if not metadata_file.exists():
            console.print(
                f"[yellow]  Skipping {block_dir.name}: missing block.yaml[/yellow]"
            )
            continue
        if not schema_file.exists():
            console.print(
                f"[yellow]  Skipping {block_dir.name}: missing schema.json[/yellow]"
            )
            continue

        try:
            metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            console.print(
                f"[yellow]  Skipping {block_dir.name}: invalid block.yaml — {exc}[/yellow]"
            )
            continue

        try:
            schema = json.loads(schema_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            console.print(
                f"[yellow]  Skipping {block_dir.name}: invalid schema.json — {exc}[/yellow]"
            )
            continue

        identifier = metadata.get("identifier", block_dir.name)
        _, status = client.create_block(
            identifier=identifier,
            name=metadata.get("name", identifier),
            description=metadata.get("description", ""),
            icon=metadata.get("icon", ""),
            group=metadata.get("group", ""),
            is_shared=metadata.get("is_shared", False),
            page_types=metadata.get("page_types", []),
            schema=schema,
            sort_order=metadata.get("sort_order", 0),
        )
        if status == 409:
            console.print(f"  [dim]{identifier} already exists, skipping[/dim]")
            skipped += 1
        else:
            console.print(f"  [green]created[/green] block [cyan]{identifier}[/cyan]")
            created += 1

    console.print(f"  Blocks: {created} created, {skipped} skipped")


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


def _load_variants(root: Path) -> None:
    console.print("[dim]Loading variants…[/dim]")
    blocks_dir = root / "blocks"
    if not blocks_dir.exists():
        console.print("[yellow]  No blocks/ directory found, skipping.[/yellow]")
        return

    created = skipped = 0
    for block_dir in sorted(d for d in blocks_dir.iterdir() if d.is_dir()):
        variants_dir = block_dir / "variants"
        if not variants_dir.exists():
            continue

        block_identifier = block_dir.name

        for collection_dir in sorted(d for d in variants_dir.iterdir() if d.is_dir()):
            collection_identifier = collection_dir.name

            for variant_dir in sorted(
                d for d in collection_dir.iterdir() if d.is_dir()
            ):
                metadata_file = variant_dir / "variant.yaml"
                description_file = variant_dir / "description.md"
                html_file = variant_dir / "template.html"

                if not metadata_file.exists():
                    console.print(
                        f"[yellow]  Skipping {variant_dir.name}: missing variant.yaml[/yellow]"
                    )
                    continue
                if not description_file.exists():
                    console.print(
                        f"[yellow]  Skipping {variant_dir.name}: missing description.md[/yellow]"
                    )
                    continue
                if not html_file.exists():
                    console.print(
                        f"[yellow]  Skipping {variant_dir.name}: missing template.html[/yellow]"
                    )
                    continue

                try:
                    metadata = (
                        yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
                    )
                except yaml.YAMLError as exc:
                    console.print(
                        f"[yellow]  Skipping {variant_dir.name}: invalid variant.yaml — {exc}[/yellow]"
                    )
                    continue

                css_file = variant_dir / "styles.css"
                js_file = variant_dir / "script.js"
                identifier = metadata.get("identifier", variant_dir.name)

                _, status = client.create_variant(
                    identifier=identifier,
                    name=metadata.get("name", variant_dir.name),
                    block=block_identifier,
                    collection=collection_identifier,
                    description=description_file.read_text(encoding="utf-8"),
                    html=html_file.read_text(encoding="utf-8"),
                    css=css_file.read_text(encoding="utf-8")
                    if css_file.exists()
                    else "",
                    javascript=js_file.read_text(encoding="utf-8")
                    if js_file.exists()
                    else "",
                    is_default=metadata.get("is_default", False),
                )
                if status == 409:
                    console.print(
                        f"  [dim]{block_identifier}/{collection_identifier}/{identifier} already exists, skipping[/dim]"
                    )
                    skipped += 1
                else:
                    console.print(
                        f"  [green]created[/green] variant [cyan]{block_identifier}/{collection_identifier}/{identifier}[/cyan]"
                    )
                    created += 1

    console.print(f"  Variants: {created} created, {skipped} skipped")
