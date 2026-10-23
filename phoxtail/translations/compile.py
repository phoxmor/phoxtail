"""Compile each language's list of phoxtail's sentences with its corrections to other packages'.

Django reads one compiled list per language from an app, so the corrections,
written by hand in ``packages/<package>/<language>.po``, are compiled into the
same ``locale/<language>/LC_MESSAGES/django.mo`` as phoxtail's own sentences.
Django's ``compilemessages`` would leave them out. Run it with
``make translations``.
"""

from pathlib import Path

from babel.messages.catalog import Catalog
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po

ROOT = Path(__file__).parent
LOCALE = ROOT / "locale"
PACKAGES = ROOT / "packages"


def read(path: Path) -> Catalog:
    with path.open("rb") as file:
        return read_po(file)


def own(language: str) -> Path:
    """The list of phoxtail's own sentences in a language, which makemessages keeps."""
    return LOCALE / language / "LC_MESSAGES" / "django.po"


def corrections(language: str) -> list[tuple[str, Catalog]]:
    """Each package phoxtail corrects in a language, with its corrections."""
    return [(path.parent.name, read(path)) for path in sorted(PACKAGES.glob(f"*/{language}.po"))]


def combined(language: str) -> Catalog:
    """phoxtail's own sentences in a language, and its corrections to other packages'.

    A correction to a sentence phoxtail also writes itself is refused: both
    would be read from this one list, and one would silently lose.
    """
    catalog = read(own(language))
    for package, fixes in corrections(language):
        for message in fixes:
            if not message.id:
                continue
            if catalog.get(message.id, message.context) is not None:
                raise ValueError(
                    f"{package}/{language}.po corrects {message.id!r}, which phoxtail "
                    "writes itself: translate it in phoxtail's own list instead"
                )
            catalog[message.id] = message
    return catalog


def untranslated(catalog: Catalog) -> list[str]:
    """The sentences a list has no translation for yet, or only a guess (fuzzy)."""
    return [
        message.id if isinstance(message.id, str) else message.id[0]
        for message in catalog
        if message.id
        and (message.fuzzy or not all(message.string if isinstance(message.string, tuple) else [message.string]))
    ]


def languages() -> list[str]:
    """Every language phoxtail has a list for, or corrections in."""
    return sorted(
        {path.name for path in LOCALE.iterdir() if path.is_dir()} | {path.stem for path in PACKAGES.glob("*/*.po")}
    )


def main() -> None:
    for language in languages():
        if not own(language).is_file():
            raise SystemExit(
                f"there are corrections in {language!r} but no list of phoxtail's own sentences in it: "
                f"create {LOCALE / language} and run make translations again, which fills it"
            )
        catalog = combined(language)
        with own(language).with_suffix(".mo").open("wb") as file:
            write_mo(file, catalog)
        missing = untranslated(read(own(language)))
        print(f"{language}: {len(missing)} to translate" + "".join(f"\n  {text!r}" for text in missing))


if __name__ == "__main__":
    main()
