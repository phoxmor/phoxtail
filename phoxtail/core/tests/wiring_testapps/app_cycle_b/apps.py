from phoxtail.core.app_config import PhoxtailAppConfig


class CycleBConfig(PhoxtailAppConfig):
    name = "phoxtail.core.tests.wiring_testapps.app_cycle_b"
    label = "wiring_testapp_cycle_b"

    depends_on = ["phoxtail.core.tests.wiring_testapps.app_cycle_a"]
