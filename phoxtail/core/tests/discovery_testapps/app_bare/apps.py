from phoxtail.core.app_config import PhoxtailAppConfig


class AppBareConfig(PhoxtailAppConfig):
    """A phoxtail app that ships neither surface — the ordinary case."""

    name = "phoxtail.core.tests.discovery_testapps.app_bare"
    label = "phoxtail_bare"
