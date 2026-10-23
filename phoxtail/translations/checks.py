"""A startup check that phoxtail's translations are installed, before every other app's.

Registered by core, which is always installed, so a missing app is noticed.

Django takes a sentence's translation from the first installed app that has
it, so an app with translations listed earlier shows its own wording where
phoxtail's differs (Wagtail's "Κωδικός" for phoxtail's "Συνθηματικό"),
silently.
"""

from pathlib import Path

from django.apps import apps
from django.core.checks import Tags, Warning, register

LABEL = "phoxtail_translations"


def listed_before(installed: list[tuple[str, str, str]]) -> list[str]:
    """The apps with translations that come before this one, from (label, name, path) in installed order."""
    earlier: list[str] = []
    for label, name, path in installed:
        if label == LABEL:
            return earlier
        if (Path(path) / "locale").is_dir():
            earlier.append(name)
    return []


@register(Tags.translation)
def translations_first(app_configs, **kwargs):
    if not apps.is_installed("phoxtail.translations"):
        return [
            Warning(
                "phoxtail.translations is not installed, so phoxtail's screens show no translations.",
                hint="List phoxtail.core first and call wire_apps, or add phoxtail.translations above it.",
                id="phoxtail_translations.W002",
            )
        ]
    earlier = listed_before([(config.label, config.name, config.path) for config in apps.get_app_configs()])
    if not earlier:
        return []
    return [
        Warning(
            f"{', '.join(earlier)} come before phoxtail.translations in INSTALLED_APPS, "
            "so their wording is shown where phoxtail's differs.",
            hint="List phoxtail.core first and let wire_apps place phoxtail.translations, or move it above them.",
            id="phoxtail_translations.W001",
        )
    ]
