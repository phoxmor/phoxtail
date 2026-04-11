from phoxtail.core.app_config import PhoxtailAppConfig


class CycleAConfig(PhoxtailAppConfig):
    name = "phoxtail.core.tests.wiring_testapps.app_cycle_a"
    label = "wiring_testapp_cycle_a"

    depends_on = ["phoxtail.core.tests.wiring_testapps.app_cycle_b"]
