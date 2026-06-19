"""
Unified management command to populate all design entities from data files.

Discovers ``management/data/`` directories across all installed Django apps,
so each phoxtail app can ship its own palettes, fonts, and roles alongside
its models.

Auto-discovers and imports:
- Palettes from data/palettes/<group>/<name>.yaml (one file per palette)
- Palette roles from data/palette_roles.yaml (semantic color roles)
- Font families from data/fonts/<font-identifier>/
  (directory with font.yaml and WOFF2 font files)
- Font roles from data/font_roles.yaml (semantic typography roles)

Usage:
    python manage.py populate_design                       # Import all entities
    python manage.py populate_design --only=palettes
    python manage.py populate_design --only=palette_roles
    python manage.py populate_design --only=fonts
    python manage.py populate_design --only=font_roles
    python manage.py populate_design --verbose             # Per-entity detail
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.apps import apps
from django.core.files import File
from django.core.management.base import BaseCommand
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from phoxtail.design.models import (
    FontFamily,
    FontRole,
    FontWeight,
    Palette,
    PaletteRole,
    PaletteSet,
)

console = Console()

_ICONS = {
    "ok": "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
}


@dataclass
class _Counts:
    created: int = 0
    skipped: int = 0
    warnings: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


def _get_data_dirs() -> list[tuple[str, Path]]:
    """Discover management/data/ directories from all installed apps.

    Returns (app_label, path) pairs. The design app's own directory is
    always listed first so its roles exist before other apps reference them.
    """
    design_app = apps.get_app_config("phoxtail_design")
    design_dir = Path(__file__).resolve().parent.parent / "data"
    dirs: list[tuple[str, Path]] = []
    if design_dir.is_dir():
        dirs.append((design_app.label, design_dir))

    for app_config in apps.get_app_configs():
        data_dir = Path(app_config.path) / "management" / "data"
        if data_dir.is_dir() and data_dir != design_dir:
            dirs.append((app_config.label, data_dir))

    return dirs


WEIGHT_NAME_MAP = {
    "thin": 100,
    "hairline": 100,
    "extralight": 200,
    "ultralight": 200,
    "light": 300,
    "regular": 400,
    "normal": 400,
    "medium": 500,
    "semibold": 600,
    "demibold": 600,
    "bold": 700,
    "extrabold": 800,
    "ultrabold": 800,
    "black": 900,
    "heavy": 900,
}


def parse_weight_style_from_filename(filename: str) -> dict:
    """Parse weight and style from filename."""
    weight = 400
    style = "normal"

    parts = filename.rsplit("-", 1)
    if len(parts) == 2:
        variant = parts[1].lower()

        if "italic" in variant:
            style = "italic"
            variant = variant.replace("italic", "")

        for name, value in WEIGHT_NAME_MAP.items():
            if name in variant:
                weight = value
                break

    return {"weight": weight, "style": style}


def _print_summary(
    *,
    palette_counts: _Counts | None,
    palette_role_counts: _Counts | None,
    font_family_counts: _Counts | None,
    font_weight_counts: _Counts | None,
    font_role_counts: _Counts | None,
    verbose: bool = False,
) -> None:
    table = Table(box=None, show_header=True, pad_edge=False, show_edge=False)
    table.add_column("", no_wrap=True, min_width=2)
    table.add_column("Type", style="bold", min_width=14)
    table.add_column("Created", justify="right", style="green")
    table.add_column("Skipped", justify="right", style="yellow")

    rows: list[tuple[str, _Counts]] = []
    if palette_counts is not None:
        rows.append(("Palettes", palette_counts))
    if palette_role_counts is not None:
        rows.append(("Palette Roles", palette_role_counts))
    if font_family_counts is not None:
        rows.append(("Font Families", font_family_counts))
    if font_weight_counts is not None:
        rows.append(("Font Weights", font_weight_counts))
    if font_role_counts is not None:
        rows.append(("Font Roles", font_role_counts))

    all_warnings: list[str] = []
    for label, counts in rows:
        icon = _ICONS["warn"] if counts.warnings else _ICONS["ok"]
        table.add_row(icon, label, str(counts.created), str(counts.skipped))
        all_warnings.extend(counts.warnings)

    extra_lines: list[str] = []

    if verbose:
        for label, counts in rows:
            if counts.details:
                extra_lines.append(f"  [dim]{label}:[/dim]")
                for line in counts.details:
                    extra_lines.append(f"  [dim]  · {line}[/dim]")

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
            title="[bold cyan]Populate Design[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()


class Command(BaseCommand):
    help = "Populates all design entities from data files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--only",
            choices=["palettes", "palette_roles", "fonts", "font_roles", "all"],
            default="all",
            help="Import only specific entity type",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Show per-entity detail in the summary",
        )

    def handle(self, *args, **options):
        only = options["only"]
        verbose = options["verbose"]

        palette_counts: _Counts | None = None
        palette_role_counts: _Counts | None = None
        font_family_counts: _Counts | None = None
        font_weight_counts: _Counts | None = None
        font_role_counts: _Counts | None = None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=30),
            MofNCompleteColumn(),
            transient=True,
            console=console,
            disable=not console.is_terminal,
        ) as progress:
            if only in ("all", "palettes"):
                palette_counts = self._import_palettes(progress)

            if only in ("all", "palette_roles"):
                palette_role_counts = self._import_palette_roles(progress)

            if only in ("all", "fonts"):
                font_family_counts, font_weight_counts = self._import_fonts(progress)

            if only in ("all", "font_roles"):
                font_role_counts = self._import_font_roles(progress)

        _print_summary(
            palette_counts=palette_counts,
            palette_role_counts=palette_role_counts,
            font_family_counts=font_family_counts,
            font_weight_counts=font_weight_counts,
            font_role_counts=font_role_counts,
            verbose=verbose,
        )

    def _import_palettes(self, progress: Progress) -> _Counts:
        counts = _Counts()

        group_dirs: list[Path] = []
        for _app_label, data_dir in _get_data_dirs():
            palettes_dir = data_dir / "palettes"
            if palettes_dir.exists():
                group_dirs.extend(sorted(d for d in palettes_dir.iterdir() if d.is_dir()))

        # Pre-collect (group_dir, palette_file) pairs so we know the total upfront.
        work_items: list[tuple[Path, Path]] = []
        for group_dir in group_dirs:
            order_file = group_dir / "order.yaml"
            if order_file.exists():
                ordered_names = yaml.safe_load(order_file.read_text())
                files = [group_dir / f"{name}.yaml" for name in ordered_names if (group_dir / f"{name}.yaml").exists()]
            else:
                files = sorted(f for f in group_dir.glob("*.yaml") if f.name not in ("group.yaml", "order.yaml"))
            for f in files:
                work_items.append((group_dir, f))

        task_id = progress.add_task("[dim]Palettes[/dim]", total=len(work_items))

        palette_sets: dict[str, PaletteSet] = {}
        sort_order = 0

        for group_dir, palette_file in work_items:
            group_key = str(group_dir)
            if group_key not in palette_sets:
                group_meta: dict = {}
                group_yaml = group_dir / "group.yaml"
                if group_yaml.exists():
                    group_meta = yaml.safe_load(group_yaml.read_text()) or {}
                palette_set, _ = PaletteSet.objects.get_or_create(
                    identifier=group_dir.name,
                    defaults={
                        "name": group_meta.get("name", group_dir.name.replace("_", " ").title()),
                        "description": group_meta.get("description", ""),
                    },
                )
                palette_sets[group_key] = palette_set
            else:
                palette_set = palette_sets[group_key]

            palette_name = palette_file.stem
            shades = yaml.safe_load(palette_file.read_text())

            _, created = Palette.objects.get_or_create(
                palette_set=palette_set,
                title=palette_name,
                defaults={
                    "description": shades.pop("description", ""),
                    "sort_order": sort_order,
                    "shade_50": shades["50"],
                    "shade_100": shades["100"],
                    "shade_200": shades["200"],
                    "shade_300": shades["300"],
                    "shade_400": shades["400"],
                    "shade_500": shades["500"],
                    "shade_600": shades["600"],
                    "shade_700": shades["700"],
                    "shade_800": shades["800"],
                    "shade_900": shades["900"],
                    "shade_950": shades["950"],
                },
            )
            sort_order += 1

            if created:
                counts.created += 1
                counts.details.append(f"created {palette_name} ({group_dir.name})")
            else:
                counts.skipped += 1
                counts.details.append(f"skipped {palette_name} ({group_dir.name}) — already exists")

            progress.advance(task_id)

        return counts

    def _import_palette_roles(self, progress: Progress) -> _Counts:
        counts = _Counts()

        palette_roles: list[dict] = []
        for _app_label, data_dir in _get_data_dirs():
            roles_file = data_dir / "palette_roles.yaml"
            if roles_file.exists():
                palette_roles.extend(yaml.safe_load(roles_file.read_text()) or [])

        task_id = progress.add_task("[dim]Palette Roles[/dim]", total=len(palette_roles))

        for role_data in palette_roles:
            _, created = PaletteRole.objects.get_or_create(
                identifier=role_data["identifier"],
                defaults={
                    "name": role_data["name"],
                    "description": role_data["description"],
                },
            )
            if created:
                counts.created += 1
                counts.details.append(f"created {role_data['name']} ({role_data['identifier']})")
            else:
                counts.skipped += 1
                counts.details.append(f"skipped {role_data['identifier']} — already exists")

            progress.advance(task_id)

        return counts

    def _import_fonts(self, progress: Progress) -> tuple[_Counts, _Counts]:
        family_counts = _Counts()
        weight_counts = _Counts()

        font_dirs: list[Path] = []
        for _app_label, data_dir in _get_data_dirs():
            fonts_dir = data_dir / "fonts"
            if fonts_dir.exists():
                font_dirs.extend(sorted(d for d in fonts_dir.iterdir() if d.is_dir()))

        task_id = progress.add_task("[dim]Fonts[/dim]", total=len(font_dirs))

        for font_dir in sorted(font_dirs):
            metadata_file = font_dir / "font.yaml"
            if not metadata_file.exists():
                family_counts.warnings.append(f"{font_dir.name}: missing font.yaml")
                progress.advance(task_id)
                continue

            try:
                metadata = yaml.safe_load(metadata_file.read_text())
            except yaml.YAMLError as e:
                family_counts.warnings.append(f"{font_dir.name}: invalid font.yaml — {e}")
                progress.advance(task_id)
                continue

            name = metadata.get("name")
            if not name:
                family_counts.warnings.append(f"{font_dir.name}: missing 'name' in font.yaml")
                progress.advance(task_id)
                continue

            family, family_created = FontFamily.objects.get_or_create(
                name=name,
                defaults={
                    "description": metadata.get("description", ""),
                    "category": metadata.get("category", "sans-serif"),
                    "fallback": metadata.get("fallback", "system-ui, -apple-system, sans-serif"),
                },
            )

            if family_created:
                family_counts.created += 1
                family_counts.details.append(f"created {family.name}")
            else:
                family_counts.skipped += 1
                family_counts.details.append(f"skipped {family.name} — already exists")

            woff2_files = sorted(list(font_dir.glob("*.woff2")) + list(font_dir.glob("*.WOFF2")))

            if not woff2_files:
                weight_counts.warnings.append(f"{font_dir.name}: no WOFF2 files found")
                progress.advance(task_id)
                continue

            for woff2_file in woff2_files:
                font_meta = parse_weight_style_from_filename(woff2_file.stem)
                weight_value = font_meta["weight"]
                style = font_meta["style"]

                if FontWeight.objects.filter(family=family, weight=weight_value, style=style).exists():
                    weight_counts.skipped += 1
                    weight_counts.details.append(f"skipped {name} {weight_value} {style} — already exists")
                    continue

                font_weight = FontWeight(family=family, weight=weight_value, style=style)
                with open(woff2_file, "rb") as f:
                    font_weight.file.save(woff2_file.name, File(f), save=True)

                weight_counts.created += 1
                weight_counts.details.append(f"created {name} {weight_value} {style}")

            progress.advance(task_id)

        return family_counts, weight_counts

    def _import_font_roles(self, progress: Progress) -> _Counts:
        counts = _Counts()

        font_roles: list[dict] = []
        for _app_label, data_dir in _get_data_dirs():
            roles_file = data_dir / "font_roles.yaml"
            if roles_file.exists():
                font_roles.extend(yaml.safe_load(roles_file.read_text()) or [])

        task_id = progress.add_task("[dim]Font Roles[/dim]", total=len(font_roles))

        for role_data in font_roles:
            _, created = FontRole.objects.get_or_create(
                identifier=role_data["identifier"],
                defaults={
                    "name": role_data["name"],
                    "description": role_data["description"],
                },
            )
            if created:
                counts.created += 1
                counts.details.append(f"created {role_data['name']} ({role_data['identifier']})")
            else:
                counts.skipped += 1
                counts.details.append(f"skipped {role_data['identifier']} — already exists")

            progress.advance(task_id)

        return counts
