from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount


class AppAConfig(PhoxtailAppConfig):
    name = "phoxtail.core.tests.wiring_testapps.app_a"
    label = "wiring_testapp_a"

    url_mount = UrlMount(prefix="a/", module="phoxtail.core.tests.wiring_testapps.app_a.urls")
    context_processors = ["phoxtail.core.tests.wiring_testapps.app_a.ctx.proc_a"]
    middleware = ["phoxtail.core.tests.wiring_testapps.app_a.middleware.MiddlewareA"]
    default_settings = {
        "APP_A_SETTING": "a-default",
        "SHARED_SETTING": "from-a",
    }
