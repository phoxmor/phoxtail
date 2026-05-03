from phoxtail.core.app_config import PhoxtailAppConfig, UrlMount


class PhoxtailCmsConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.cms"
    label = "phoxtail_cms"
    verbose_name = "Phoxtail CMS"

    url_mount = UrlMount(prefix="phoxtail_cms/", module="phoxtail.cms.urls")

    depends_on = [
        "phoxtail.design",
        "phoxtail.streams",
    ]

    page_schema_contributors = [
        "phoxtail.cms.api.v1.page_schemas.contribute_site_page",
    ]
