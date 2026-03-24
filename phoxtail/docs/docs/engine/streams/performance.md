# Dynamic Blocks: Performance Bottlenecks & Mitigations

This document tracks identified performance bottlenecks in the dynamic blocks
architecture and the mitigations applied to address each one.

---

## Bottleneck #1 — Database Query Per Block Render

**Severity:** High

**Location:** `streams/blocks/base.py` — `BlockVariantStructBlock.render()`

**Problem:**
Every time a block without a variant is rendered, the system calls
`Block.objects.get(identifier=...)` to fetch the block's HTML, CSS, and
JavaScript from the database. A page with N blocks fires N separate queries
on every page view. Block definitions are edited rarely (admin-only
operations), yet the database is queried on every single render.

**Mitigation:** In-memory block record cache (`streams/cache.py`)

A process-level dictionary caches `Block` instances keyed by identifier.
The first render fetches from the database; all subsequent renders read from
memory. The cache is invalidated via Django `post_save` / `post_delete`
signals whenever a `Block` is saved or deleted in the admin.

**Files changed:**
- `streams/cache.py` — new module; `get_block_by_identifier()` + `clear_block_cache()`
- `streams/signals.py` — new module; connects invalidation signals
- `streams/apps.py` — calls `connect_cache_signals()` in `ready()`
- `streams/blocks/base.py` — `render()` now calls `get_block_by_identifier()` instead of `Block.objects.get()`

**Expected impact:**
- Before: N database queries per page (one per block)
- After: 0 database queries per page (after first request warms the cache)

---

## Bottleneck #2 — Template Recompilation on Every Render

**Severity:** High

**Location:** `streams/blocks/base.py` — `Template(html).render(...)` calls

**Problem:**
`django.template.Template(string)` parses and compiles the template from
scratch every time it is called. Django's built-in template caching only
works for file-based templates loaded via template loaders — string-based
`Template()` bypasses it entirely. Each block can compile up to 3 templates
(HTML, CSS, JavaScript), so a page with 10 blocks performs up to 30
compilations per page view for strings that haven't changed.

**Mitigation:** Compiled template cache (`streams/cache.py`)

A process-level dictionary caches compiled `Template` objects keyed by the
hash of the template string. The first time a given HTML/CSS/JS string is
encountered, `Template(string)` compiles it and the result is stored.
All subsequent renders of the same string reuse the already-compiled object —
only the `.render(context)` call runs, which is the cheap part.

The cache is cleared by the same `post_save` / `post_delete` signal that
clears the block record cache (Mitigation #1), since template content only
changes when a Block is edited.

**Files changed:**
- `streams/cache.py` — added `get_compiled_template()`, `_template_cache` dict, extended `clear_block_cache()` to also clear template cache
- `streams/blocks/base.py` — `render()` now calls `get_compiled_template(string).render(context)` instead of `Template(string).render(context)`; removed unused `Template` import

**Expected impact:**
- Before: up to 3 template compilations per block per page view (N×3 total)
- After: 0 compilations per page view (after first request warms the cache)

---

## Bottleneck #3 — `stream_block` Property Regenerates on Every Access (Memory Leak)

**Severity:** Critical (causes steadily degrading performance per request)

**Location:** `streams/fields.py` — `SchemaStreamField.stream_block`

**Problem:**
Wagtail's base `StreamField` uses `@cached_property` for `stream_block`,
meaning the block list is computed once and reused forever. Our
`SchemaStreamField` overrides this with a plain `@property` to support
dynamic blocks — but this means every access triggers a full rebuild.

Each rebuild calls `get_dynamic_blocks()`, which:
1. Queries `Block.objects.all()` from the database
2. For each Block, calls `type()` to create new Python class objects
3. For each nested struct/list_struct, creates additional class objects
4. Creates new `Meta` classes via `type()` for each

Wagtail internally accesses `self.stream_block` from multiple methods
(`from_db_value`, `to_python`, `formfield`, `check`, etc.), so a single
page load can trigger multiple rebuilds.

Python classes created with `type()` are heavyweight objects that register
as subclasses on their parent classes and are tracked by the garbage
collector's gen2 (which runs infrequently). With each page request, dozens
of orphaned class objects accumulate in memory. This manifests as:

- **Steadily increasing LCP** with each page refresh (observed: ~1s first
  load growing to ~10s after 10-12 refreshes)
- **Performance resets on container/process restart** (fresh process = no
  accumulated objects)

**Root cause confirmed:** `@property` replacing `@cached_property` combined
with `type()` class generation = memory leak via class accumulation.

**Mitigation:** Two-layer cache with generation counter

**Layer 1 — Dynamic blocks list cache** (`streams/cache.py`):
The `get_dynamic_blocks()` result (the list of `(identifier, block_instance)`
tuples) is cached in `_dynamic_blocks_cache`. The actual generation logic is
moved to `build_dynamic_blocks()` in `factory.py`, called only on first
access or after cache invalidation. This ensures `type()` is called once per
Block definition, not once per `stream_block` access.

**Layer 2 — StreamBlock instance cache** (`streams/fields.py`):
Each `SchemaStreamField` instance caches its `StreamBlock` result in
`_cached_stream_block`. A global `_cache_generation` counter (incremented
on every cache clear) tells the field whether its cached `StreamBlock` is
stale. If the generation matches, the cached `StreamBlock` is returned
directly — zero work done.

**Files changed:**
- `streams/cache.py` — added `_dynamic_blocks_cache`, `get_cached_dynamic_blocks()`, `_cache_generation`, `get_cache_generation()`; `clear_block_cache()` now clears all caches and increments generation
- `streams/blocks/factory.py` — generation logic moved to `build_dynamic_blocks()`; `get_dynamic_blocks()` now delegates to cache
- `streams/fields.py` — `stream_block` property now caches its `StreamBlock` and checks generation counter before rebuilding

**Expected impact:**
- Before: N class objects created per `stream_block` access, accumulating across requests (memory leak)
- After: class objects created once on first access, reused for all subsequent requests until a Block is edited

---

## Architecture Notes

All caches share the same invalidation trigger: a `Block` or `BlockVariant`
being saved or deleted in the admin. This is safe because:

- Block/variant edits are rare (admin-only operations)
- Cache rebuilds are cheap (one DB query, fast in-memory work)
- Per-process cache requires no external dependencies (no Redis)
- In multi-process deployments (gunicorn), each worker warms independently

---

## Future Optimizations (TODO)

### TODO #1 — Cross-Process Cache Invalidation via Redis

**Severity:** Medium (matters in multi-worker production deployments)

**Problem:**
The Django `post_save` signal fires only in the process that handled the
admin request. In production with multiple gunicorn workers, when an admin
edits a Block, only the worker that processed the save clears its cache.
Other workers continue serving stale cached data until they are recycled.

**Proposed solution:**
When Redis is available (planned for Celery integration), use it as a
shared generation counter. On Block save, increment the counter in Redis.
Each worker checks the Redis counter on request and compares to its local
generation — if they differ, local caches are cleared and rebuilt.

This keeps the fast in-process caches (nanosecond reads) while adding
instant cross-process invalidation (one Redis GET per request, ~0.1ms).

**Prerequisites:** Redis, django-redis or redis-py

---

### TODO #2 — Inline CSS/JS Deduplication

**Severity:** Medium

**Problem:**
Each block renders its own `<style>` and `<script>` tags inline. When the
same block type appears multiple times on a page (e.g. three `rich_text`
blocks without variants), identical CSS/JS is emitted three times. This
increases HTML payload size and causes the browser to recalculate styles
after each `<style>` block (render-blocking).

**Proposed solution:**
Track which block identifiers have already emitted their CSS/JS within the
current render context. Skip duplicate output for blocks with the same
identifier and no variant override.

**Files affected:** `streams/blocks/base.py` — `render()` method

---

### TODO #3 — CSS/JS Aggregation (Move to `<head>` / End of `<body>`)

**Severity:** Medium

**Problem:**
Even after deduplication, `<style>` tags scattered throughout `<body>` are
suboptimal. They cause Flash of Unstyled Content (FOUC) and force the
browser to re-layout after each encountered style block. `<script>` tags in
`<body>` can be parser-blocking.

**Proposed solution:**
Collect all block CSS/JS during page render and emit them once:
- CSS in a single `<style>` block in `<head>` (via a custom template tag or
  context processor)
- JS in a single `<script>` block at the end of `<body>`

This requires a two-pass approach or a page-level collector that blocks
contribute to during render, with a template tag that outputs the
aggregated result.

**Files affected:** `streams/blocks/base.py`, new template tag, page templates

---

### TODO #4 — Explicit Variant Selection Bypasses All Caches (N+1)

**Severity:** Medium-High (scales linearly with variant adoption)

**Problem:**
There are two variant resolution paths with very different costs:

| Path | Cost |
|------|------|
| No variant selected → `get_default_variant()` | 0 queries (cached in `_default_variant_cache`) |
| Editor selects variant → `value.get("variant")` | 1 DB query per block (Wagtail SnippetChooserBlock FK resolution during `from_db_value`) |

When Wagtail deserializes a StreamField value, every `SnippetChooserBlock`
resolves its FK via a separate query. This happens in Wagtail's
`from_db_value()` / `to_python()` path — before `render()` is even called —
so our cache layer never sees it. A page with 8 blocks where editors have
explicitly chosen variants = 8 extra queries that bypass every cache in
`streams/cache.py`.

This is the **single remaining N+1 in the system** and the only path where
query count scales with page content. Additionally, the explicit variant
path produces fresh string objects for `.html`, `.css`, `.javascript` on
each deserialization, meaning `hash()` in `get_compiled_template()` must
compute O(n) on the string length rather than returning the internally-
cached hash from a persistent string object (as happens with the cached
default variant path).

**Proposed solution:**
Cache `BlockVariant` records in an in-memory dict (keyed by PK) with signal
invalidation on `BlockVariant` save/delete — the signals are already
connected. Investigate Wagtail's StreamField deserialization path for
prefetch opportunities, though this may require patching or subclassing
`SnippetChooserBlock` to intercept FK resolution.

**Files affected:** `streams/cache.py`, potentially a custom chooser block subclass

---

### ~~TODO #5 — BlockVariant Signal Invalidation~~ ✅ Done

`BlockVariant` `post_save` / `post_delete` signals are now connected to
`clear_block_cache` in `streams/signals.py`. All caches (including
`_template_cache`) are cleared when a variant is edited or deleted.

---

### TODO #5 — Template Cache Key Uses `hash()` Instead of String Identity

**Severity:** Low (correctness footnote, not a performance bottleneck)

**Problem:**
`get_compiled_template()` in `cache.py` uses `hash(template_string)` as
the cache key. Python's `hash()` is not collision-resistant — two different
strings *can* produce the same hash value. With dozens of templates this
will never happen in practice, but the cache could silently return the
wrong compiled template on a collision.

Additionally, using `hash()` is redundant: Python dicts already hash their
keys internally. Using `hash(string)` as the key means the string is hashed
to produce an int, then the int is hashed again for the dict bucket lookup.

**Proposed solution:**
Use the template string itself as the dict key. This is both simpler and
eliminates the theoretical collision:

```python
# Before
cache_key = hash(template_string)

# After
cache_key = template_string
```

Dict lookups on strings are already O(1) amortized via internal hashing,
and Python caches the hash value on `str` objects after first computation.

**Files affected:** `streams/cache.py` — `get_compiled_template()`

---

### TODO #6 — HTTP-Level Page Caching

**Severity:** Medium-High (largest potential impact for read-heavy sites)

**Problem:**
Even with all in-process caches warm, each page view still renders all
blocks through Django's template engine. For pages whose content doesn't
change frequently, this work is repeated unnecessarily.

**Proposed solution:**
Add page-level caching using one or more of:
- Wagtail's built-in cache framework (`{% cache %}` template tags)
- Django cache middleware for full-page caching
- CDN-level caching with appropriate cache headers
- Cache invalidation on page publish via Wagtail's `page_published` signal

This would make most page views bypass block rendering entirely, serving
the fully-rendered HTML from cache.

**Prerequisites:** Cache backend (Redis recommended), cache invalidation strategy

---

### TODO #7 — Minor: `block_map` Dict Rebuilt on Every Factory Call

**Severity:** Low (only runs during cache rebuild, not per-render)

**Problem:**
`_create_field_block()` in `factory.py` constructs a 23-entry `block_map`
dictionary inside the function body on every call. During cache rebuild,
this function is called once per field across all blocks — potentially
dozens of times — each allocating and discarding the same dict.

**Proposed solution:**
Hoist `block_map` to module-level as a constant. Trivial one-line change.

**Files affected:** `streams/blocks/factory.py`

---

### TODO #8 — Minor: `print()` Statements in Factory

**Severity:** Low

**Problem:**
`factory.py` lines 213 and 434 use `print()` for warnings instead of
`logger.warning()`. In production, stdout writes are synchronous and
unfiltered. Every other warning path in the factory correctly uses the
logger.

**Proposed solution:**
Replace with `logger.warning()` calls.

**Files affected:** `streams/blocks/factory.py`
