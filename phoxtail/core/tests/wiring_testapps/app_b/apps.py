from phoxtail.core.app_config import PhoxtailAppConfig


class AppBConfig(PhoxtailAppConfig):
    name = "phoxtail.core.tests.wiring_testapps.app_b"
    label = "wiring_testapp_b"

    depends_on = ["phoxtail.core.tests.wiring_testapps.app_a"]
    context_processors = ["phoxtail.core.tests.wiring_testapps.app_b.ctx.proc_b"]
    default_settings = {
        "APP_B_SETTING": "b-default",
        "SHARED_SETTING": "from-b",
    }
