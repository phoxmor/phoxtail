"""Base AppConfig and helpers for autonomous phoxtail app wiring."""

from dataclasses import dataclass

from django.apps import AppConfig


@dataclass
class UrlMount:
    prefix: str
    module: str
    namespace: str | None = None
    # Mount under a language prefix (/en/dashboard/). Set it for anything a
    # person reads; leave it off for machine endpoints, whose callers would
    # have to learn a locale to reach them.
    i18n: bool = False


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

    # Neither surface is declared here. Subclassing this class is what makes
    # an app discoverable, and its two surfaces are then found by name:
    # <pkg>/api/ is mounted at /api/<label minus phoxtail_>/<version>/, and
    # every module in <pkg>/mcp/ is imported so its tools register. See
    # phoxtail.core.discovery.
    #
    # page_schema_contributors: dotted paths to zero-arg callables
    #   returning a phoxtail.cms.api.v1.contrib.PageSchemaContribution.
    #   Consumed by the pages domain to power /page-types/,
    #   GET /pages/{id}/ per-type fields, and PATCH validation.
    page_schema_contributors: list[str] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "default" not in cls.__dict__:
            cls.default = True
