"""``phoxtail studio dump`` — dump stream entities to a portable file archive.

Fetches all collections, blocks, and variants from the running project's
API and writes them to a directory tree that exactly mirrors the
``management/data/`` format consumed by ``populate_streams`` (and
``phoxtail studio load``).  The output can be zipped (``--zip``) for
easy transfer between projects.

Dumped layout::

    <output>/
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
                styles.css         (omitted when empty)
                script.js          (omitted when empty)

Usage::

    phoxtail studio dump                        # writes to .phoxtail/studio-dump/
    phoxtail studio dump --out ./my-dump
    phoxtail studio dump --zip                  # creates .phoxtail/studio-dump.zip
    phoxtail studio dump --zip --out ./data
    phoxtail studio dump --only=collections
    phoxtail studio dump --only=blocks
    phoxtail studio dump --only=variants
    phoxtail studio dump --peer https://other-project.example.com
"""

from __future__ import annotations

import json
import shutil
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

_YAML_OPTS: dict = dict(default_flow_style=False, allow_unicode=True, sort_keys=False, width=1000)


class DumpScope(StrEnum):
    all = "all"
    collections = "collections"
    blocks = "blocks"
    variants = "variants"


def dump(
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Output directory (or zip base name when --zip is set). Defaults to .phoxtail/studio-dump/.",
            show_default=False,
        ),
    ] = None,
    zip_output: Annotated[
        bool,
        typer.Option(
            "--zip",
            help="Bundle the dump directory into a zip archive and remove the directory.",
        ),
    ] = False,
    only: Annotated[
        DumpScope,
        typer.Option(
            "--only",
            help="Dump only a specific entity type.",
        ),
    ] = DumpScope.all,
    peer: Annotated[
        str | None,
        typer.Option(
            "--peer",
            help=(
                "Base URL of the Phoxtail project to dump from "
                "(e.g. https://other.example.com). "
                "Defaults to the local project API."
            ),
            show_default=False,
        ),
    ] = None,
) -> None:
    """Dump collections, blocks, and variants to a portable file archive."""

    if peer:
        client.set_peer(peer)

    out = (out or _default_dump_path()).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if only in (DumpScope.all, DumpScope.collections):
        _dump_collections(out)

    if only in (DumpScope.all, DumpScope.blocks):
        _dump_blocks(out)

    if only in (DumpScope.all, DumpScope.variants):
        _dump_variants(out)

    if zip_output:
        zip_path = out.with_suffix(".zip")
        _zip_directory(out, zip_path)
        shutil.rmtree(out)
        console.print(f"[green]Dumped[/green] archive [bold]{zip_path}[/bold]")
    else:
        console.print(f"[green]Dumped[/green] data to [bold]{out}[/bold]")


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def _dump_collections(root: Path) -> None:
    console.print("[dim]Dumping collections…[/dim]")
    response = client.list_collections()
    collections_dir = root / "collections"
    collections_dir.mkdir(parents=True, exist_ok=True)

    for summary in response.get("collections", []):
        detail, _ = client.get_collection_by_id(summary["id"])
        _write_collection(collections_dir, detail)
        console.print(f"  [cyan]{summary['identifier']}[/cyan]")


def _write_collection(collections_dir: Path, detail: dict) -> None:
    """Write a single collection as a .md file with YAML frontmatter."""
    frontmatter: dict = {"name": detail["name"], "identifier": detail["identifier"]}
    if detail.get("description"):
        frontmatter["description"] = detail["description"]

    fm_text = yaml.dump(frontmatter, **_YAML_OPTS).rstrip()
    body = detail.get("template", "").strip()

    content = f"---\n{fm_text}\n---\n\n{body}\n" if body else f"---\n{fm_text}\n---\n"
    (collections_dir / f"{detail['identifier']}.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


def _dump_blocks(root: Path) -> None:
    console.print("[dim]Dumping blocks…[/dim]")
    response = client.list_blocks()
    blocks_dir = root / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)

    for summary in response.get("blocks", []):
        detail, _ = client.get_block_by_id(summary["id"])
        _write_block(blocks_dir, detail)
        console.print(f"  [cyan]{summary['identifier']}[/cyan]")


def _write_block(blocks_dir: Path, detail: dict) -> None:
    """Write block.yaml and schema.json for a single block."""
    block_dir = blocks_dir / detail["identifier"]
    block_dir.mkdir(parents=True, exist_ok=True)

    metadata: dict = {"name": detail["name"], "identifier": detail["identifier"]}
    if detail.get("description"):
        metadata["description"] = detail["description"]
    if detail.get("icon"):
        metadata["icon"] = detail["icon"]
    if detail.get("group"):
        metadata["group"] = detail["group"]
    if detail.get("is_shared"):
        metadata["is_shared"] = detail["is_shared"]
    if detail.get("page_types"):
        metadata["page_types"] = detail["page_types"]
    sort_order = detail.get("sort_order", 0)
    if sort_order:
        metadata["sort_order"] = sort_order

    (block_dir / "block.yaml").write_text(yaml.dump(metadata, **_YAML_OPTS), encoding="utf-8")

    field_schema_raw = detail.get("field_schema", "[]")
    try:
        schema_obj = json.loads(field_schema_raw)
    except (json.JSONDecodeError, TypeError):
        schema_obj = []
    (block_dir / "schema.json").write_text(
        json.dumps(schema_obj, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


def _dump_variants(root: Path) -> None:
    console.print("[dim]Dumping variants…[/dim]")
    response = client.list_variants()
    blocks_dir = root / "blocks"

    for summary in response.get("variants", []):
        block_slug = summary["block"]["identifier"]
        collection_slug = summary["collection"]["identifier"]
        variant_slug = summary["identifier"]

        detail, _ = client.get_variant_by_id(summary["id"])
        variant_dir = blocks_dir / block_slug / "variants" / collection_slug / variant_slug
        variant_dir.mkdir(parents=True, exist_ok=True)
        _write_variant(variant_dir, detail)
        console.print(f"  [cyan]{block_slug}/{collection_slug}/{variant_slug}[/cyan]")


def _write_variant(variant_dir: Path, detail: dict) -> None:
    """Write all files for a single variant directory."""
    variant_meta: dict = {"name": detail["name"], "identifier": detail["identifier"]}
    if detail.get("is_default"):
        variant_meta["is_default"] = True

    (variant_dir / "variant.yaml").write_text(yaml.dump(variant_meta, **_YAML_OPTS), encoding="utf-8")
    (variant_dir / "description.md").write_text(detail.get("description", ""), encoding="utf-8")
    (variant_dir / "template.html").write_text(detail.get("html", ""), encoding="utf-8")

    css = detail.get("css", "")
    if css.strip():
        (variant_dir / "styles.css").write_text(css, encoding="utf-8")

    js = detail.get("javascript", "")
    if js.strip():
        (variant_dir / "script.js").write_text(js, encoding="utf-8")


# ---------------------------------------------------------------------------
# Zip helpers
# ---------------------------------------------------------------------------


def _zip_directory(source: Path, zip_path: Path) -> None:
    """Recursively pack *source* into *zip_path*."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in source.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(source.parent))
