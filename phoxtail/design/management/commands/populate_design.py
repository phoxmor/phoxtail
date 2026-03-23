"""
Unified management command to populate all design entities from data files.

Auto-discovers and imports:
- Palettes from data/palettes/<group>/<name>.yaml (one file per palette)
- Palette roles from data/palette_roles.yaml (semantic color roles)
- Font families from data/fonts/<font-identifier>/
  (directory with font.yaml and font files)
- Font roles from data/font_roles.yaml (semantic typography roles)

Font auto-conversion:
- Automatically converts TTF/OTF files to WOFF2
- Detects weight/style from font metadata
- Requires: pip install fonttools brotli

Usage:
    python manage.py populate_design                       # Import all entities
    python manage.py populate_design --only=palettes
    python manage.py populate_design --only=palette_roles
    python manage.py populate_design --only=fonts
    python manage.py populate_design --only=font_roles
    python manage.py populate_design --only=fonts --keep-originals
"""

from pathlib import Path

import yaml
from django.core.files import File
from django.core.management.base import BaseCommand

from phoxtail.design.models import (
    FontFamily,
    FontRole,
    FontWeight,
    Palette,
    PaletteRole,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

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


def get_font_metadata(font_path: Path) -> dict:
    """Extract weight and style from font file metadata using fontTools."""
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(font_path)

        weight = 400
        if "OS/2" in font:
            weight = font["OS/2"].usWeightClass

        style = "normal"
        if "OS/2" in font:
            fs_selection = font["OS/2"].fsSelection
            if fs_selection & 1:
                style = "italic"
        elif "head" in font:
            mac_style = font["head"].macStyle
            if mac_style & 2:
                style = "italic"

        font.close()
        return {"weight": weight, "style": style}

    except Exception:
        return parse_weight_style_from_filename(font_path.stem)


def parse_weight_style_from_filename(filename: str) -> dict:
    """Parse weight and style from filename as fallback."""
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


def convert_to_woff2(input_path: Path, output_path: Path) -> bool:
    """Convert a font file to WOFF2 format."""
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(input_path)
        font.flavor = "woff2"
        font.save(output_path)
        font.close()
        return True
    except Exception:
        return False


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
            "--keep-originals",
            action="store_true",
            help="Keep original TTF/OTF files after conversion to WOFF2",
        )

    def handle(self, *args, **options):
        only = options["only"]

        if only in ("all", "palettes"):
            self.import_palettes()

        if only in ("all", "palette_roles"):
            self.import_palette_roles()

        if only in ("all", "fonts"):
            self.import_fonts(options["keep_originals"])

        if only in ("all", "font_roles"):
            self.import_font_roles()

        self.stdout.write(self.style.SUCCESS("Design entities populated successfully!"))

    def import_palettes(self):
        """Import palettes from data/palettes/<group>/<name>.yaml files."""
        self.stdout.write(self.style.SUCCESS("Importing palettes..."))

        palettes_dir = DATA_DIR / "palettes"
        if not palettes_dir.exists():
            self.stdout.write(
                self.style.ERROR(f"Palettes directory not found: {palettes_dir}")
            )
            return

        groups = sorted(d for d in palettes_dir.iterdir() if d.is_dir())
        if not groups:
            self.stdout.write(
                self.style.WARNING(
                    "No palette group directories found in data/palettes/"
                )
            )
            return

        created_count = 0
        skipped_count = 0

        for group_dir in groups:
            palette_files = sorted(group_dir.glob("*.yaml"))
            if not palette_files:
                self.stdout.write(
                    self.style.WARNING(f"  No yaml files found in {group_dir.name}/")
                )
                continue

            self.stdout.write(f"  Group: {group_dir.name}")

            for palette_file in palette_files:
                palette_name = palette_file.stem
                shades = yaml.safe_load(palette_file.read_text())

                palette, created = Palette.objects.get_or_create(
                    title=palette_name,
                    defaults={
                        "description": shades.pop("description", ""),
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
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(f"    Created palette: {palette_name}")
                    )
                    created_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Palette '{palette_name}' already exists, skipping"
                        )
                    )
                    skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Palettes: {created_count} created, {skipped_count} skipped"
            )
        )

    def import_palette_roles(self):
        """Import semantic palette roles from data/palette_roles.yaml."""
        self.stdout.write(self.style.SUCCESS("Importing palette roles..."))

        roles_file = DATA_DIR / "palette_roles.yaml"
        if not roles_file.exists():
            self.stdout.write(
                self.style.ERROR(f"Palette roles data file not found: {roles_file}")
            )
            return

        palette_roles = yaml.safe_load(roles_file.read_text())

        created_count = 0
        skipped_count = 0

        for role_data in palette_roles:
            _, created = PaletteRole.objects.get_or_create(
                identifier=role_data["identifier"],
                defaults={
                    "name": role_data["name"],
                    "description": role_data["description"],
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created role: {role_data['name']} "
                        f"({role_data['identifier']})"
                    )
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {role_data['identifier']} already exists, skipping..."
                    )
                )
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Palette roles: {created_count} created, {skipped_count} skipped"
            )
        )

    def import_fonts(self, keep_originals=False):
        """Import font families from data/fonts/ directories."""
        self.stdout.write(self.style.SUCCESS("Importing font families..."))

        try:
            import fontTools  # noqa: F401
        except ImportError:
            self.stdout.write(
                self.style.ERROR(
                    "fonttools is required. Install with: pip install fonttools brotli"
                )
            )
            return

        fonts_dir = DATA_DIR / "fonts"
        if not fonts_dir.exists():
            self.stdout.write(
                self.style.WARNING(f"Fonts directory not found: {fonts_dir}")
            )
            return

        font_dirs = [d for d in fonts_dir.iterdir() if d.is_dir()]
        if not font_dirs:
            self.stdout.write(
                self.style.WARNING("No font directories found in fonts directory")
            )
            return

        created_families = 0
        skipped_families = 0
        created_weights = 0
        skipped_weights = 0
        converted_files = 0

        for font_dir in sorted(font_dirs):
            metadata_file = font_dir / "font.yaml"
            if not metadata_file.exists():
                self.stdout.write(
                    self.style.WARNING(f"Skipping {font_dir.name}: missing font.yaml")
                )
                continue

            try:
                metadata = yaml.safe_load(metadata_file.read_text())
            except yaml.YAMLError as e:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {font_dir.name}: invalid font.yaml - {e}"
                    )
                )
                continue

            name = metadata.get("name")
            if not name:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {font_dir.name}: missing 'name' in font.yaml"
                    )
                )
                continue

            family, family_created = FontFamily.objects.get_or_create(
                name=name,
                defaults={
                    "description": metadata.get("description", ""),
                    "category": metadata.get("category", "sans-serif"),
                    "fallback": metadata.get(
                        "fallback", "system-ui, -apple-system, sans-serif"
                    ),
                },
            )

            if family_created:
                self.stdout.write(
                    self.style.SUCCESS(f"  Created font family: {family.name}")
                )
                created_families += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Font family '{family.name}' already exists, "
                        f"checking weights..."
                    )
                )
                skipped_families += 1

            font_files = []
            for ext in ["*.ttf", "*.otf", "*.TTF", "*.OTF"]:
                font_files.extend(font_dir.glob(ext))

            woff2_files = list(font_dir.glob("*.woff2")) + list(
                font_dir.glob("*.WOFF2")
            )

            if not font_files and not woff2_files:
                self.stdout.write(
                    self.style.WARNING(f"  No font files found in {font_dir.name}/")
                )
                continue

            for font_file in font_files:
                woff2_path = font_file.with_suffix(".woff2")

                if woff2_path.exists():
                    self.stdout.write(
                        f"    {woff2_path.name} already exists, skipping conversion"
                    )
                    if woff2_path not in woff2_files:
                        woff2_files.append(woff2_path)
                    continue

                self.stdout.write(f"    Converting {font_file.name} to WOFF2...")

                if convert_to_woff2(font_file, woff2_path):
                    original_size = font_file.stat().st_size
                    new_size = woff2_path.stat().st_size
                    reduction = (1 - new_size / original_size) * 100
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"      {original_size:,} -> {new_size:,} bytes "
                            f"({reduction:.1f}% smaller)"
                        )
                    )
                    woff2_files.append(woff2_path)
                    converted_files += 1

                    if not keep_originals:
                        font_file.unlink()
                        self.stdout.write(f"      Deleted original {font_file.name}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"      Failed to convert {font_file.name}")
                    )

            for woff2_file in sorted(woff2_files):
                font_meta = get_font_metadata(woff2_file)
                weight_value = font_meta["weight"]
                style = font_meta["style"]

                existing_weight = FontWeight.objects.filter(
                    family=family, weight=weight_value, style=style
                ).first()

                if existing_weight:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    Weight {weight_value} {style} already "
                            f"exists, skipping..."
                        )
                    )
                    skipped_weights += 1
                    continue

                font_weight = FontWeight(
                    family=family,
                    weight=weight_value,
                    style=style,
                )

                with open(woff2_file, "rb") as f:
                    font_weight.file.save(
                        woff2_file.name,
                        File(f),
                        save=True,
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"    Created weight: {weight_value} {style} "
                        f"({woff2_file.name})"
                    )
                )
                created_weights += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Font families: {created_families} created, {skipped_families} skipped"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Font weights: {created_weights} created, {skipped_weights} skipped"
            )
        )
        if converted_files:
            self.stdout.write(
                self.style.SUCCESS(f"Files converted to WOFF2: {converted_files}")
            )

    def import_font_roles(self):
        """Import semantic font roles from data/font_roles.yaml."""
        self.stdout.write(self.style.SUCCESS("Importing font roles..."))

        roles_file = DATA_DIR / "font_roles.yaml"
        if not roles_file.exists():
            self.stdout.write(
                self.style.ERROR(f"Font roles data file not found: {roles_file}")
            )
            return

        font_roles = yaml.safe_load(roles_file.read_text())

        created_count = 0
        skipped_count = 0

        for role_data in font_roles:
            _, created = FontRole.objects.get_or_create(
                identifier=role_data["identifier"],
                defaults={
                    "name": role_data["name"],
                    "description": role_data["description"],
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Created role: {role_data['name']} "
                        f"({role_data['identifier']})"
                    )
                )
                created_count += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {role_data['identifier']} already exists, skipping..."
                    )
                )
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Font roles: {created_count} created, {skipped_count} skipped"
            )
        )
