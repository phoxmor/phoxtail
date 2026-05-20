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

    phoxtail studio load                         # reads from .phoxtail/studio-dump/
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
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console

from phoxtail.cli.studio import client
from phoxtail.cli.utils.config import find_config_file


def _default_dump_path() -> Path:
    config = find_config_file()
    root = config.parent if config else Path.cwd()
    return root / ".phoxtail" / "studio-dump"


console = Console()


class LoadScope(StrEnum):
    all = "all"
    collections = "collections"
    blocks = "blocks"
    variants = "variants"


def load(
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            help="Path to the dump directory or zip file. Defaults to .phoxtail/studio-dump/ in the project root.",
            show_default=False,
        ),
    ] = None,
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
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Overwrite existing entities instead of skipping them.",
        ),
    ] = False,
) -> None:
    """Load collections, blocks, and variants from a file archive into a project."""

    if peer:
        client.set_peer(peer)

    # Unzip to a temp dir if a zip was supplied; clean up afterwards.
    tmp_dir: Path | None = None
    data_root = (path or _default_dump_path()).resolve()

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
            _load_collections(data_root, force=force)

        if only in (LoadScope.all, LoadScope.blocks):
            _load_blocks(data_root, force=force)

        if only in (LoadScope.all, LoadScope.variants):
            _load_variants(data_root, force=force)
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


def _load_collections(root: Path, *, force: bool = False) -> None:
    console.print("[dim]Loading collections…[/dim]")
    collections_dir = root / "collections"
    if not collections_dir.exists():
        console.print("[yellow]  No collections/ directory found, skipping.[/yellow]")
        return

    id_by_identifier: dict[str, int] = {}
    if force:
        data = client.list_collections()
        id_by_identifier = {c["identifier"]: c["id"] for c in data.get("collections", [])}

    created = updated = skipped = 0
    for md_file in sorted(collections_dir.glob("*.md")):
        metadata, body = _parse_frontmatter(md_file.read_text(encoding="utf-8"))
        name = metadata.get("name")
        if not name:
            console.print(f"[yellow]  Skipping {md_file.name}: missing 'name' in frontmatter[/yellow]")
            continue

        identifier = metadata.get("identifier", md_file.stem)
        _, status = client.create_collection(
            identifier=identifier,
            name=name,
            description=metadata.get("description", ""),
            template=body,
        )
        if status == 409:
            if force:
                coll_id = id_by_identifier.get(identifier)
                if coll_id is None:
                    console.print(f"[yellow]  {identifier}: exists but ID not found, skipping[/yellow]")
                    skipped += 1
                else:
                    _, etag = client.get_collection_by_id(coll_id)
                    client.update_collection_by_id(
                        coll_id,
                        name=name,
                        description=metadata.get("description", ""),
                        template=body,
                        etag=etag or "*",
                    )
                    console.print(f"  [yellow]updated[/yellow] collection [cyan]{identifier}[/cyan]")
                    updated += 1
            else:
                console.print(f"  [dim]{identifier} already exists, skipping[/dim]")
                skipped += 1
        else:
            console.print(f"  [green]created[/green] collection [cyan]{identifier}[/cyan]")
            created += 1

    summary = f"  Collections: {created} created"
    if updated:
        summary += f", {updated} updated"
    summary += f", {skipped} skipped"
    console.print(summary)


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


def _load_blocks(root: Path, *, force: bool = False) -> None:
    console.print("[dim]Loading blocks…[/dim]")
    blocks_dir = root / "blocks"
    if not blocks_dir.exists():
        console.print("[yellow]  No blocks/ directory found, skipping.[/yellow]")
        return

    id_by_identifier: dict[str, int] = {}
    if force:
        data = client.list_blocks()
        id_by_identifier = {b["identifier"]: b["id"] for b in data.get("blocks", [])}

    created = updated = skipped = 0
    for block_dir in sorted(d for d in blocks_dir.iterdir() if d.is_dir()):
        metadata_file = block_dir / "block.yaml"
        schema_file = block_dir / "schema.json"

        if not metadata_file.exists():
            console.print(f"[yellow]  Skipping {block_dir.name}: missing block.yaml[/yellow]")
            continue
        if not schema_file.exists():
            console.print(f"[yellow]  Skipping {block_dir.name}: missing schema.json[/yellow]")
            continue

        try:
            metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            console.print(f"[yellow]  Skipping {block_dir.name}: invalid block.yaml — {exc}[/yellow]")
            continue

        try:
            schema = json.loads(schema_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            console.print(f"[yellow]  Skipping {block_dir.name}: invalid schema.json — {exc}[/yellow]")
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
            if force:
                block_id = id_by_identifier.get(identifier)
                if block_id is None:
                    console.print(f"[yellow]  {identifier}: exists but ID not found, skipping[/yellow]")
                    skipped += 1
                else:
                    _, etag = client.get_block_by_id(block_id)
                    client.update_block_by_id(
                        block_id,
                        name=metadata.get("name", identifier),
                        description=metadata.get("description", ""),
                        icon=metadata.get("icon", ""),
                        group=metadata.get("group", ""),
                        is_shared=metadata.get("is_shared", False),
                        page_types=metadata.get("page_types", []),
                        schema=schema,
                        sort_order=metadata.get("sort_order", 0),
                        etag=etag or "*",
                    )
                    console.print(f"  [yellow]updated[/yellow] block [cyan]{identifier}[/cyan]")
                    updated += 1
            else:
                console.print(f"  [dim]{identifier} already exists, skipping[/dim]")
                skipped += 1
        else:
            console.print(f"  [green]created[/green] block [cyan]{identifier}[/cyan]")
            created += 1

    summary = f"  Blocks: {created} created"
    if updated:
        summary += f", {updated} updated"
    summary += f", {skipped} skipped"
    console.print(summary)


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


def _load_variants(root: Path, *, force: bool = False) -> None:
    console.print("[dim]Loading variants…[/dim]")
    blocks_dir = root / "blocks"
    if not blocks_dir.exists():
        console.print("[yellow]  No blocks/ directory found, skipping.[/yellow]")
        return

    blocks_data = client.list_blocks()
    block_id_by_identifier = {b["identifier"]: b["id"] for b in blocks_data.get("blocks", [])}

    collections_data = client.list_collections()
    collection_id_by_identifier = {c["identifier"]: c["id"] for c in collections_data.get("collections", [])}

    # (block_identifier, collection_identifier, variant_identifier) → variant_id
    variant_id_by_key: dict[tuple[str, str, str], int] = {}
    if force:
        variants_data = client.list_variants()
        for v in variants_data.get("variants", []):
            key = (
                v["block"]["identifier"],
                v["collection"]["identifier"],
                v["identifier"],
            )
            variant_id_by_key[key] = v["id"]

    created = updated = skipped = 0
    for block_dir in sorted(d for d in blocks_dir.iterdir() if d.is_dir()):
        variants_dir = block_dir / "variants"
        if not variants_dir.exists():
            continue

        block_identifier = block_dir.name
        block_id = block_id_by_identifier.get(block_identifier)
        if block_id is None:
            console.print(f"[yellow]  Skipping block {block_identifier}: not found on server[/yellow]")
            continue

        for collection_dir in sorted(d for d in variants_dir.iterdir() if d.is_dir()):
            collection_identifier = collection_dir.name
            collection_id = collection_id_by_identifier.get(collection_identifier)
            if collection_id is None:
                console.print(f"[yellow]  Skipping collection {collection_identifier}: not found on server[/yellow]")
                continue

            for variant_dir in sorted(d for d in collection_dir.iterdir() if d.is_dir()):
                metadata_file = variant_dir / "variant.yaml"
                description_file = variant_dir / "description.md"
                html_file = variant_dir / "template.html"

                if not metadata_file.exists():
                    console.print(f"[yellow]  Skipping {variant_dir.name}: missing variant.yaml[/yellow]")
                    continue
                if not description_file.exists():
                    console.print(f"[yellow]  Skipping {variant_dir.name}: missing description.md[/yellow]")
                    continue
                if not html_file.exists():
                    console.print(f"[yellow]  Skipping {variant_dir.name}: missing template.html[/yellow]")
                    continue

                try:
                    metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
                except yaml.YAMLError as exc:
                    console.print(f"[yellow]  Skipping {variant_dir.name}: invalid variant.yaml — {exc}[/yellow]")
                    continue

                css_file = variant_dir / "styles.css"
                js_file = variant_dir / "script.js"
                identifier = metadata.get("identifier", variant_dir.name)

                name = metadata.get("name", variant_dir.name)
                description = description_file.read_text(encoding="utf-8")
                html = html_file.read_text(encoding="utf-8")
                css = css_file.read_text(encoding="utf-8") if css_file.exists() else ""
                javascript = js_file.read_text(encoding="utf-8") if js_file.exists() else ""
                is_default = metadata.get("is_default", False)

                _, status = client.create_variant(
                    identifier=identifier,
                    name=name,
                    block_id=block_id,
                    collection_id=collection_id,
                    description=description,
                    html=html,
                    css=css,
                    javascript=javascript,
                    is_default=is_default,
                )
                if status == 409:
                    if force:
                        key = (block_identifier, collection_identifier, identifier)
                        variant_id = variant_id_by_key.get(key)
                        if variant_id is None:
                            console.print(
                                f"[yellow]  {block_identifier}/"
                                f"{collection_identifier}/{identifier}:"
                                " exists but ID not found, skipping[/yellow]"
                            )
                            skipped += 1
                        else:
                            _, etag = client.get_variant_by_id(variant_id)
                            client.update_variant_by_id(
                                variant_id,
                                name=name,
                                description=description,
                                html=html,
                                css=css,
                                javascript=javascript,
                                is_default=is_default,
                                etag=etag or "*",
                            )
                            console.print(
                                f"  [yellow]updated[/yellow] variant [cyan]"
                                f"{block_identifier}/{collection_identifier}"
                                f"/{identifier}[/cyan]"
                            )
                            updated += 1
                    else:
                        console.print(
                            f"  [dim]{block_identifier}/{collection_identifier}"
                            f"/{identifier} already exists, skipping[/dim]"
                        )
                        skipped += 1
                else:
                    console.print(
                        f"  [green]created[/green] variant"
                        f" [cyan]{block_identifier}/{collection_identifier}/{identifier}[/cyan]"
                    )
                    created += 1

    summary = f"  Variants: {created} created"
    if updated:
        summary += f", {updated} updated"
    summary += f", {skipped} skipped"
    console.print(summary)
