# Pages Domain — Test Plan (brief for the implementing agent)

**Read this whole document first.** The previous version of this brief
was scoped to 12 regression tests pinned against a presumed test
harness. That harness does not exist, and the owner has since broadened
scope to "a full test suite for the pages domain, not just the 12
rows." This rewrite captures both the missing harness *and* the wider
coverage the owner now expects.

Your deliverable is:

1. A working Django+Wagtail+Ninja+PAT integration-test harness covering
   the pages domain, the blog contribution, and the pages MCP layer.
2. A comprehensive pytest suite for everything under
   `phoxtail/api/content/v1/`, `phoxtail/blog/api/v1/`,
   `phoxtail/blog/mcp/`, `phoxtail/mcp/pages/`, and the contributed-router
   mount logic in `phoxtail/api/__init__.py` + `phoxtail/core/apps.py`.
3. Updates to `pages-domain-review.md` flipping drift #10 and #12 to ✅.

Write tests against the real ORM and real Wagtail APIs (see
[§0 Non-negotiables](#0-non-negotiables)). No `unittest.mock` on the
ORM, no `MagicMock()` standing in for a `Page`.

---

## 0. Non-negotiables

- **Real DB, real Wagtail.** Use `pytest-django`'s `db` /
  `transactional_db` fixtures, `Page.add_child(instance=...)`,
  `save_revision()`, `publish()`. If a test feels like it needs
  `mock.patch` on `Page.objects.*`, the test is wrong — write it at a
  higher level.
- **Do not revert the `get_project_apps()` gate to
  `apps.is_installed(...)`.** That gate lives in
  `phoxtail/blog/mcp/__init__.py:31` and protects MCP tool registration
  on the *host* venv where Django isn't bootstrapped. Reverting breaks
  `phoxtail mcp serve`. See `pages-domain.md` → "MCP registration" for
  the rationale; see `pages-domain-review.md` → Bug #3 for the
  ⚠️ Divergence callout.
- **Test the code as it is, not the brief.** If anything here disagrees
  with what you read in the source, update *this doc* in the same PR.

---

## 1. Orientation — read before writing any test

Run these once, in order:

1. `pages-domain.md` (sibling) — end to end. Pay attention to §17
   (Test plan), the MCP-registration section, ETag/revision semantics.
2. `pages-domain-review.md` (sibling) — every ✅ is a fix you are
   pinning; every 🧪 is a path whose only validation *is* the test you
   are about to write.
3. `git log -p --since="2 weeks ago" -- phoxtail/api/pages
   phoxtail/blog phoxtail/cms phoxtail/mcp/pages phoxtail/api
   phoxtail/core` — ground truth for what changed.
4. This file.

There is **no** `phoxtail/api/streams/v1/tests/` directory (the prior
version of this brief told you to copy from it; ignore that). The
closest house patterns that actually exist:

- `phoxtail/tokens/tests/test_ninja.py` — how `PhoxtailTokenAuth` is
  exercised; pairs with a project-wide `access_token` fixture in
  `phoxtail/tokens/tests/conftest.py`. Grep for it; reuse it verbatim
  for the PAT.
- `phoxtail/streams/tests/` — real Wagtail/DB fixtures for StreamField
  content.
- `phoxtail/booking/reservations/tests/conftest.py` — how the codebase
  structures a per-package conftest on top of real fixtures.

---

## 2. State of the harness — what you are standing up

The pages API is production-grade but **the test harness for it does
not exist yet**. You will build it. Concretely:

### 2.1 `phoxtail/core/tests/settings.py` (the `DJANGO_SETTINGS_MODULE`)

Currently missing, needed for these tests:

- `phoxtail.cms`, `phoxtail.blog`, `phoxtail.api`, `phoxtail.tokens`,
  `phoxtail.users` in `INSTALLED_APPS`.
- `wagtail.documents`, `wagtail.embeds`, `wagtail.snippets` (blog uses
  `register_snippet`), `wagtail.contrib.routable_page` if any Wagtail
  page depends on it (check), and any other Wagtail contrib apps that
  migrations in `phoxtail.cms.migrations` / `phoxtail.blog.migrations`
  assume.
- A `ROOT_URLCONF` that mounts `phoxtail.api.api.urls` (the shared
  `NinjaAPI`) at `/api/`. A tiny `phoxtail/core/tests/urls.py` that
  does `urlpatterns = [path("api/", api.urls)]` is enough.
- `WAGTAIL_SITE_NAME`, `WAGTAILADMIN_BASE_URL` (already present), and
  `WAGTAILSEARCH_BACKENDS` pointing at
  `wagtail.search.backends.database` so `blog/api/v1/authors.py`'s
  `backend.autocomplete(...)` works without Elasticsearch.

Do not remove apps that are there; only add. Verify `pytest
phoxtail/core/tests` still passes after your changes.

### 2.2 `pyproject.toml` — `[tool.pytest.ini_options].testpaths`

Currently excludes every path we are writing to. Add:

```
phoxtail/api/content/v1/tests
phoxtail/api/tests
phoxtail/blog/api/v1/tests
phoxtail/blog/mcp/tests
phoxtail/cms/api/v1/tests
phoxtail/mcp/pages/tests
```

Don't prune existing entries.

### 2.3 A root-ish `conftest.py` for the pages+blog+mcp tree

Put shared fixtures somewhere they are discoverable by all six test
directories above. Options: a new
`phoxtail/api/conftest.py` (pytest walks up), or duplicate-and-import.
Pick the least-surprising option and document it in a one-line
docstring at the top of the conftest.

Required fixtures (names are load-bearing — tests in §4 reference
them):

| Fixture | Scope | Notes |
|---|---|---|
| `pat_user` | `function` | Django user with `wagtail_admin` access + publish/edit perms on the test root page. Must be a `User`, not a `Superuser`, so 403 tests can flip permissions meaningfully. |
| `access_token` | `function` | PAT via `phoxtail.tokens` helpers (reuse the existing `access_token` fixture from `phoxtail/tokens/tests/conftest.py` if possible — it exposes `._raw_token`). Bind to `pat_user`. |
| `api_client` | `function` | `django.test.Client` pre-authenticated via `HTTP_AUTHORIZATION=f"Bearer {access_token._raw_token}"`. Expose helpers `get(path, **headers)`, `patch_json(path, data, etag=None)`, `put_json`, `post`. |
| `blog_index` | `function` | A published `BlogIndexPage` under the Wagtail root. `BlogPostPage.parent_page_types = ["phoxtail_blog.BlogIndexPage"]`, so blog posts **must** live under this. |
| `site_parent` | `function` | A published parent page that accepts `SitePage` children. `SitePage` has no restrictive `parent_page_types`, so the Wagtail root page works; document whatever you pick. |
| `blog_post` | `function` | A published `BlogPostPage` under `blog_index` with a non-empty body (≥ 1 block of a real variant) and at least one tag. |
| `site_page` | `function` | A published `SitePage` under `site_parent` with a non-empty body. |
| `blog_author` | `function` | A `BlogAuthor` snippet with a real `User`; use a `factory` or explicit `.objects.create()` — no FK-skipping hacks. |

Scope rule: mark tests that call `publish()` with
`@pytest.mark.django_db(transaction=True)` (Wagtail's publish path
fires post-save signals that misbehave inside nested SAVEPOINTs);
plain `django_db` is fine for everything else. Apply the same rule to
fixtures that publish.

### 2.4 `phoxtail.toml` on disk

The blog MCP gate calls `get_project_apps()` → reads
`phoxtail.toml → [project].apps`. Tests that exercise the gate
(§4.10) monkeypatch `phoxtail.cli.utils.config.get_project_apps` —
they must **not** rely on a real `phoxtail.toml` being present. If the
existing CLI-test conftest already creates one via the autouse
`project_dir` fixture, make sure the pages tests do not inherit it
unexpectedly.

---

## 3. Implementation map — what you are testing

A one-screen cheat sheet so you aren't hopping files while writing
assertions.

### 3.1 Core pages API — `phoxtail/api/content/v1/`

| File | Surface |
|---|---|
| `pages.py` | `GET /pages/` (list, filters: `type` `parent` `live`), `GET /pages/{id}/`, `PATCH /pages/{id}/` (draft revision), `POST /pages/{id}/publish/`, `POST /pages/{id}/unpublish/`. All writes require `If-Match`. |
| `body.py` | `GET /pages/{id}/body/`, `PUT /pages/{id}/body/` (draft revision, `If-Match` required). |
| `media.py` | `GET /media/images/` `GET /media/documents/` — search by title, pagination. |
| `page_types.py` | `GET /page-types/` — returns `{"types": {content_type: {content_type, writable_fields, fk_lookups}}}`. |
| `contrib.py` | `PageSchemaContribution` dataclass + `collect_page_schemas()` with an **in-module `_cache`** (`reset_cache()` exposed for tests). Duplicate `content_type` → `RuntimeError`. Factory returning non-`PageSchemaContribution` → `TypeError`. |
| `schemas.py` | `PagePatch` has `model_config = {"extra": "allow"}` — Pydantic v2 extras. `PageDetail = dict[str, Any]`. |
| `_helpers.py` | `page_etag()` (weak, `pk + latest_revision_created_at + last_published_at + live`), `resolve_page()` / `resolve_page_for_read()` (the latter returns `get_latest_revision_as_object()` when a draft exists — this is the **Bug #1 fix**), `require_edit_permission`, `require_publish_permission`, `require_if_match`, `filter_by_content_type` (400 for malformed, 404 for "well-formed but unknown"), `serialize_body`, `replace_body`. |

### 3.2 Contributed routers — `phoxtail/api/__init__.py` + `phoxtail/core/apps.py`

- Core short labels: `_CORE_SHORT_LABELS = frozenset({"streams", "pages"})`.
- `collect_contributed_routers()` yields `(short_label, router)` for
  every `PhoxtailAppConfig` with a non-null `api_version_router`,
  stripping the `phoxtail_` prefix. Raises `RuntimeError` on core-label
  collision and on duplicate short labels.
- `mount_contributed_routers()` is idempotent: uses a **module-level**
  `_contributed_mounted: bool` flag. Tests that want to re-run it must
  reset that flag.
- `PhoxtailCoreConfig.ready()` calls `mount_contributed_routers()`;
  already-fired once by the time tests start.

### 3.3 Page-schema contributions

- `phoxtail.cms.api.v1.page_schemas.contribute_site_page()` →
  `content_type="phoxtail_cms.sitepage"`, `writable_fields` just
  `body`.
- `phoxtail.blog.api.v1.page_schemas.contribute_blog_post()` →
  `content_type="phoxtail_blog.blogpostpage"`, writable fields
  `intro, read_mins, author, preview_image, tags, hide_dates,
  first_published_at_override, last_published_at_override, body`.
  `fk_lookups = {"author": "phoxtail_blog_list_authors",
  "preview_image": "phoxtail_pages_list_images"}`.
  - `_apply_tags(page, names)` → `page.tags.set(names, clear=True)`
    (django-taggit ≥ 4 signature).
  - `_resolve_author(value)` → 400 `HttpError` on unknown id / bad
    shape.
- `phoxtail.blog.api.v1.page_schemas.contribute_blog_index()` →
  `content_type="phoxtail_blog.blogindexpage"`, writable fields
  `posts_per_page, body`.

### 3.4 Blog API — `phoxtail/blog/api/v1/`

- Single router mounted at `/api/blog/v1/` via
  `PhoxtailBlogConfig.api_version_router =
  "phoxtail.blog.api.v1.router"`.
- `authors.py` → `GET /authors/` with `search` (Wagtail
  `backend.autocomplete`), `limit`, `offset`. Returns
  `{items: [{id, title}], total}`.

### 3.5 Core pages MCP — `phoxtail/mcp/pages/`

- `pages.py`, `body.py`, `media.py`, `resources.py`. All use
  `bind_prefix("/api/pages/v1")` from `phoxtail/mcp/_http.py`.
- `pages.py:_write_error_envelope(resp)` is the shared helper used
  across every tool; returns either `None` (2xx) or a JSON string
  `'{"error": <label>, "status": <int>, "detail": <str>}'`. Error
  labels: 400→`validation_error`, 403→`permission_denied`,
  404→`not_found`, 409→`conflict`, 412→`precondition_failed`,
  428→`precondition_required`, **everything else →`http_error`**
  (the Bug #5 fix — 5xx no longer leaks as an exception).
- `resources.py` registers the `phoxtail://page-types` MCP resource.

### 3.6 Blog MCP — `phoxtail/blog/mcp/`

- `__init__.py` gates submodule import on `"phoxtail.blog" in
  get_project_apps()` (host-side, not Django). This is the
  **Bug #3 fix** — do not revert.
- `authors.py` registers `phoxtail_blog_list_authors`.

---

## 4. Test matrix — minimum coverage

Write each test below. Rows marked **[MUST]** are the regression pins
from the original brief; **[ADD]** are new coverage the owner has now
asked for. Filenames are load-bearing; test-function names are
suggestions.

### 4.1 `phoxtail/api/content/v1/tests/test_pages.py`

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_patch_then_get_returns_draft_title_without_publish` | After `PATCH /pages/{id}/ {"title":"Draft"}` the next `GET` returns `title=="Draft"`; `live` unchanged. Pins Bug #1. |
| [MUST] | `test_etag_from_patch_matches_subsequent_get` | `PATCH` response `ETag` == next `GET` `ETag`. Pins Bug #1 ETag. |
| [MUST] | `test_type_filter_status_codes` | `?type=bogus_string` → 400; `?type=unknown_app.UnknownModel` → 404; `?type=wagtailcore.page` → 200. |
| [ADD] | `test_list_filters_by_parent_and_live` | `?parent={blog_index.pk}` returns only children; `?live=false` returns only drafts. |
| [ADD] | `test_list_pagination_limit_offset` | `limit=1`, `offset=1` returns 1 item at offset 1; `total` always reflects unpaginated count. |
| [ADD] | `test_list_content_type_downcasts_to_specific` | Response entries for blog posts carry `content_type=="phoxtail_blog.blogpostpage"`, not `"wagtailcore.page"`. |
| [ADD] | `test_get_404_for_missing_page` | `GET /pages/999999/` → 404, envelope shape `{detail: ...}`. |
| [ADD] | `test_patch_requires_if_match` | `PATCH` without `If-Match` → 428. |
| [ADD] | `test_patch_stale_if_match` | `PATCH` with stale ETag → 412. |
| [ADD] | `test_patch_403_for_user_without_edit_perm` | A user with no page perms → 403. |
| [ADD] | `test_patch_accepts_common_and_contributed_fields_together` | `PATCH` with `{"title":"X","intro":"Y"}` on a `BlogPostPage` lands both in the draft revision. |
| [ADD] | `test_publish_goes_live_and_updates_url` | Draft → `POST /publish/` → `live=true`, `url` non-null, new `ETag`. |
| [ADD] | `test_publish_409_when_no_revision_yet` | Bootstrapped page with no `save_revision()` → 409. |
| [ADD] | `test_unpublish_returns_200_and_drops_live` | `POST /unpublish/` → `live=false`. |
| [ADD] | `test_get_page_url_is_null_for_never_published` | Fresh draft has `url=None`. |

### 4.2 `phoxtail/api/content/v1/tests/test_body.py`

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_put_body_then_get_body_returns_new_value_without_publish` | `PUT` then `GET` round-trips without publish; pins Bug #1 body variant. |
| [ADD] | `test_body_etag_equals_page_etag` | `GET /pages/{id}/body/` ETag == `GET /pages/{id}/` ETag. |
| [ADD] | `test_put_body_requires_if_match_and_412_on_stale` | 428 missing, 412 stale. |
| [ADD] | `test_put_body_round_trips_stream_format` | `[{"type":"navbar","value":{"variant":<real_id>}}]` → GET returns equivalent list (with server-assigned `id` UUIDs). |
| [ADD] | `test_put_body_400_on_unknown_field` | Payload `{"notbody": ...}` → 400 (Pydantic). |
| [ADD] | `test_put_body_403_for_user_without_edit_perm` | 403 when user lacks edit perm. |

### 4.3 `phoxtail/api/content/v1/tests/test_contrib.py`

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_patch_with_only_contributed_field_reaches_apply_patch` | Unit: `PagePatch(intro="x").model_dump(exclude_unset=True)` contains `"intro"`. End-to-end: `PATCH` on `blog_post` with `{"intro":"x"}` produces a revision whose `intro` is `"x"`. Pins drift #10. |
| [MUST] | `test_duplicate_contribution_raises` | Two contributions with same `content_type` → `RuntimeError` from `collect_page_schemas()`. Use `reset_cache()` between setups. |
| [ADD] | `test_contribution_must_return_correct_type` | Factory returning a non-`PageSchemaContribution` → `TypeError`. |
| [ADD] | `test_reset_cache_allows_rebuild` | After `reset_cache()`, a second call re-walks the registry (verify by mutating a fake contributor). |
| [ADD] | `test_get_contribution_for_page_specific_subclass` | Pass a generic `Page` row that happens to be a `BlogPostPage` → returns blog post contribution, not the base. |
| [ADD] | `test_apply_patch_ignores_unknown_keys` | `apply_contributed_patch(page, {"nonsense": 1})` is a no-op, no exception. |

### 4.4 `phoxtail/api/content/v1/tests/test_page_types.py`

| Kind | Test | Asserts |
|---|---|---|
| [ADD] | `test_page_types_endpoint_lists_installed_contributions` | `GET /api/content/v1/page-types/` → `types` contains `phoxtail_cms.sitepage` and, because blog is in `INSTALLED_APPS` for tests, `phoxtail_blog.blogpostpage` and `phoxtail_blog.blogindexpage`. |
| [ADD] | `test_page_types_includes_fk_lookups_for_blog_post` | `types["phoxtail_blog.blogpostpage"].fk_lookups["author"] == "phoxtail_blog_list_authors"`. |
| [ADD] | `test_page_types_writable_fields_match_contribution` | Spot-check `intro`, `read_mins`, `body`. |

### 4.5 `phoxtail/api/content/v1/tests/test_media.py`

| Kind | Test | Asserts |
|---|---|---|
| [ADD] | `test_list_images_empty` | Zero images → `{items: [], total: 0}`. |
| [ADD] | `test_list_images_search_filter` | Two real `Image` rows with titles `"alpha"`, `"beta"`; `?search=alp` → only alpha. |
| [ADD] | `test_list_images_pagination` | `limit=1 offset=1` behavior. |
| [ADD] | `test_list_documents_smoke` | Same for `wagtail.documents` model. |

### 4.6 `phoxtail/api/tests/test_api_mount.py`

Be careful: `mount_contributed_routers()` uses a **module-level flag**
(`phoxtail.api._contributed_mounted`). Reset it explicitly in a fixture
before each test that calls `mount_contributed_routers()`. Also reset
`api._routers` / `api.urls_namespace` if you assert against the live
`NinjaAPI` — prefer calling `collect_contributed_routers()` on
hand-built fakes instead.

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_collect_contributed_routers_rejects_core_short_labels` | Build a fake `PhoxtailAppConfig` subclass with `label="phoxtail_pages"` and a dummy router; assert `RuntimeError`. |
| [MUST] | `test_collect_contributed_routers_rejects_duplicate_short_labels` | Two fake configs with label `phoxtail_foo` each → `RuntimeError`. |
| [MUST] | `test_mount_contributed_routers_is_idempotent` | Snapshot `api._routers` length, call `mount_contributed_routers()` twice, assert length unchanged. |
| [ADD] | `test_short_label_strips_phoxtail_prefix` | Config with `label="phoxtail_booking_reservations"` mounts at `/booking_reservations/v1/`. |
| [ADD] | `test_short_label_verbatim_for_non_phoxtail` | Config with `label="foo"` mounts at `/foo/v1/`. |
| [ADD] | `test_ready_mount_invoked_once_on_startup` | After full Django setup, `phoxtail.api._contributed_mounted is True`. |

### 4.7 `phoxtail/blog/api/v1/tests/test_page_schemas.py`

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_tags_set_replaces_tag_set` | `BlogPostPage` starts with tags `{"a","b"}`; `PATCH {"tags":["c"]}` + publish → `page.tags.names() == ["c"]` (sorted), no `TypeError`. |
| [ADD] | `test_tags_empty_list_clears` | `PATCH {"tags": []}` removes all tags. |
| [ADD] | `test_patch_author_by_id_resolves_to_fk` | `PATCH {"author": <blog_author.pk>}` → `page.author == blog_author` after `save_revision` + publish. |
| [ADD] | `test_patch_author_unknown_id_returns_400` | Unknown author id → 400 with `detail` mentioning the id. |
| [ADD] | `test_patch_preview_image_sets_fk_id` | `PATCH {"preview_image": <image.pk>}` round-trips via `preview_image_id`. |
| [ADD] | `test_patch_read_mins_and_hide_dates` | Scalars land on the revision. |
| [ADD] | `test_serialize_blog_post_shape` | Round-trip the whole `_serialize_blog_post` dict from `GET /pages/{id}/`: intro, read_mins, author, preview_image, tags (sorted), hide_dates, overrides, body. |
| [ADD] | `test_serialize_blog_index_shape` | `posts_per_page`, `body` present on `BlogIndexPage` response. |

### 4.8 `phoxtail/blog/api/v1/tests/test_authors.py`

| Kind | Test | Asserts |
|---|---|---|
| [ADD] | `test_list_authors_empty` | Zero authors → `{items: [], total: 0}`. |
| [ADD] | `test_list_authors_ordered_by_username` | Three authors with predictable usernames; ordering matches `user__username`. |
| [ADD] | `test_list_authors_search_autocomplete_smoke` | Insert authors, call `?search=<prefix>`; assert the search backend is the in-memory database backend and the match surfaces. |
| [ADD] | `test_list_authors_pagination` | `limit=1 offset=1` behavior. |
| [ADD] | `test_list_authors_title_is_author_str` | `item.title == str(author)` (full name or username fallback). |

### 4.9 `phoxtail/cms/api/v1/tests/test_site_page_contrib.py`

| Kind | Test | Asserts |
|---|---|---|
| [ADD] | `test_site_page_contribution_writable_fields_has_body_only` | `contribute_site_page().writable_fields == {"body": ...}`. |
| [ADD] | `test_site_page_apply_patch_is_noop_for_scalars` | `_apply_site_page_patch(page, {"title": "X"})` does not mutate `title` (common patch handles that). |
| [ADD] | `test_site_page_get_detail_includes_body` | `GET /pages/{site_page.pk}/` response dict carries `body` as a list. |

### 4.10 `phoxtail/blog/mcp/tests/test_blog_mcp_gate.py`

Critical pattern: the gate is evaluated at module-import time. To
re-test, you must drop `phoxtail.blog.mcp` **and** `phoxtail.blog.mcp.authors`
from `sys.modules`, monkeypatch
`phoxtail.cli.utils.config.get_project_apps`, then re-import.

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_blog_mcp_submodules_not_imported_when_blog_absent` | With `get_project_apps()` returning `("phoxtail.cms",)`, re-import `phoxtail.blog.mcp`; `"phoxtail.blog.mcp.authors" not in sys.modules`. Flip to include `"phoxtail.blog"`; re-import; assert present. |
| [ADD] | `test_gate_reads_get_project_apps_not_django_apps` | Monkeypatch `django.apps.apps.is_installed` to raise; re-import `phoxtail.blog.mcp` under the "blog present" gate; import must still succeed. (Proves the host-side gate is not secretly touching Django.) |
| [ADD] | `test_tool_list_authors_registered_after_gate_opens` | After a re-import with blog present, `phoxtail_blog_list_authors` appears on the shared `mcp_server` tool list; after a re-import without blog and a FastMCP server reset, it does not. (If FastMCP doesn't support unregistration, document the limitation and collapse this into the first row.) |

### 4.11 `phoxtail/mcp/pages/tests/test_pages_mcp.py`

The MCP tools hit HTTP via `phoxtail.mcp._http.request`, which reads
`api_base_url()` from `phoxtail.cli.utils.config.get_api_base_url`.
Point it at the Django test server. Options:

- (Preferred) Use `pytest-httpx` to stub HTTP responses and assert on
  the request shape + envelope output. Real DB not needed for this
  file; it's testing the MCP→HTTP translation layer.
- (Alternate) Run a live `LiveServerTestCase`-style server and let the
  tool call it end-to-end. Slower but end-to-end truth.

Document which you chose in the file docstring. Prefer `pytest-httpx`
for speed; reserve the live-server path for §4.12 if at all.

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_error_envelope_covers_404_409_500` | Stub responses at 404/409/500; each tool returns a JSON string parseable into `{"error": <label>, "status": <int>, "detail": <str>}`; **no exception raised**. Pins Bug #5. |
| [ADD] | `test_error_envelope_422_falls_back_to_http_error_label` | 422 → label `"http_error"`, `status == 422`. |
| [ADD] | `test_error_envelope_detail_from_body_when_json` | Response body `{"detail":"bad"}` surfaces in envelope. |
| [ADD] | `test_error_envelope_detail_fallback_when_not_json` | Plaintext body → falls back to the hint string. |
| [ADD] | `test_get_page_attaches_etag_as__etag` | 200 with `ETag: W/"abc"` → returned JSON has `_etag == 'W/"abc"'`. |
| [ADD] | `test_update_page_sends_if_match_header` | `update_page(id, etag="W/\"x\"", fields={...})` sends `If-Match: W/"x"`. |
| [ADD] | `test_replace_body_wraps_body_payload` | `replace_body(id, etag, [blocks])` PUTs `{"body": [blocks]}`, not `[blocks]` directly. |
| [ADD] | `test_bind_prefix_keeps_full_path` | `_http.url("/api/streams/v1/x/")` returns `"{base}/api/streams/v1/x/"` — no double prefix. (Regression against the old `API_PREFIX` constant.) |

### 4.12 `phoxtail/mcp/pages/tests/test_page_types.py`

| Kind | Test | Asserts |
|---|---|---|
| [MUST] | `test_page_types_resource_omits_blog_when_absent` | With `get_project_apps()` patched to return no blog, the `phoxtail://page-types` resource payload contains `phoxtail_cms.sitepage` but not `phoxtail_blog.*`. Pins Bug #3 symmetry. Note: the resource fetches `/api/content/v1/page-types/` — symmetry means the *server* registry must also not carry blog. In the test environment blog IS installed, so you'll need to either (a) stub the HTTP response, or (b) monkeypatch `collect_page_schemas` at the source to drop blog entries. Use (a). |
| [ADD] | `test_page_types_resource_includes_blog_when_present` | Symmetric positive case. |
| [ADD] | `test_page_types_error_envelope_on_500` | Stubbed 500 → envelope, not exception. |

### 4.13 `phoxtail/mcp/pages/tests/test_media_mcp.py`

| Kind | Test | Asserts |
|---|---|---|
| [ADD] | `test_list_images_forwards_search_and_limit` | Query string built correctly. |
| [ADD] | `test_list_documents_forwards_search_and_limit` | Same. |
| [ADD] | `test_media_tools_return_envelope_on_non_2xx` | 500 → envelope. |

---

## 5. Explicitly NOT in scope

- Surgical StreamField block editing
  (`PATCH /pages/{id}/body/blocks/{block_id}/`) — no endpoint exists.
- Page creation (`POST /pages/`) — post-MVP, absent from the routers.
- `phoxtail_pages_unpublish` beyond the 200 smoke test — re-publish
  flow not spec'd.
- Cross-app FK contributions beyond blog — none exist yet.
- Any change to the runtime gate semantics (don't "fix"
  `get_project_apps` to `apps.is_installed`).

Do not invent tests for these.

---

## 6. Done criteria

- `pytest phoxtail/api/pages phoxtail/api/tests phoxtail/blog phoxtail/cms phoxtail/mcp/pages`
  exits 0. No xfail, no skip without a linked reason in the skip
  reason string.
- `pytest` from the repo root still passes (harness additions to the
  test settings must not break the existing suites in
  `phoxtail/cli/tests`, `phoxtail/core/tests`,
  `phoxtail/booking/**/tests`, `phoxtail/streams/tests`,
  `phoxtail/tokens/tests`).
- `ruff check phoxtail/api/pages phoxtail/api/tests phoxtail/blog/api
  phoxtail/blog/mcp phoxtail/cms/api phoxtail/mcp/pages` clean.
- `phoxtail/docs/docs/mcp/pages-domain-review.md`:
  - Drift #10 (Pydantic extras): 🧪 → ✅.
  - Drift #12 (no test suite): ⏳ → ✅.
- If you added fixtures / harness pieces that other agents will
  reuse, document them in a one-paragraph "Shared test harness"
  section at the bottom of `pages-domain.md`.

---

## 7. Budget and sequencing tips

This is a large task. If time/credits are short, ship in this order
so each landing is valuable on its own:

1. **Harness first.** §2.1–§2.3. A green `pytest phoxtail/core/tests`
   after your settings changes is your canary.
2. **Conftest + fixtures.** §2.3 fixtures plus one trivial smoke test
   (`GET /api/content/v1/page-types/` returns 200) so you know the API
   is reachable through auth.
3. **The 12 [MUST] rows.** Land these as one commit; they pin every
   ✅/🧪 in `pages-domain-review.md`.
4. **[ADD] coverage**, file by file, in the order of §4. Each file is
   an independently mergeable commit.
5. Review-doc flips (§6) only after the suite is green.

If the budget runs out partway through §4, stop at a file boundary
and leave a TODO comment at the top of the next untouched test file
listing the [ADD] rows you didn't get to — don't half-write them.
