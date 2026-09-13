"""Registry for per-page-type contributions from Phoxtail apps.

Apps that ship their own ``wagtail.models.Page`` subclasses list their
contributors in ``page_schemas`` in their ``<pkg>/api/`` package, beside the
``versions`` that declare their routers. Each contributor is a zero-arg
callable returning a :class:`PageSchemaContribution`. The pages domain calls
:func:`collect_page_schemas` at runtime to:

1. Enumerate the ``phoxtail://page-types`` discovery resource.
2. Serialize per-type fields inside ``GET /pages/{id}/``.
3. Apply per-type scalar writes inside ``PATCH /pages/{id}/``.

Contributions are **explicit**, not introspective. Contributors list
the writable fields by hand and ship their own ``serialize`` and
``apply_patch`` callables. This is the single discipline that keeps
the pages domain from leaking app-specific knowledge into core.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from wagtail.models import Page

WritableFields = dict[str, dict]
FkLookups = dict[str, str]


@dataclass(frozen=True)
class PageSchemaContribution:
    """A single app's declaration of how one Page subclass is exposed.

    Fields:
      ``model`` — the concrete ``Page`` subclass.
      ``content_type`` — the ``"{app_label}.{model}"`` string (lowercase
         model name, matching Django's ContentType convention).
      ``writable_fields`` — JSON-Schema-ish description returned by the
         ``phoxtail://page-types`` resource. Keys are field names; values
         are dicts with at minimum ``{"type": <str>}``; may include
         ``required``, ``help_text``, ``fk_model``, etc.
      ``serialize`` — ``serialize(page) -> dict`` producing the per-type
         extra fields merged into ``GET /pages/{id}/`` alongside the
         common Wagtail page fields.
      ``apply_patch`` — ``apply_patch(page, data)`` mutating the page
         instance in place (must NOT call ``save`` or ``save_revision``;
         the core endpoint handles persistence). Unknown keys in
         ``data`` should be ignored silently so that a PATCH payload
         can freely mix common + per-type fields.
      ``fk_lookups`` — maps a writable FK field to the MCP tool name an
         agent should call to resolve a name/title to the integer PK.
         Used purely as string metadata surfaced by
         ``phoxtail://page-types`` — core never imports the tool.
    """

    model: type[Page]
    content_type: str
    writable_fields: WritableFields
    serialize: Callable[[Page], dict]
    apply_patch: Callable[[Page, dict], None]
    fk_lookups: FkLookups = field(default_factory=dict)


# Lazy cache — rebuilt on demand rather than once per process so that
# test fixtures can stub contributions without monkeypatching dotted
# imports.
_cache: dict[str, PageSchemaContribution] | None = None


def collect_page_schemas() -> dict[str, PageSchemaContribution]:
    """Return a mapping of ``content_type`` → contribution.

    Walks the same ``<pkg>/api/`` packages discovery already mounts routers
    from, and reads ``page_schemas`` off each. The contributors are ordinary
    imports there, so a renamed factory is an ImportError at startup rather
    than a surface that quietly goes missing.

    Duplicates — two apps contributing the same ``content_type`` — raise
    ``RuntimeError``, which almost certainly indicates a copy-paste bug rather
    than a legitimate override.

    One consequence worth knowing: the contributors are imported when the
    ``api`` package is, which is at ``django.setup()`` rather than on the first
    call here. Every app that ships page schemas ships a router too, so those
    modules were already loading then; an app that ships schemas and no router
    would newly pay that cost at startup.
    """
    global _cache
    if _cache is not None:
        return _cache

    from phoxtail.core.discovery import discover

    result: dict[str, PageSchemaContribution] = {}
    for name, module in discover("api"):
        for factory in getattr(module, "page_schemas", ()):
            contribution = factory()
            if not isinstance(contribution, PageSchemaContribution):
                raise TypeError(
                    f"{name}: {factory.__name__} must return a PageSchemaContribution, "
                    f"got {type(contribution).__name__}"
                )
            if contribution.content_type in result:
                raise RuntimeError(
                    f"Duplicate page_schema contribution for "
                    f"'{contribution.content_type}': already provided by "
                    f"another app."
                )
            result[contribution.content_type] = contribution

    _cache = result
    return result


def get_contribution_for_page(page: Page) -> PageSchemaContribution | None:
    """Look up the contribution for a concrete page instance.

    Returns None when the page's specific class has no registered
    contribution. Callers treat that as "only common fields are
    exposed" rather than as an error — an app may ship a Page subclass
    without any per-type writable fields.
    """
    schemas = collect_page_schemas()
    ct = _content_type_for(page.specific_class or type(page))
    return schemas.get(ct)


def reset_cache() -> None:
    """Drop the cached contribution map. For tests + MCP reloads."""
    global _cache
    _cache = None


def _content_type_for(page_cls: type[Page]) -> str:
    return f"{page_cls._meta.app_label}.{page_cls._meta.model_name}"
