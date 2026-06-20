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
          description.md
          schema.json
          variants/
            <variant>/
              variant.yaml
              description.md
              template.html
              styles.css
              script.js
              preview/                      (only with --with-previews)
                preview_image_desktop.<ext>
                preview_image_desktop_dark.<ext>
                preview_image_tablet.<ext>
                preview_image_tablet_dark.<ext>
                preview_image_mobile.<ext>
                preview_image_mobile_dark.<ext>

Usage::

    phoxtail studio dump                        # writes to .phoxtail/studio-dump/
    phoxtail studio dump --out ./my-dump
    phoxtail studio dump --zip                  # creates .phoxtail/studio-dump.zip
    phoxtail studio dump --zip --out ./data
    phoxtail studio dump --only=collections
    phoxtail studio dump --only=blocks
    phoxtail studio dump --only=variants
    phoxtail studio dump --with-previews        # also dump variant preview images
    phoxtail studio dump --peer https://other-project.example.com
    phoxtail studio dump --verbose              # show per-entity detail
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
import yaml
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from phoxtail.cli.studio import client
from phoxtail.cli.utils.config import find_config_file


def _default_dump_path() -> Path:
    config = find_config_file()
    root = config.parent if config else Path.cwd()
    return root / ".phoxtail" / "studio-dump"


console = Console()

_YAML_OPTS: dict = dict(default_flow_style=False, allow_unicode=True, sort_keys=False, width=1000)

_ICONS = {
    "ok": "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
}


class DumpScope(StrEnum):
    all = "all"
    collections = "collections"
    blocks = "blocks"
    variants = "variants"


@dataclass
class _Counts:
    written: int = 0
    archived: int = 0
    warnings: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _print_summary(
    *,
    coll_counts: _Counts | None,
    block_counts: _Counts | None,
    variant_counts: _Counts | None,
    archive_root: Path | None = None,
    verbose: bool = False,
) -> None:
    table = Table(box=None, show_header=True, pad_edge=False, show_edge=False)
    table.add_column("", no_wrap=True, min_width=2)
    table.add_column("Type", style="bold", min_width=14)
    table.add_column("Written", justify="right", style="green")
    table.add_column("Archived", justify="right")

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
        archived_cell = f"[yellow]{counts.archived}[/yellow]" if counts.archived else "[dim]—[/dim]"
        table.add_row(icon, label, str(counts.written), archived_cell)
        all_warnings.extend(counts.warnings)

    extra_lines: list[str] = []

    if verbose:
        for label, counts in rows:
            if counts.details:
                extra_lines.append(f"  [dim]{label}:[/dim]")
                for line in counts.details:
                    extra_lines.append(f"  [dim]  · {line}[/dim]")

    total_archived = sum(c.archived for _, c in rows)
    if total_archived and archive_root is not None:
        extra_lines.append(f"  [dim]Archived items moved to [bold]{archive_root}[/bold][/dim]")

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
            title="[bold cyan]Studio Dump[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()


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
    with_previews: Annotated[
        bool,
        typer.Option(
            "--with-previews",
            help="Also download and dump variant preview images into a preview/ subfolder.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show per-entity detail in the summary.",
        ),
    ] = False,
) -> None:
    """Dump collections, blocks, and variants to a portable file archive."""

    if peer:
        client.set_peer(peer)

    out = (out or _default_dump_path()).resolve()
    out.mkdir(parents=True, exist_ok=True)

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
        if only in (DumpScope.all, DumpScope.collections):
            coll_counts = _dump_collections(out, progress=progress)

        if only in (DumpScope.all, DumpScope.blocks):
            block_counts = _dump_blocks(out, progress=progress)

        if only in (DumpScope.all, DumpScope.variants):
            variant_counts = _dump_variants(out, progress=progress, with_previews=with_previews)

    _print_summary(
        coll_counts=coll_counts,
        block_counts=block_counts,
        variant_counts=variant_counts,
        archive_root=out / ".archive",
        verbose=verbose,
    )

    if zip_output:
        zip_path = out.with_suffix(".zip")
        _zip_directory(out, zip_path)
        shutil.rmtree(out)
        console.print(f"[green]Archive[/green] [bold]{zip_path}[/bold]")
    else:
        console.print(f"[green]Output[/green]  [bold]{out}[/bold]")


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def _dump_collections(root: Path, *, progress: Progress) -> _Counts:
    counts = _Counts()
    response = client.list_collections()
    summaries = response.get("collections", [])

    collections_dir = root / "collections"
    collections_dir.mkdir(parents=True, exist_ok=True)

    # Archive stale collections
    db_identifiers = {summary["identifier"] for summary in summaries}
    if collections_dir.exists():
        for path in collections_dir.glob("*.md"):
            if path.stem not in db_identifiers:
                archive_dir = root / ".archive" / "collections"
                archive_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), archive_dir / path.name)
                counts.archived += 1

    task_id = progress.add_task("[dim]Collections[/dim]", total=len(summaries))

    for summary in summaries:
        detail, _ = client.get_collection_by_id(summary["id"])
        _write_collection(collections_dir, detail)
        counts.written += 1
        counts.details.append(summary["identifier"])
        progress.advance(task_id)

    return counts


def _write_collection(collections_dir: Path, detail: dict) -> None:
    """Write a single collection as a .md file with YAML frontmatter."""
    frontmatter: dict = {"name": detail["name"], "identifier": detail["identifier"]}
    if detail.get("description"):
        frontmatter["description"] = detail["description"]

    fm_text = yaml.dump(frontmatter, **_YAML_OPTS).rstrip()
    content = f"---\n{fm_text}\n---\n"
    (collections_dir / f"{detail['identifier']}.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


def _dump_blocks(root: Path, *, progress: Progress) -> _Counts:
    counts = _Counts()
    response = client.list_blocks()
    summaries = response.get("blocks", [])

    blocks_dir = root / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)

    # Archive stale blocks
    db_identifiers = {summary["identifier"] for summary in summaries}
    if blocks_dir.exists():
        for path in list(blocks_dir.iterdir()):
            if path.is_dir() and path.name not in db_identifiers:
                archive_dir = root / ".archive" / "blocks"
                archive_dir.mkdir(parents=True, exist_ok=True)
                dest = archive_dir / path.name
                if dest.exists():
                    shutil.copytree(path, dest, dirs_exist_ok=True)
                    shutil.rmtree(path)
                else:
                    shutil.move(str(path), dest)
                counts.archived += 1

    task_id = progress.add_task("[dim]Blocks[/dim]", total=len(summaries))

    for summary in summaries:
        detail, _ = client.get_block_by_id(summary["id"])
        _write_block(blocks_dir, detail)
        counts.written += 1
        counts.details.append(summary["identifier"])
        progress.advance(task_id)

    return counts


def _write_block(blocks_dir: Path, detail: dict) -> None:
    """Write block.yaml, description.md, and schema.json for a single block."""
    block_dir = blocks_dir / detail["identifier"]
    block_dir.mkdir(parents=True, exist_ok=True)

    metadata: dict = {"name": detail["name"], "identifier": detail["identifier"]}
    if detail.get("icon"):
        metadata["icon"] = detail["icon"]
    if detail.get("group"):
        metadata["group"] = detail["group"]
    if detail.get("is_shared"):
        metadata["is_shared"] = detail["is_shared"]
    if detail.get("source_app"):
        metadata["source_app"] = detail["source_app"]
    if detail.get("page_types"):
        metadata["page_types"] = detail["page_types"]
    sort_order = detail.get("sort_order", 0)
    if sort_order:
        metadata["sort_order"] = sort_order

    (block_dir / "block.yaml").write_text(yaml.dump(metadata, **_YAML_OPTS), encoding="utf-8")
    (block_dir / "description.md").write_text(detail.get("description", ""), encoding="utf-8")

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

_PREVIEW_FIELDS: list[tuple[str, str]] = [
    ("preview_desktop_light_url", "preview_image_desktop"),
    ("preview_desktop_dark_url", "preview_image_desktop_dark"),
    ("preview_tablet_light_url", "preview_image_tablet"),
    ("preview_tablet_dark_url", "preview_image_tablet_dark"),
    ("preview_mobile_light_url", "preview_image_mobile"),
    ("preview_mobile_dark_url", "preview_image_mobile_dark"),
]


def _dump_variants(root: Path, *, progress: Progress, with_previews: bool = False) -> _Counts:
    counts = _Counts()
    response = client.list_variants()
    summaries = response.get("variants", [])

    blocks_dir = root / "blocks"

    # Clean up stale variants in the dump.
    # Path structure is now flat: blocks/<block>/variants/<variant>/
    db_variants = {(summary["block"]["identifier"], summary["identifier"]) for summary in summaries}
    if blocks_dir.exists():
        for variant_path in list(blocks_dir.glob("*/variants/*")):
            if variant_path.is_dir():
                rel_parts = variant_path.relative_to(blocks_dir).parts
                if len(rel_parts) == 3 and rel_parts[1] == "variants":
                    block_slug = rel_parts[0]
                    variant_slug = rel_parts[2]
                    if (block_slug, variant_slug) not in db_variants:
                        rel = variant_path.relative_to(blocks_dir)
                        archive_path = root / ".archive" / "blocks" / rel
                        if archive_path.exists():
                            shutil.rmtree(archive_path)
                        archive_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(variant_path), archive_path)
                        counts.archived += 1

                        variants_dir = variant_path.parent
                        if variants_dir.is_dir() and not any(variants_dir.iterdir()):
                            variants_dir.rmdir()

    task_id = progress.add_task("[dim]Variants[/dim]", total=len(summaries))

    for summary in summaries:
        block_slug = summary["block"]["identifier"]
        variant_slug = summary["identifier"]

        detail, _ = client.get_variant_by_id(summary["id"])
        variant_dir = blocks_dir / block_slug / "variants" / variant_slug
        variant_dir.mkdir(parents=True, exist_ok=True)
        warn = _write_variant(variant_dir, detail, with_previews=with_previews)
        if warn:
            counts.warnings.append(warn)
        counts.written += 1
        counts.details.append(f"{block_slug}/{variant_slug}")
        progress.advance(task_id)

    return counts


def _write_variant(variant_dir: Path, detail: dict, *, with_previews: bool = False) -> str | None:
    """Write all files for a single variant directory. Returns a warning string or None."""
    variant_meta: dict = {"name": detail["name"], "identifier": detail["identifier"]}
    if detail.get("is_default"):
        variant_meta["is_default"] = True

    (variant_dir / "variant.yaml").write_text(yaml.dump(variant_meta, **_YAML_OPTS), encoding="utf-8")
    (variant_dir / "description.md").write_text(detail.get("description", ""), encoding="utf-8")
    (variant_dir / "template.html").write_text(detail.get("html", ""), encoding="utf-8")
    (variant_dir / "styles.css").write_text(detail.get("css", ""), encoding="utf-8")
    (variant_dir / "script.js").write_text(detail.get("javascript", ""), encoding="utf-8")

    if not with_previews:
        return None

    preview_dir = variant_dir / "preview"
    failed: list[str] = []
    for url_key, field_name in _PREVIEW_FIELDS:
        url = detail.get(url_key)
        if not url:
            continue
        preview_dir.mkdir(exist_ok=True)
        ext = Path(urlparse(url).path).suffix or ".png"
        data = client.download_bytes(url)
        if data:
            (preview_dir / f"{field_name}{ext}").write_bytes(data)
        else:
            failed.append(field_name)

    if failed:
        slug = detail.get("identifier", variant_dir.name)
        return f"{slug}: failed to download preview(s): {', '.join(failed)}"
    return None


# ---------------------------------------------------------------------------
# Zip helpers
# ---------------------------------------------------------------------------


def _zip_directory(source: Path, zip_path: Path) -> None:
    """Recursively pack *source* into *zip_path*."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in source.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(source.parent))
