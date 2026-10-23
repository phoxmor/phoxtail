"""phoxtail's translations: its own list per language, and its corrections to other packages'."""

import gettext
import importlib
import re
from io import BytesIO
from pathlib import Path

import pytest
from babel.messages.mofile import write_mo
from django.utils import translation

from phoxtail.translations.checks import listed_before, translations_first
from phoxtail.translations.compile import LOCALE, PACKAGES, combined, languages, main, read, untranslated

LANGUAGES = languages()
CORRECTIONS = sorted(PACKAGES.glob("*/*.po"))


def _key(message):
    return message.context, message.id if isinstance(message.id, str) else message.id[0]


def _entries(path):
    return [message for message in read(path) if message.id]


@pytest.mark.parametrize("path", CORRECTIONS, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_each_correction_is_for_a_sentence_its_package_still_writes(path):
    """A package that rewords a sentence leaves phoxtail's correction behind: drop it, or redo it."""
    package, language = path.parent.name, path.stem
    folder = Path(importlib.import_module(package).__file__).parent
    theirs = {
        _key(message)
        for catalogue in folder.glob(f"**/locale/{language}/LC_MESSAGES/django.po")
        for message in _entries(catalogue)
    }

    assert [_key(message)[1] for message in _entries(path) if _key(message) not in theirs] == []


@pytest.mark.parametrize("path", CORRECTIONS, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_each_correction_is_translated_for_sure(path):
    catalogue = read(path)

    assert catalogue.plural_forms
    assert untranslated(catalogue) == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_compiled_list_is_up_to_date(language):
    """Holds the corrections and the latest translations: Django's compilemessages leaves the corrections out."""

    def entries(file):
        catalog = gettext.GNUTranslations(file)._catalog
        # The header names the babel release that compiled it; any release will do.
        catalog[""] = re.sub(r"^Generated-By: .*\n", "", catalog[""], flags=re.MULTILINE)
        return catalog

    expected = BytesIO()
    write_mo(expected, combined(language))
    expected.seek(0)
    compiled = LOCALE / language / "LC_MESSAGES" / "django.mo"

    with compiled.open("rb") as file:
        assert entries(file) == entries(expected)


@pytest.mark.parametrize("path", CORRECTIONS, ids=lambda path: f"{path.parent.name}/{path.name}")
def test_each_correction_is_what_the_language_reads(path):
    def reads(message):
        if isinstance(message.id, tuple):
            if message.context:
                return tuple(translation.npgettext(message.context, *message.id, n) for n in (1, 5))
            return tuple(translation.ngettext(*message.id, n) for n in (1, 5))
        return translation.pgettext(message.context, message.id) if message.context else translation.gettext(message.id)

    def ours(message):
        return tuple(message.string) if isinstance(message.id, tuple) else message.string

    with translation.override(path.stem):
        assert [_key(message)[1] for message in _entries(path) if reads(message) != ours(message)] == []


def test_a_correction_to_a_sentence_phoxtail_writes_is_refused(tmp_path, monkeypatch):
    (tmp_path / "allauth").mkdir()
    (tmp_path / "allauth" / "el.po").write_text('msgid "Cancel"\nmsgstr "Άκυρο"\n', encoding="utf-8")
    monkeypatch.setattr("phoxtail.translations.compile.PACKAGES", tmp_path)

    with pytest.raises(ValueError, match="allauth/el.po corrects 'Cancel', which phoxtail writes itself"):
        combined("el")


def test_the_test_settings_put_the_translations_first():
    assert translations_first(None) == []


def test_a_project_without_the_app_is_told(monkeypatch):
    monkeypatch.setattr("phoxtail.translations.checks.apps.is_installed", lambda name: name != "phoxtail.translations")

    assert [warning.id for warning in translations_first(None)] == ["phoxtail_translations.W002"]


def _app(tmp_path, name, translated):
    path = tmp_path / name
    (path / "locale" if translated else path).mkdir(parents=True)
    return name.replace(".", "_"), name, str(path)


def test_an_app_with_translations_listed_first_is_named(tmp_path):
    installed = [
        _app(tmp_path, "wagtail.admin", True),
        _app(tmp_path, "modelcluster", False),
        ("phoxtail_translations", "phoxtail.translations", str(tmp_path)),
        _app(tmp_path, "allauth.account", True),
    ]

    assert listed_before(installed) == ["wagtail.admin"]


def test_nothing_is_named_when_the_app_is_not_installed(tmp_path):
    assert listed_before([_app(tmp_path, "wagtail.admin", True)]) == []


def test_corrections_in_a_language_without_a_list_stop_the_build(tmp_path, monkeypatch):
    (tmp_path / "allauth").mkdir()
    (tmp_path / "allauth" / "de.po").write_text('msgid "Sign In"\nmsgstr "Anmelden"\n', encoding="utf-8")
    monkeypatch.setattr("phoxtail.translations.compile.PACKAGES", tmp_path)
    # A list of its own in another language, so nothing real is written.
    (tmp_path / "locale" / "zz" / "LC_MESSAGES").mkdir(parents=True)
    (tmp_path / "locale" / "zz" / "LC_MESSAGES" / "django.po").write_text('msgid ""\nmsgstr ""\n', encoding="utf-8")
    monkeypatch.setattr("phoxtail.translations.compile.LOCALE", tmp_path / "locale")

    with pytest.raises(SystemExit, match="corrections in 'de' but no list of phoxtail's own sentences"):
        main()
