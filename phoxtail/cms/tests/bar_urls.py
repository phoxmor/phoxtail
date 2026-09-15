"""URLconf for the phoxtail-bar tests.

The shared test settings point ``ROOT_URLCONF`` at ``phoxtail.core.urls``,
which mounts neither the agent views nor the dashboard. The bar reaches
both through ``{% url ... as %}``, which sets an empty string rather than
raising when a route is missing — so the media button is absent for every
user, whatever their permissions, and a test asserting it is withheld
would pass without the check existing.

Mounting them here is what makes the permission the reason.
"""

from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls

from phoxtail.agent import urls as agent_urls
from phoxtail.core import urls as core_urls

urlpatterns = [
    path("admin/", include(wagtailadmin_urls)),
    path("agent/", include(agent_urls)),
    path("", include(core_urls)),
    path("", include(wagtail_urls)),
]
