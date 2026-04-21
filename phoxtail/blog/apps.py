from phoxtail.core.app_config import PhoxtailAppConfig


class PhoxtailBlogConfig(PhoxtailAppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "phoxtail.blog"
    label = "phoxtail_blog"
    verbose_name = "Phoxtail Blog"

    # Blog contributes its own HTTP router and page-schema contributions.
    # MCP tools are registered via the ``phoxtail.mcp_modules`` entry
    # point in pyproject.toml; the module self-gates on
    # ``apps.is_installed("phoxtail.blog")`` so tools appear only when
    # the app is active in INSTALLED_APPS.
    api_version_router = "phoxtail.blog.api.v1.router"
    page_schema_contributors = [
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_post",
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_index",
    ]
