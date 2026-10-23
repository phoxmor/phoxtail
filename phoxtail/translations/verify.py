"""Fail when ``make translations`` was forgotten, as ``makemigrations --check`` does.

Gathers phoxtail's sentences again in a copy of the package, so the real lists
are never written, and compares each language's sentences with the committed
list: a sentence new or gone in the code, or one left to translate, fails.
Where a sentence sits in the code (the ``#:`` lines) is not compared, so moving
code needs no new run. The arguments are makemessages', given by
``make translations-check`` so both targets gather alike.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from phoxtail.translations.compile import LOCALE, read, untranslated

PACKAGE = LOCALE.parents[1]


def sentences(path: Path) -> set[tuple]:
    return {(message.context, message.id) for message in read(path) if message.id}


def gather(arguments: list[str], copy: Path) -> None:
    """Run makemessages in a copy of the package, after checking the copy is what Python imports."""
    shutil.copytree(PACKAGE, copy / "phoxtail", ignore=shutil.ignore_patterns("__pycache__"))
    env = {**os.environ, "PYTHONPATH": str(copy)}
    found = subprocess.run(
        [sys.executable, "-c", "import phoxtail; print(phoxtail.__file__)"],
        cwd=copy / "phoxtail",
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not Path(found).is_relative_to(copy):
        raise SystemExit(f"the copy is not what Python imports ({found}): nothing gathered")
    subprocess.run(
        [sys.executable, "-m", "django", "makemessages", *arguments],
        cwd=copy / "phoxtail",
        env=env,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder)
        gather(sys.argv[1:], copy)
        failed = False
        for committed in sorted(LOCALE.glob("*/LC_MESSAGES/django.po")):
            gathered = copy / committed.relative_to(PACKAGE.parent)
            language = committed.parents[1].name
            new = sentences(gathered) - sentences(committed)
            gone = sentences(committed) - sentences(gathered)
            missing = untranslated(read(committed))
            for title, found in (("new", new), ("gone", gone)):
                for context, text in sorted(found, key=str):
                    print(f"{language}: {title} {text!r}" + (f" ({context})" if context else ""))
            for text in missing:
                print(f"{language}: to translate {text!r}")
            failed = failed or bool(new or gone or missing)
    print("run make translations, and translate what it names" if failed else "translations up to date")
    sys.exit(failed)


if __name__ == "__main__":
    main()
