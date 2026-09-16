"""A root URLconf that mounts every phoxtail app the way a hatched project does.

Deliberately everything, not only the tokens app: what is under test is that
a project which only ever called ``collect_url_patterns()`` serves the
discovery document at its root, beside every other mount.
"""

from phoxtail.core.wiring import collect_url_patterns

urlpatterns = collect_url_patterns()
