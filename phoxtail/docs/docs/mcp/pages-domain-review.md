# Pages Domain — Implementation Review

Critical analysis of the initial implementation of the pages domain
(see [Pages Domain](pages-domain.md) for the design spec). Ordered
by severity: bugs first, design drifts second, nits last.

> **Status legend:** ✅ resolved in code · 🧪 resolved in code, needs
> regression test (see [Pages Domain — Test Plan](pages-domain-tests.md))
> · ⏳ still open.

## Bugs

### 1. PATCH appears to succeed but subsequent GET shows stale scalars — ✅

`phoxtail/api/content/v1/pages.py:104-128` calls `page.save_revision(user=...)`
and returns the in-memory page, but never `page.save()`. Wagtail stores
the revision JSON separately; the live `wagtailcore_page` row still has
the old `title` / `slug` / contributed fields.

A fresh `GET /pages/{id}/` runs `resolve_page()` →
`Page.objects.get(pk=...).specific`, which reads the DB row and returns
the pre-PATCH values. The Wagtail pattern for surfacing draft state is
`page.get_latest_revision_as_object()` — not used anywhere.

As-is, MVP step 10 only works because publish happens first. Any
"PATCH then GET without publishing" is silently broken. The ETag
helper (`_helpers.py:28-47`) already acknowledges this by excluding
`title` / `slug` from the hash to avoid If-Match mismatches — papering
over the symptom rather than fixing the cause.

**Fix**: in `get_page` / `get_body`, when a later draft revision
exists, return `page.get_latest_revision_as_object()` instead of the
live row. Or do a direct `page.save()` of the common scalars alongside
`save_revision()`, accepting that core scalars go live immediately.

### 2. `mcp_modules` attribute is dead code — ✅

`PhoxtailAppConfig.mcp_modules` is declared (`core/app_config.py:56`)
and set by blog (`blog/apps.py:12`), but `phoxtail/mcp/__init__.py`
discovers tools exclusively via the `phoxtail.mcp_modules`
entry-point group (`pyproject.toml`). The AppConfig attribute is
never read.

A contributor who follows the AppConfig contract (per the spec, doc
line 67-69) gets zero tools registered. Pick one channel; remove the
other. The spec itself is internally inconsistent — line 67 describes
`mcp_modules` as an AppConfig list, line 199-201 describes entry-point
discovery.

### 3. Blog MCP tools register even when blog is not installed — ✅ (divergent fix)

Entry points fire for any installed *package*, not any entry in
`INSTALLED_APPS`. The phoxtail package itself declares
`phoxtail_blog = "phoxtail.blog.mcp"` in `pyproject.toml`, so
`phoxtail_blog_list_authors` is always registered.

In a hatched project without blog in `INSTALLED_APPS`, the tool still
appears in the MCP catalog and calls `/api/blog/v1/authors/` → 404.
The spec's claim (lines 69 and 212) that "apps absent from
`INSTALLED_APPS` are never imported" is false as implemented.

**Fix**: either move the entry point declaration to a per-app
`pyproject.toml` (only works once blog is a separable distribution),
or gate the import inside `phoxtail.blog.mcp` on
`apps.is_installed("phoxtail.blog")`.

> **⚠️ Divergence from the review's suggested fix — do not revert.**
> The applied fix gates on `phoxtail.cli.utils.config.get_project_apps()`
> (which reads `phoxtail.toml → [project].apps`), **not** on
> `django.apps.apps.is_installed(...)`. Reason: `phoxtail mcp serve`
> runs on the host, outside any Django process — there is no app
> registry to consult. The `phoxtail.toml` manifest is the host-side
> source of truth for which optional apps are active in the project.
> See `pages-domain.md` → "MCP tool registration" for the full
> rationale. A future agent who "fixes" this to `apps.is_installed`
> will break MCP on the host.

### 4. `page.tags.set(*names, clear=True)` signature risk — ✅

`blog/api/v1/page_schemas.py:72`. django-taggit 4.x changed
`TaggableManager.set` from `set(*tags, ...)` to `set(tags, ...)`
(positional list argument). Against taggit ≥ 4 this call will
TypeError. Pin the taggit version or update the call shape.

### 5. 5xx responses leak as exceptions to the agent — ✅

`_write_error_envelope` (`mcp/pages/pages.py:72`) handles 400 / 403 /
412 / 428 only. Anything else falls through to `resp.raise_for_status()`
and the MCP tool throws. The spec (line 506) promises structured JSON
for all non-2xx so the agent can reason about the failure.

### 6. `list_authors` OR-chain is messy — ✅ (Wagtail search backend)

`blog/api/v1/authors.py:41-52` does
`qs.filter(a) | qs.filter(b) | qs.filter(c) | qs.filter(d)` and then
`.distinct()`. Functionally OK, but each branch carries its own
`select_related("user")` join. A single
`.filter(Q(user__username__icontains=s) | Q(user__email__icontains=s) | ...)`
is cleaner and produces a tighter plan.

## Design drifts from the spec

### 7. `_mount_contributed_routers()` runs at module import — ✅

Called at the bottom of `phoxtail/api/__init__.py`. It depends on
`django_apps.get_app_configs()` being populated. In the production
path (Django loads `phoxtail.api.urls` after `apps.populate()`) this
works. But any earlier import — a management command, a settings
module that touches `phoxtail.api`, a test that imports the api
package directly — will run against an empty or half-populated
registry and either crash or register nothing.

**Fix**: call from an `AppConfig.ready()` hook, or lazy-mount on first
request. The spec (line 160) explicitly says "The mount happens after
`django.setup()`" — the current implementation depends on callers to
honor that indirectly.

### 8. `collect_contributed_routers()` function named in spec does not exist — ✅

Spec doc line 169-173 describes a function by that name; the logic is
inlined into `_mount_contributed_routers`. Minor doc drift — either
extract the helper or update the spec.

### 9. Body serialization duplicated in three places — ✅

`_helpers.serialize_body`, `blog/api/v1/page_schemas._body_as_json`,
and `cms/api/v1/page_schemas._serialize_site_page` all do the same
`stream_value.stream_block.get_api_representation(...)` dance. The
comment in blog's file ("scoped so contributions don't depend on the
helper's private API") is a self-imposed rule that just creates drift
risk. Promote `serialize_body` to public API and call it from the
contributors.

### 10. `PagePatch.model_dump(exclude_unset=True)` + `extra="allow"` — 🧪

In Pydantic v2, extras live in `__pydantic_extra__`. Whether
`exclude_unset=True` correctly surfaces them is version-sensitive and
there is no test asserting it. Add a unit test that a patch carrying
only a contributed field (e.g. `{"intro": "x"}`) survives through to
`apply_contributed_patch`.

### 11. `filter_by_content_type` inconsistency — ✅

`GET /pages/?type=phoxtail_blog.BlogPostPage` in a project without
blog installed returns 400 — the same status as a malformed string.
Consider 404 or an empty list for "not installed" vs 400 for
malformed.

### 12. No test suite — ⏳

The spec section 17 (doc line 510-529) lays out a full test tree in
`phoxtail/api/content/v1/tests/` and `phoxtail/blog/api/v1/tests/`.
None of it exists. The spec says "the MVP is not validated until the
tests pass against a real in-process database." Currently nothing
would catch bug #1.

## Nits — ✅ (all addressed)

- `_safe_full_url` (`_helpers.py:142`) swallows every `Exception` —
  narrow to the known Wagtail exceptions (`Http404`, site-config
  errors).
- `already_mounted = {"streams", "pages"}` in
  `phoxtail/api/__init__.py` is hardcoded. Easy to forget to update
  when a new core router is added above.
- `phoxtail/api/content/__init__.py` is empty (1 byte). Fine, but
  `phoxtail/mcp/pages/__init__.py` has a docstring explaining why it
  is empty — consistency would help.
- `PagePatch` uses `title: str | None = None` etc.; `apply_common_patch`
  then skips `None` values. A client sending `{"title": null}` to mean
  "clear the title" cannot — but `title` is non-nullable in Wagtail
  anyway, so this is fine. `search_description` and `seo_title` accept
  empty strings, which is the right "clear" affordance.

## Priority ranking

1. **Bug #1** — PATCH/GET draft visibility. This will surprise the
   agent mid-flow and is the most important correctness issue.
2. **Bugs #2 + #3** — reconcile `mcp_modules` vs entry points. Decide
   which is canonical, remove the other, and fix blog's "always on"
   registration.
3. **Bug #4** — verify taggit `.set()` against the pinned version.
4. **Drift #12** — add the MVP test scaffold so regressions have a
   net.
5. Everything else.
