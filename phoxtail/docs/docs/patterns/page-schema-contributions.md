# Page Schema Contributions

The pages domain (`phoxtail/api/pages/v1/`) exposes a generic Wagtail
surface: list, get, patch, publish, body editing. Those endpoints work
for any `Page` subclass. But a `BlogPostPage` has fields that a
`SitePage` doesn't — `intro`, `read_mins`, `author`, `tags` — and the
agent needs to know about them.

Page schema contributions are the mechanism by which each app teaches
the pages domain about its own `Page` subclasses, without the core
pages code knowing anything about blog, cms, or any future app.

---

## Why explicit, not introspective

A contribution is a hand-written declaration, not a reflection of
`_meta.get_fields()`. Each contributing app names its writable fields,
ships its own serializer, and ships its own patch handler.

This is the most important discipline in the design. Introspection
would produce:

- **Unpredictable writable surfaces.** ORM fields that should never be
  written via the API (internal flags, computed timestamps, FK ids that
  must be resolved through a lookup) would appear as writable.
- **Leaky coupling.** Core would need to understand field types,
  `editable=False`, `blank`, `null`, taggit managers, StreamField
  serialization — all app-specific concerns.
- **Silent agent errors.** An agent writing to a field that exists in
  the ORM but has no business being written would produce a corrupt
  revision with no error.

Explicitness means the contributing app makes these decisions once, in
one place, and core is never involved.

---

## The `PageSchemaContribution` dataclass

```python
# phoxtail/api/pages/v1/contrib.py

@dataclass(frozen=True)
class PageSchemaContribution:
    model: type[Page]
    content_type: str
    writable_fields: WritableFields
    serialize: Callable[[Page], dict]
    apply_patch: Callable[[Page, dict], None]
    fk_lookups: FkLookups = field(default_factory=dict)
```

### `model`

The concrete `Page` subclass this contribution describes. Used to
match a page instance to its contribution via `specific_class`.

### `content_type`

The `"{app_label}.{model_name}"` string (all lowercase, matching
Django's `ContentType` convention). Examples: `"phoxtail_blog.blogpostpage"`,
`"phoxtail_cms.sitepage"`. This is the key in the registry and the
value surfaced in API responses and the `phoxtail://page-types`
resource.

### `writable_fields`

A `dict[str, dict]` describing each field the agent may write via
`PATCH /api/pages/v1/pages/{id}/`. This is the JSON schema-ish
description returned by `GET /api/pages/v1/page-types/`. Keys are
field names; values are dicts with at minimum `{"type": <str>}`;
optional keys include `required`, `help_text`, `fk_model`.

Example:

```python
writable_fields = {
    "intro": {"type": "str", "required": False},
    "read_mins": {"type": "int", "required": False},
    "author": {
        "type": "fk",
        "fk_model": "phoxtail_blog.BlogAuthor",
        "required": False,
    },
    "tags": {"type": "list[str]", "required": False},
    "body": {"type": "streamfield", "required": False},
}
```

### `serialize`

```python
serialize: Callable[[Page], dict]
```

Called from `GET /api/pages/v1/pages/{id}/` when the page matches this
contribution. Returns a JSON-ready dict of per-type fields that is
merged into the base Wagtail page response. It receives the page
instance (already the specific subclass via `get_latest_revision_as_object()`
when a draft exists).

Contract:

- Return only the fields declared in `writable_fields` plus any
  read-only fields the app wants to expose (e.g. `tags` as a sorted
  list of strings).
- Return values must be JSON-serializable. FK fields should serialize
  to an integer ID (and optionally a `{id, title}` object).
- Do not raise; return `None` for a field that is unexpectedly absent.

### `apply_patch`

```python
apply_patch: Callable[[Page, dict], None]
```

Called from `PATCH /api/pages/v1/pages/{id}/` after common Wagtail
fields (title, slug, seo fields) have been applied. Receives the page
instance and a `data` dict containing only the keys the caller
supplied.

Contract:

- **Mutate the page instance in place.** Do not call `save()`,
  `save_revision()`, or `publish()`. The core endpoint handles
  persistence after all handlers run.
- **Ignore unknown keys silently.** A PATCH payload can freely mix
  common and per-type fields. Any key not recognised by this handler
  is simply skipped — no error, no warning.
- **Validate here, raise `HttpError` on bad input.** An unknown FK id,
  a string where an int is expected, or a structurally invalid tag list
  should raise `ninja.errors.HttpError(400, ...)` with a clear detail
  message. The core endpoint propagates this to the caller.
- **Do not assume the dict is complete.** `apply_patch` is called with
  only the keys the caller actually sent — treat it as a partial update.

Example (excerpt from `phoxtail/blog/api/v1/page_schemas.py`):

```python
def _apply_blog_post_patch(page: BlogPostPage, data: dict) -> None:
    if "intro" in data:
        page.intro = data["intro"]
    if "read_mins" in data:
        page.read_mins = data["read_mins"]
    if "tags" in data:
        _apply_tags(page, data["tags"])
    if "author" in data:
        page.author = _resolve_author(data["author"])
    if "hide_dates" in data:
        page.hide_dates = data["hide_dates"]
```

### `fk_lookups`

```python
fk_lookups: dict[str, str]
```

Maps a writable FK field name to the MCP tool name an agent should
call to resolve a human-readable title to an integer ID. This is pure
string metadata — the pages domain never imports or calls the named
tool. It surfaces via `GET /api/pages/v1/page-types/` so the agent
can discover the lookup without hardcoding it.

Example:

```python
fk_lookups = {
    "author": "phoxtail_blog_list_authors",
    "preview_image": "phoxtail_pages_list_images",
}
```

An agent reading `phoxtail://page-types` learns: "to set `author` on a
`BlogPostPage`, call `phoxtail_blog_list_authors` with a search term,
pick an id, then PATCH with `{"author": <id>}`."

---

## Declaring a contribution

Contributions are declared as zero-arg factory functions that return
a `PageSchemaContribution`. They live in the contributing app's
`phoxtail/<app>/api/v1/page_schemas.py` module (by convention) and
are wired via `page_schema_contributors` on the app's
`PhoxtailAppConfig`.

```python
# phoxtail/blog/api/v1/page_schemas.py

def contribute_blog_post() -> PageSchemaContribution:
    from phoxtail.blog.models import BlogPostPage

    return PageSchemaContribution(
        model=BlogPostPage,
        content_type="phoxtail_blog.blogpostpage",
        writable_fields={...},
        serialize=_serialize_blog_post,
        apply_patch=_apply_blog_post_patch,
        fk_lookups={
            "author": "phoxtail_blog_list_authors",
            "preview_image": "phoxtail_pages_list_images",
        },
    )
```

```python
# phoxtail/blog/apps.py

class PhoxtailBlogConfig(PhoxtailAppConfig):
    page_schema_contributors = [
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_post",
        "phoxtail.blog.api.v1.page_schemas.contribute_blog_index",
    ]
```

---

## The registry

`phoxtail.api.pages.v1.contrib.collect_page_schemas()` builds the
registry on first call by walking `apps.get_app_configs()`, finding
every `PhoxtailAppConfig` with `page_schema_contributors`, importing
each factory, and invoking it.

The result is cached in a module-level `_cache` dict keyed by
`content_type`. Subsequent calls return the same dict without
re-walking the app registry. This is safe in production (apps don't
change at runtime) and in tests when `reset_cache()` is called between
setups.

```python
from phoxtail.api.pages.v1.contrib import collect_page_schemas, reset_cache

schemas = collect_page_schemas()  # walks registry, caches
schemas = collect_page_schemas()  # returns cache immediately

reset_cache()                      # for tests: clears _cache
schemas = collect_page_schemas()  # re-walks
```

Two failure modes are detected at registry build time:

- **Duplicate `content_type`** — two contributions for the same model
  raise `RuntimeError`. This almost always indicates a copy-paste bug.
- **Wrong return type** — a factory that returns anything other than
  `PageSchemaContribution` raises `TypeError` immediately.

---

## What the agent sees

When all contributions are registered, the agent's workflow for
editing a `BlogPostPage` looks like this:

1. `GET phoxtail://page-types` — reads the registry. Learns that
   `phoxtail_blog.blogpostpage` has writable fields `intro`, `author`,
   `tags`, `body`, … and that `author` resolves via
   `phoxtail_blog_list_authors`.
2. `phoxtail_blog_list_authors(search="Alice")` → gets `{id: 3, title:
   "Alice Smith"}`.
3. `phoxtail_pages_get_page(id=42)` → gets the page with all fields
   including blog-specific ones, plus `_etag`.
4. `phoxtail_pages_update_page(id=42, etag="...", fields={"author": 3,
   "intro": "New intro", "tags": ["python", "django"]})` → core applies
   common fields, then calls `apply_patch(page, {"author": 3, "intro":
   "New intro", "tags": ["python", "django"]})`, then saves a draft
   revision.
5. `phoxtail_pages_publish(id=42, etag="...")` → publishes the draft.

The agent never needed to know it was talking to a `BlogPostPage`
specifically. The registry told it everything.

---

## Checklist for a new Page subclass

- [ ] Write `contribute_<model>()` in `phoxtail/<app>/api/v1/page_schemas.py`.
- [ ] List all and only the fields the agent should be able to write in
  `writable_fields`.
- [ ] Implement `serialize` — all writable fields plus useful read-only
  fields; JSON-safe values only.
- [ ] Implement `apply_patch` — ignore unknown keys, raise `HttpError(400)`
  on invalid values, never call `save()`.
- [ ] Declare `fk_lookups` for every FK field, naming the MCP tool
  that resolves titles to IDs.
- [ ] Add the dotted factory path to `page_schema_contributors` on the
  app's `PhoxtailAppConfig`.
- [ ] Verify with `GET /api/pages/v1/page-types/` that the new type
  appears with the expected fields and lookups.
