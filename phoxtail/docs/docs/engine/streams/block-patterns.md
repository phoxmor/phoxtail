# Block Patterns

## Overview

By default every dynamic block is available on every page type that uses
`BodyStreamField`. App-level blocks break that assumption: a block can be
restricted to one or more specific page types (e.g. only on `BlogPostPage`),
or it can be a **context-reader block** — a block with no editable schema
fields that reads its data directly from the page it lives on.

This document covers:

1. [Page-type scoping](#1-page-type-scoping) — restricting a block to
   specific page types via `Block.page_types`
2. [Per-page-type StreamFields](#2-per-page-type-streamfields) — how page
   models declare their own StreamField callable
3. [Context-reader blocks](#3-context-reader-blocks) — blocks that render
   page model fields instead of their own value
4. [HTMX in context-reader blocks](#4-htmx-in-context-reader-blocks) — the
   `hx-select` pattern for dynamic updates without separate partials
5. [Current implementation: Blog](#5-current-implementation-blog)
6. [Adding a new app-level block](#6-adding-a-new-app-level-block)
7. [Cross-app blocks](#7-cross-app-blocks) — blocks with schema fields that
   fetch data from another app at render time via template tags

---

## The block primitive

Before diving into the named patterns, it helps to understand what a block
actually *is* at the engine level — because the engine draws no distinction
between any of the categories this document names.

Every block template is a Django template that always receives three things:

1. **`value`** — the block's own schema fields, deserialized into a
   `StructValue`. Empty when the schema is `[]`.
2. **The full parent template context** — `page`, `request`, and everything
   `get_context()` returns, passed in via `parent_context`.
3. **`{% load %}`** — any registered Django template tag library can be
   loaded inside the template.

That's it. The engine has one code path for all blocks.

The named categories — *standard*, *context-reader*, *cross-app* — are
documentation conventions for the most common ways to combine these three
capabilities, not distinct object types or code paths:

| Pattern | `value` fields | `page_types` set | Reads `{{ page.* }}` | Uses template tags |
|---|---|---|---|---|
| Standard | Yes | No | No | No |
| Context-reader | No | Yes (convention) | Yes | No |
| Cross-app | Yes | No | No | Yes |
| Mixed | Yes | Yes | Yes | Yes |

**The page-type restriction is the only structural distinction** — it
genuinely changes which pages a block is offered on in the chooser. But it
says nothing about how a block renders. A context-reader block placed on the
wrong page type would simply produce empty output for `{{ page.intro }}`
without raising an error; the restriction is a defensive configuration
choice, not an engine constraint.

A block can freely combine all four capabilities. Nothing prevents a block
from having schema fields *and* reading `{{ page.author }}` *and* calling a
template tag *and* being restricted to a specific page type. The categories
are useful for reasoning about intent; they are not enforced.

---

## 1. Page-Type Scoping

### The `page_types` field

`Block` has a `ManyToManyField` to `django.contrib.contenttypes.ContentType`:

```python
class Block(models.Model):
    ...
    page_types = ManyToManyField(
        "contenttypes.ContentType",
        blank=True,
        limit_choices_to=_page_content_type_choices,  # filtered to Page subclasses
    )
```

**Rules:**

| `page_types` value | Availability |
|--------------------|--------------|
| Empty (default)    | Available on **all** page types |
| One or more types  | Available **only** on those page types |

### How the factory uses it

`build_dynamic_blocks()` — used by the general `BodyStreamField` — returns
only blocks where `page_types` is empty:

```python
no_restriction = ~Exists(PageTypeRelation.objects.filter(block_id=OuterRef("pk")))
Block.objects.filter(no_restriction)
```

`build_blocks_for_page_type(content_type_id)` — used by page-type-specific
StreamFields — returns unrestricted blocks **plus** blocks whose `page_types`
includes the given content type:

```python
no_restriction = ~Exists(PageTypeRelation.objects.filter(block_id=OuterRef("pk")))
has_this_type  = Exists(PageTypeRelation.objects.filter(
    block_id=OuterRef("pk"), contenttype_id=content_type_id
))
Block.objects.filter(no_restriction | has_this_type)
```

### Cache layer

Results are cached per content type ID in `streams/cache.py`:

```python
_page_type_blocks_cache: dict  # { content_type_id → [(identifier, block_instance), ...] }

get_cached_blocks_for_page_type(content_type_id) → list
```

The cache is invalidated (cleared to `{}`) together with all other block
caches when a `Block` is saved or deleted via the `clear_block_cache` signal
handler.

---

## 2. Per-Page-Type StreamFields

A page model that needs app-level blocks defines its own callable and
`SchemaStreamField` instance:

```python
# In yourapp/streams.py

from streams.fields import SchemaStreamField

def get_blog_post_body_blocks():
    from django.contrib.contenttypes.models import ContentType
    from django.db import OperationalError, ProgrammingError

    from blog.models import BlogPostPage  # lazy — inside function to avoid circular imports
    from streams.cache import get_cached_blocks_for_page_type

    try:
        ct = ContentType.objects.get_for_model(BlogPostPage)
        return get_cached_blocks_for_page_type(ct.id)
    except (ProgrammingError, OperationalError):
        return []

BlogPostBodyStreamField = SchemaStreamField(
    get_blog_post_body_blocks,
    null=True,
    blank=True,
    collapsed=True,
)

# In yourapp/models.py

from blog.streams import BlogPostBodyStreamField

class BlogPostPage(TimestampMixin, Page):
    body = BlogPostBodyStreamField
```

**Key points:**

- Stream field callables and descriptors live in a dedicated `streams.py`
  module alongside the app's `models.py`. This keeps `models.py` focused
  on model definitions.
- The callable imports the page model lazily (inside the function body) to
  avoid circular imports between `streams.py` and `models.py`.
- The `SchemaStreamField` generation cache still works — when `_cache_generation`
  increments (Block saved/deleted), the StreamField rebuilds by calling
  `get_blog_post_body_blocks()` again, which hits the now-cleared
  `_page_type_blocks_cache` and fetches fresh data.

---

## 3. Context-Reader Blocks

A context-reader block has **no content fields in its schema**. Instead of
reading `{{ value.field }}`, its variant templates read directly from the
**page context** — `{{ page.title }}`, `{{ page.author }}`, etc.

### Why this works

`BlockVariantStructBlock.render()` passes the full parent template context
into the block's Django template via `parent_context`. This means any block
template already has access to `{{ page }}`, `{{ request }}`, and everything
else on them — not just `{{ value }}`.

### Schema definition

A context-reader block has an empty (or near-empty) schema:

```json
[]
```

The factory produces a block with only the variant chooser:

```
┌──────────────────────────────┐
│ Blog Post Header             │
│ Variant: [ Choose...  ▾ ]   │
└──────────────────────────────┘
```

### Variant template

The variant's HTML template reads from `page`, not `value`:

```django
<header id="bph-{{ block.id }}" class="bph-wrapper">
    <h1 class="bph-title">{{ page.title }}</h1>
    <p class="bph-intro">{{ page.intro }}</p>

    <time datetime="{{ page.first_published_at|date:'Y-m-d' }}">
        {{ page.first_published_at|date:"M d, Y" }}
    </time>

    {% if page.author %}
        <div class="bph-author">
            {{ page.author.user.get_full_name }}
            {% if page.author.title %}
                <span>| {{ page.author.title }}</span>
            {% endif %}
        </div>
    {% endif %}
</header>
```

### Scoping requirement

Context-reader blocks **must** be scoped to the page types they understand.
A `Blog Post Header` block that reads `page.author` and `page.intro` would
break on a `SitePage` that has neither field. Always set `page_types` on
context-reader blocks to the page types whose fields the variant templates
reference.

### Tradeoff: flexibility vs. guarantees

| Approach | Flexibility | Guarantee |
|----------|-------------|-----------|
| Hardcoded template header | One visual style | Header always present |
| Context-reader block | Multiple variants via block system | Editor can delete/reorder |

Use context-reader blocks when you genuinely want multiple header styles
selectable per-post. Use the hardcoded template approach when a single
consistent header is sufficient.

---

## 4. HTMX in Context-Reader Blocks

Context-reader blocks that need dynamic updates (search, pagination, filters)
**must not** use separate server-side partial templates. Doing so decouples
the rendering from the block variant, requiring parallel maintenance of both
files whenever the variant changes.

### The `hx-select` pattern

Instead of returning a lightweight partial, the server always renders the
**full page**. HTMX selects only the elements it needs from the response
client-side:

```django
<input hx-get="{{ request.path }}"
       hx-target="#bpl-posts-{{ block.id }}"
       hx-swap="outerHTML"
       hx-select="#bpl-posts-{{ block.id }}"
       hx-select-oob="#bpl-pagination-{{ block.id }},#bpl-results-{{ block.id }}">
```

- `hx-select` — which element to extract from the full-page response and
  place into `hx-target`
- `hx-select-oob` — additional elements to extract from the response and
  swap out-of-band (comma-separated)

The page's `serve()` method requires no HTMX-specific branching:

```python
def serve(self, request, *args, **kwargs):
    context = self.get_context(request, *args, **kwargs)
    return render(request, self.template, context)
```

The block variant template is the **single source of truth** for all
rendering — initial load and every subsequent HTMX update.

### Scoped HTMX IDs

Because multiple instances of the same block can appear on a page, all
element IDs that HTMX targets must be scoped to the block instance:

```django
id="bpl-posts-{{ block.id }}"
id="bpl-pagination-{{ block.id }}"
id="bpl-results-{{ block.id }}"
id="bpl-loading-{{ block.id }}"
id="bpl-input-{{ block.id }}"
```

The same IDs are used in the `hx-target`, `hx-select`, `hx-select-oob`, and
`hx-indicator` attributes. JavaScript that reads these IDs uses a
`data-bpl-id="{{ block.id }}"` attribute on the root element to locate
scoped IDs without global selectors:

```javascript
function initBlogPostList(wrapper) {
    var id = wrapper.dataset.bplId;
    var searchInput = document.getElementById('bpl-input-' + id);
    // ...
}
document.querySelectorAll('[data-bpl-id]').forEach(initBlogPostList);
```

**Note on `hx-include`:** when the triggering element itself carries
`name="q"`, its value is already serialised automatically by HTMX. Do not
use `hx-include="[name='q']"` — with multiple blocks on the page that
selector matches all instances and sends duplicate parameters.

---

## 5. Current Implementation: Blog

### What exists

`BlogPostPage.body` uses `BlogPostBodyStreamField`, which calls
`get_blog_post_body_blocks()`. This returns:

- All unrestricted blocks (general dynamic blocks available on every page)
- Any block whose `page_types` includes `BlogPostPage`'s ContentType

`BlogIndexPage.body` uses `BlogIndexBodyStreamField`, which calls
`get_blog_index_body_blocks()`. This returns:

- All unrestricted blocks
- Any block whose `page_types` includes `BlogIndexPage`'s ContentType

Both index and detail templates are now plain body-loops — all content is
delivered through blocks.

### Blog-specific blocks (group: Blog)

| Block identifier      | Page type      | Kind            | Description |
|-----------------------|----------------|-----------------|-------------|
| `blog_post_header`    | BlogPostPage   | Context-reader  | Post title, intro, date, read time, author |
| `blog_related_posts`  | BlogPostPage   | Context-reader  | 3-column grid of sibling posts |
| `blog_post_list`      | BlogIndexPage  | Context-reader  | Searchable, paginated post grid with HTMX |
| `blog_recent_posts`   | Any page       | Cross-app       | Configurable grid of recent posts from a chosen BlogIndexPage |

### Setting a block as blog-only

In the Wagtail admin → Streams → Blocks → edit a block → Details tab:

1. Find the **Page Types** field
2. Select `blog | blog post page` or `blog | blog index page`
3. Save

From that point the block only appears in the block chooser when editing
that specific page type.

---

## 6. Adding a New App-Level Block

### Step 1: Create the block via `populate_streams` or admin

Create the data files under
`streams/management/commands/data/blocks/<identifier>/`:

```
block.yaml          # name, identifier, icon, group, page_types
schema.json         # [] for context-reader, or field definitions
variants/
  ground_state/
    default/
      variant.yaml
      template.html  # never use {% include %} — inline all HTML and SVGs
      styles.css     # pure CSS, scoped under #prefix-{{ block.id }}
      script.js      # optional; use data attribute for multi-instance init
```

Set `page_types` in `block.yaml`:

```yaml
page_types:
  - yourapp.yourpagetype
```

### Step 2: Create a page-type-specific StreamField (if not already exists)

```python
# In yourapp/streams.py

from streams.fields import SchemaStreamField

def get_yourpage_body_blocks():
    from django.contrib.contenttypes.models import ContentType
    from django.db import OperationalError, ProgrammingError

    from yourapp.models import YourDetailPage  # lazy import to avoid circular imports
    from streams.cache import get_cached_blocks_for_page_type

    try:
        ct = ContentType.objects.get_for_model(YourDetailPage)
        return get_cached_blocks_for_page_type(ct.id)
    except (ProgrammingError, OperationalError):
        return []

YourBodyStreamField = SchemaStreamField(
    get_yourpage_body_blocks,
    null=True,
    blank=True,
    collapsed=True,
)

# In yourapp/models.py

from yourapp.streams import YourBodyStreamField

class YourDetailPage(Page):
    body = YourBodyStreamField
```

### Step 3: Write variant templates

For context-reader blocks, templates use `{{ page.field }}`.
For normal app-level blocks, templates use `{{ value.field }}` as usual.

**Rules for all block variant templates:**

- Never use `{% include %}` — inline all HTML, including SVGs
- Use pure CSS, scoped under `#prefix-{{ block.id }}`
- Scope all HTMX element IDs with `{{ block.id }}` to support multiple
  instances on the same page
- If the block needs HTMX dynamic updates, use the `hx-select` + full-page
  render pattern (see [section 4](#4-htmx-in-context-reader-blocks))

### Step 4: Update the page template (if replacing hardcoded content)

Replace any hardcoded sections in the page template with the body-loop:

```django
{% for block in page.body %}
    {% with streamfield_name="body" block_index=forloop.counter0 %}
        {% include_block block %}
    {% endwith %}
{% endfor %}
```

---

## File Reference

| File | Role |
|------|------|
| `streams/models.py` | `Block.page_types` M2M field (imports `_page_content_type_choices`) |
| `streams/utils.py` | `_page_content_type_choices` — filters page type choices to Page subclasses |
| `streams/blocks/factory.py` | `build_dynamic_blocks` (unrestricted only) + `build_blocks_for_page_type` |
| `streams/cache.py` | `_page_type_blocks_cache` + `get_cached_blocks_for_page_type` |
| `streams/viewsets.py` | `FieldPanel("page_types")` in Block admin Details tab |
| `blog/streams.py` | `get_blog_post_body_blocks` + `BlogPostBodyStreamField` + `get_blog_index_body_blocks` + `BlogIndexBodyStreamField` |
| `blog/models.py` | `BlogPostPage.body` + `BlogIndexPage.body` (imports from `blog/streams.py`) |
| `blog/templatetags/blog_tags.py` | `get_recent_blog_posts` template tag for cross-app blocks |
| `blog/templates/blog/detail/object.html` | Body-loop template for BlogPostPage |
| `blog/templates/blog/list/index.html` | Body-loop template for BlogIndexPage |

---

## 7. Cross-App Blocks

### What distinguishes them

A **cross-app block** differs from context-reader blocks in two key ways:

| Property | Context-reader block | Cross-app block |
|----------|----------------------|-----------------|
| Schema fields | Empty (`[]`) | Has configurable fields (e.g., page chooser, integer) |
| Data source | `{{ page.field }}` from parent context | Fetched at render time via a template tag |
| Page type restriction | Required (reads page-specific fields) | Optional — typically unrestricted (available everywhere) |

### The template tag bridge

Block variant templates are stored in the database and rendered via Django
Template Language. They cannot execute Python querysets directly. The bridge
is a **template tag** defined in the app that owns the data:

```python
# blog/templatetags/blog_tags.py

from django import template

register = template.Library()

@register.simple_tag
def get_recent_blog_posts(blog_index_page, count=3):
    if not blog_index_page:
        return []
    from blog.models import BlogPostPage
    return (
        BlogPostPage.objects.live()
        .child_of(blog_index_page)
        .order_by("-first_published_at")[:count]
    )
```

The variant template loads the tag and uses it:

```django
{% load blog_tags %}
{% get_recent_blog_posts value.blog_index value.count|default:3 as recent_posts %}
{% for post in recent_posts %}...{% endfor %}
```

The import of `BlogPostPage` is deferred inside the function to avoid
circular imports at module load time.

### The `page_type` restriction in schema

`PageChooserBlock` accepts a `page_type` kwarg that restricts the chooser to
a specific page model. In `schema.json`, set it in the field value:

```json
{
  "type": "page_chooser_field",
  "value": {
    "name": "blog_index",
    "required": true,
    "page_type": "blog.blogindexpage"
  }
}
```

For this to work the factory must pass `page_type` through to
`PageChooserBlock`. The mapping in `streams/blocks/factory.py` is:

```python
"page_chooser_field": (PageChooserBlock, ["page_type", "can_choose_root"]),
```

Wagtail accepts `"app_label.modelname"` strings natively as the `page_type`
argument.

### Architecture diagram

```
SitePage.body = [blog_recent_posts block]
                        │
                  value.blog_index  ──→  BlogIndexPage instance (PageChooserBlock)
                  value.count       ──→  integer (IntegerBlock)
                        │
          {% get_recent_blog_posts value.blog_index value.count as posts %}
                        │
          BlogPostPage.objects.live().child_of(blog_index).order_by(...)[:count]
                        │
          {% for post in posts %}...{% endfor %}
```

The template tag is defined in `blog/` (which owns the queryset logic). The
block template is DB-stored and portable. No app-level coupling occurs at
import time.

### Example: `blog_recent_posts`

| Property | Value |
|----------|-------|
| Identifier | `blog_recent_posts` |
| Page types | None (available on all pages) |
| Schema fields | `blog_index` (PageChooser → BlogIndexPage), `count` (integer 1–12) |
| Template tag | `{% get_recent_blog_posts value.blog_index value.count as posts %}` |
| Styles prefix | `brp-` scoped under `#brp-{{ block.id }}` |

### Adding a new cross-app block

1. Create the block data files (same structure as any block)
2. Set `schema.json` to include the chooser/config fields — do **not** leave
   it empty like a context-reader block
3. Omit `page_types` in `block.yaml` if the block should appear everywhere
4. Create a `templatetags/` package in the app that owns the data model
5. Write a `simple_tag` that accepts the chooser value and returns a queryset
6. In the variant template, `{% load <app>_tags %}` and call the tag with
   `as <var>`, then iterate
