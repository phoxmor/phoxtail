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
    phoxtail studio load --verbose               # show full per-entity detail
"""

from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from phoxtail.cli.studio import client
from phoxtail.cli.utils.config import find_config_file

_ICONS = {
    "ok": "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
}


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


@dataclass
class _Counts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_incompatible: int = 0
    skipped_other: int = 0
    warnings: list[str] = field(default_factory=list)

    def total_skipped(self) -> int:
        return self.skipped_incompatible + self.skipped_other


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
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Show full per-entity detail in the summary (e.g. which blocks were skipped).",
        ),
    ] = False,
) -> None:
    """Load collections, blocks, and variants from a file archive into a project."""

    if peer:
        client.set_peer(peer)

    tmp_dir: Path | None = None
    data_root = (path or _default_dump_path()).resolve()

    if zipfile.is_zipfile(data_root):
        tmp_dir = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(data_root) as zf:
            zf.extractall(tmp_dir)
        subdirs = [d for d in tmp_dir.iterdir() if d.is_dir()]
        data_root = subdirs[0] if len(subdirs) == 1 else tmp_dir

    try:
        incompatible, skipped_by_app = _preflight(data_root)

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
        ) as progress:
            if only in (LoadScope.all, LoadScope.collections):
                coll_counts = _load_collections(data_root, force=force, progress=progress)

            if only in (LoadScope.all, LoadScope.blocks):
                block_counts = _load_blocks(data_root, incompatible=incompatible, force=force, progress=progress)

            if only in (LoadScope.all, LoadScope.variants):
                variant_counts = _load_variants(data_root, incompatible=incompatible, force=force, progress=progress)

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    _print_summary(
        coll_counts=coll_counts,
        block_counts=block_counts,
        variant_counts=variant_counts,
        skipped_by_app=skipped_by_app,
        verbose=verbose,
    )


# ---------------------------------------------------------------------------
# Summary panel
# ---------------------------------------------------------------------------


def _print_summary(
    *,
    coll_counts: _Counts | None,
    block_counts: _Counts | None,
    variant_counts: _Counts | None,
    skipped_by_app: dict[str, list[str]],
    verbose: bool = False,
) -> None:
    table = Table(box=None, show_header=True, pad_edge=False, show_edge=False)
    table.add_column("", no_wrap=True, min_width=2)
    table.add_column("Type", style="bold", min_width=12)
    table.add_column("Created", justify="right", style="green")
    table.add_column("Updated", justify="right", style="yellow")
    table.add_column("Unchanged", justify="right", style="dim")
    table.add_column("Skipped", justify="right", style="yellow")

    rows: list[tuple[str, _Counts]] = []
    if coll_counts is not None:
        rows.append(("Collections", coll_counts))
    if block_counts is not None:
        rows.append(("Blocks", block_counts))
    if variant_counts is not None:
        rows.append(("Variants", variant_counts))

    for label, counts in rows:
        icon = _ICONS["warn"] if counts.warnings else _ICONS["ok"]
        table.add_row(
            icon,
            label,
            str(counts.created),
            str(counts.updated),
            str(counts.unchanged),
            str(counts.total_skipped()),
        )

    # Collect all warnings across phases — always shown regardless of --verbose.
    all_warnings: list[str] = []
    for _, counts in rows:
        all_warnings.extend(counts.warnings)

    extra_lines: list[str] = []

    if skipped_by_app:
        if verbose:
            extra_lines.append("  [dim]Skipped — app not installed:[/dim]")
            for app_label, identifiers in sorted(skipped_by_app.items()):
                extra_lines.append(f"  [dim]  {app_label}:[/dim]")
                for ident in identifiers:
                    extra_lines.append(f"  [dim]    · {ident}[/dim]")
        else:
            total_skipped = sum(len(ids) for ids in skipped_by_app.values())
            extra_lines.append(f"  [dim]{total_skipped} block(s) skipped — run with --verbose for details[/dim]")

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
            title="[bold cyan]Studio Load[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()


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
# Pre-flight compatibility check
# ---------------------------------------------------------------------------


def _preflight(root: Path) -> tuple[set[str], dict[str, list[str]]]:
    """Scan dump for blocks whose page_types reference uninstalled apps.

    Returns ``(incompatible_identifiers, skipped_by_app)``:
    - ``incompatible_identifiers`` — block identifiers to skip entirely
    - ``skipped_by_app`` — maps app_label → list of block identifiers for the summary
    """
    blocks_dir = root / "blocks"
    if not blocks_dir.exists():
        return set(), {}

    valid_app_labels = client.list_page_type_app_labels()

    unknown: dict[str, list[str]] = {}
    incompatible: set[str] = set()

    for block_dir in sorted(d for d in blocks_dir.iterdir() if d.is_dir()):
        metadata_file = block_dir / "block.yaml"
        if not metadata_file.exists():
            continue
        try:
            metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue

        identifier = metadata.get("identifier", block_dir.name)

        # Check source_app first — strongest signal.
        source_app = metadata.get("source_app", "")
        if source_app and source_app not in valid_app_labels:
            unknown.setdefault(source_app, []).append(identifier)
            incompatible.add(identifier)
            continue

        # Also check page_types — catches manually-created blocks that restrict
        # to an uninstalled app but have no source_app set.
        page_types = metadata.get("page_types") or []
        for pt in page_types:
            try:
                app_label = pt.rsplit(".", 1)[0]
            except (ValueError, AttributeError):
                continue
            if app_label not in valid_app_labels:
                unknown.setdefault(app_label, []).append(identifier)
                incompatible.add(identifier)

    return incompatible, unknown


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def _load_collections(root: Path, *, force: bool = False, progress: Progress | None = None) -> _Counts:
    counts = _Counts()
    collections_dir = root / "collections"

    all_files = sorted(collections_dir.glob("*.md")) if collections_dir.exists() else []
    task_id = progress.add_task("[dim]Collections[/dim]", total=len(all_files)) if progress else None

    id_by_identifier: dict[str, int] = {}
    if force:
        data = client.list_collections()
        id_by_identifier = {c["identifier"]: c["id"] for c in data.get("collections", [])}

    for md_file in all_files:
        metadata, _ = _parse_frontmatter(md_file.read_text(encoding="utf-8"))
        name = metadata.get("name")
        if not name:
            counts.warnings.append(f"{md_file.name}: missing 'name' in frontmatter")
            counts.skipped_other += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        identifier = metadata.get("identifier", md_file.stem)
        description = metadata.get("description", "")

        _, status = client.create_collection(
            identifier=identifier,
            name=name,
            description=description,
        )
        if status == 409:
            if force:
                coll_id = id_by_identifier.get(identifier)
                if coll_id is None:
                    counts.warnings.append(f"{identifier}: exists but ID not found, skipping")
                    counts.skipped_other += 1
                else:
                    _, etag = client.get_collection_by_id(coll_id)
                    client.update_collection_by_id(
                        coll_id,
                        name=name,
                        description=description,
                        etag=etag or "*",
                    )
                    counts.updated += 1
            else:
                counts.unchanged += 1
        else:
            counts.created += 1

        if progress and task_id is not None:
            progress.advance(task_id)

    return counts


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


def _load_blocks(
    root: Path, *, incompatible: set[str], force: bool = False, progress: Progress | None = None
) -> _Counts:
    counts = _Counts()
    blocks_dir = root / "blocks"

    all_dirs = sorted(d for d in blocks_dir.iterdir() if d.is_dir()) if blocks_dir.exists() else []
    task_id = progress.add_task("[dim]Blocks[/dim]", total=len(all_dirs)) if progress else None

    id_by_identifier: dict[str, int] = {}
    if force:
        data = client.list_blocks()
        id_by_identifier = {b["identifier"]: b["id"] for b in data.get("blocks", [])}

    for block_dir in all_dirs:
        metadata_file = block_dir / "block.yaml"
        schema_file = block_dir / "schema.json"

        if not metadata_file.exists():
            counts.warnings.append(f"{block_dir.name}: missing block.yaml")
            counts.skipped_other += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            continue
        if not schema_file.exists():
            counts.warnings.append(f"{block_dir.name}: missing schema.json")
            counts.skipped_other += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        try:
            metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            counts.warnings.append(f"{block_dir.name}: invalid block.yaml — {exc}")
            counts.skipped_other += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        try:
            schema = json.loads(schema_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            counts.warnings.append(f"{block_dir.name}: invalid schema.json — {exc}")
            counts.skipped_other += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        identifier = metadata.get("identifier", block_dir.name)

        if identifier in incompatible:
            counts.skipped_incompatible += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

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
                    counts.warnings.append(f"{identifier}: exists but ID not found, skipping")
                    counts.skipped_other += 1
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
                    counts.updated += 1
            else:
                counts.unchanged += 1
        else:
            counts.created += 1

        if progress and task_id is not None:
            progress.advance(task_id)

    return counts


# ---------------------------------------------------------------------------
# Variants
# ---------------------------------------------------------------------------


@dataclass
class _VariantItem:
    block_dir: Path
    block_identifier: str
    variant_dir: Path


def _load_variants(
    root: Path, *, incompatible: set[str], force: bool = False, progress: Progress | None = None
) -> _Counts:
    counts = _Counts()
    blocks_dir = root / "blocks"
    if not blocks_dir.exists():
        return counts

    # Collect all variant work items upfront so total is known before we start.
    work_items: list[_VariantItem] = []
    for block_dir in sorted(d for d in blocks_dir.iterdir() if d.is_dir()):
        if block_dir.name in incompatible:
            continue
        variants_dir = block_dir / "variants"
        if not variants_dir.exists():
            continue
        for variant_dir in sorted(d for d in variants_dir.iterdir() if d.is_dir()):
            work_items.append(
                _VariantItem(
                    block_dir=block_dir,
                    block_identifier=block_dir.name,
                    variant_dir=variant_dir,
                )
            )

    task_id = progress.add_task("[dim]Variants[/dim]", total=len(work_items)) if progress else None

    blocks_data = client.list_blocks()
    block_id_by_identifier = {b["identifier"]: b["id"] for b in blocks_data.get("blocks", [])}

    variant_id_by_key: dict[tuple[str, str], int] = {}
    if force:
        variants_data = client.list_variants()
        for v in variants_data.get("variants", []):
            key = (v["block"]["identifier"], v["identifier"])
            variant_id_by_key[key] = v["id"]

    seen_missing_blocks: set[str] = set()

    for item in work_items:
        block_id = block_id_by_identifier.get(item.block_identifier)
        if block_id is None:
            if item.block_identifier not in seen_missing_blocks:
                seen_missing_blocks.add(item.block_identifier)
                counts.warnings.append(f"block {item.block_identifier}: not found on server")
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        variant_dir = item.variant_dir
        metadata_file = variant_dir / "variant.yaml"
        description_file = variant_dir / "description.md"
        html_file = variant_dir / "template.html"

        required = [
            (metadata_file, "variant.yaml"),
            (description_file, "description.md"),
            (html_file, "template.html"),
        ]
        missing = next((label for f, label in required if not f.exists()), None)
        if missing:
            counts.warnings.append(f"{variant_dir.name}: missing {missing}")
            counts.skipped_other += 1
            if progress and task_id is not None:
                progress.advance(task_id)
            continue

        try:
            metadata = yaml.safe_load(metadata_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            counts.warnings.append(f"{variant_dir.name}: invalid variant.yaml — {exc}")
            counts.skipped_other += 1
            if progress and task_id is not None:
                progress.advance(task_id)
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
            collection_id=None,
            description=description,
            html=html,
            css=css,
            javascript=javascript,
            is_default=is_default,
        )
        if status == 409:
            if force:
                key = (item.block_identifier, identifier)
                variant_id = variant_id_by_key.get(key)
                if variant_id is None:
                    counts.warnings.append(f"{item.block_identifier}/{identifier}: exists but ID not found, skipping")
                    counts.skipped_other += 1
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
                    counts.updated += 1
            else:
                counts.unchanged += 1
        else:
            counts.created += 1

        if progress and task_id is not None:
            progress.advance(task_id)

    return counts
