"""Settings for gathering phoxtail's sentences: the test settings, plus where they go.

makemessages writes the sentences of every app without its own locale folder
into the first LOCALE_PATHS entry, so all of phoxtail's land in this app's list.
"""

from pathlib import Path

from phoxtail.core.tests.settings import *  # noqa: F401, F403

LOCALE_PATHS = [Path(__file__).resolve().parents[1] / "locale"]
