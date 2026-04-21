"""Base AppConfig and helpers for autonomous phoxtail app wiring."""

from dataclasses import dataclass

from django.apps import AppConfig


@dataclass
class UrlMount:
    prefix: str
    module: str
    namespace: str | None = None


class PhoxtailAppConfig(AppConfig):
    """Base AppConfig for phoxtail apps that participate in autonomous wiring.

    Subclasses declare their integration requirements as class attributes.
    The project template's settings and urls modules read these at load time
    and auto-wire them. All fields are optional — an app that sets none of
    them is still a valid PhoxtailAppConfig.
    """

    # Django's AppConfig.create() scans apps.py with inspect.getmembers and
    # treats every AppConfig subclass it finds as a candidate. Because concrete
    # configs import PhoxtailAppConfig into their apps.py module, that import
    # is itself a candidate. Marking the base with default = False excludes it,
    # and __init_subclass__ restores default = True on concrete subclasses so
    # Django picks them unambiguously.
    default = False

    depends_on: list[str] = []
    url_mount: UrlMount | None = None
    context_processors: list[str] = []
    middleware: list[str] = []
    default_settings: dict = {}
    requires_celery: bool = False
    requirements: list[str] = []

    # API + pages-domain contribution hooks. All optional.
    #
    # api_version_router: dotted path to a ninja.Router. Mounted by
    #   phoxtail.api at /api/<short_label>/v1/, where
    #   short_label = self.label.removeprefix("phoxtail_").
    #
    # page_schema_contributors: dotted paths to zero-arg callables
    #   returning a phoxtail.api.pages.v1.contrib.PageSchemaContribution.
    #   Consumed by the pages domain to power /page-types/,
    #   GET /pages/{id}/ per-type fields, and PATCH validation.
    #
    # MCP tool modules are NOT declared here — they are discovered via
    # the ``phoxtail.mcp_modules`` Python entry-point group declared in
    # the distributing package's ``pyproject.toml``. See
    # ``phoxtail/docs/docs/mcp/pages-domain.md`` ("MCP registration")
    # for the full rationale.
    api_version_router: str | None = None
    page_schema_contributors: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "default" not in cls.__dict__:
            cls.default = True
