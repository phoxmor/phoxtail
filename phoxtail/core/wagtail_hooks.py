import os
from pathlib import Path

from wagtail import hooks

_APP_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _APP_DIR / "templates"


@hooks.register("register_icons")
def register_icons(icons):
    svg_icons = []
    svg_dir = _TEMPLATES_DIR / "phoxtail_core" / "svgs"

    if svg_dir.exists():
        for root, dirs, files in os.walk(svg_dir):
            for file in files:
                if file.endswith(".html"):
                    relative_path = os.path.relpath(
                        os.path.join(root, file),
                        str(_TEMPLATES_DIR),
                    )
                    svg_icons.append(relative_path)

    return icons + svg_icons


@hooks.register("construct_main_menu")
def change_main_menu_icons(request, menu_items):
    for item in menu_items:
        if item.name == "settings":
            item.icon_name = "settings"


@hooks.register("construct_reports_menu")
def change_reports_menu_icons(request, menu_items):
    for item in menu_items:
        if item.name == "locked-pages":
            item.icon_name = "lock"
        if item.name == "workflows":
            item.icon_name = "flowchart"
        if item.name == "workflow-tasks":
            item.icon_name = "keep"
        if item.name == "site-history":
            item.icon_name = "history"
        if item.name == "aging-pages":
            item.icon_name = "schedule"
        if item.name == "page-types-usage":
            item.icon_name = "docs"


@hooks.register("construct_settings_menu")
def change_settings_menu_icons(request, menu_items):
    for item in menu_items:
        if item.name == "workflows":
            item.icon_name = "flowchart"
        if item.name == "workflow-tasks":
            item.icon_name = "keep"
        if item.name == "users":
            item.icon_name = "person"
        if item.name == "groups":
            item.icon_name = "group"
        if item.name == "sites":
            item.icon_name = "globe"
        if item.name == "locales":
            item.icon_name = "globe-location-pin"
        if item.name == "collections":
            item.icon_name = "folder-open"
        if item.name == "redirects":
            item.icon_name = "directions"


@hooks.register("construct_help_menu")
def change_help_menu_icons(request, menu_items):
    for item in menu_items:
        if item.name == "help":
            item.icon_name = "help"
        if item.name == "keyboard-shortcuts-trigger":
            item.icon_name = "keyboard"
