"""Settings for phoxtail's own test suite.

The shared base ships as :mod:`phoxtail.core.testing` so packages built
on phoxtail can use it too. This module adds only what is private to this
repository — a test app that exists to exercise the wiring and is not
distributed.
"""

from phoxtail.core.testing import *  # noqa: F401, F403

INSTALLED_APPS = [*INSTALLED_APPS, "phoxtail.core.tests.testapp"]  # noqa: F405
