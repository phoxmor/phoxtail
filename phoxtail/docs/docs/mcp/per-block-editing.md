# Per-Block Editing

This document covers the full mechanism for **surgical per-block content editing** via the Phoxtail chatbot — what was built, how it works end-to-end, and what remains.

Background on the chatbot itself, the MCP tool architecture, and the SSE streaming model is in [`chatbot.md`](chatbot.md). Read that first if you are new to the stack.

---

## Status

**Fully implemented and working.** All steps described below are complete. The only planned enhancement not yet built is automatic body refresh on publish (see [Future Work](#future-work)).

---

## What Was Built

### The Problem

The original mechanism used `phoxtail_pages_replace_body`, which replaced the entire StreamField body wholesale. After any write, `_touch_reload()` in `phoxtail/mcp/_http.py` touched `src/_reload_trigger.py` — a file watched by Django's autoreloader — which triggered a full browser tab refresh via `django-browser-reload`.

This was broken in two ways:

1. **Full page refresh closed the chatbot drawer.** The user had to reopen it after every edit. Not acceptable for a fluid edit session.
2. **Wholesale body replacement is the wrong primitive.** Replacing 12 blocks to update one title is wasteful and fragile.

The solution has two interdependent halves:

1. **Per-block MCP tools** — surgical read/write operations on individual blocks by UUID.
2. **HTMX block-level refresh** — each block wrapper listens for a custom event and re-renders itself in-place, without touching the rest of the page or the chatbot drawer.

`_reload_trigger` was also removed entirely; it is no longer needed.

---

## Architecture

### Block CRUD API — `phoxtail/api/content/v1/blocks.py`

Five JSON endpoints under `/api/content/v1/pages/{page_id}/`:

| Method | Path | Description |
|---|---|---|
| `GET` | `/{page_id}/blocks/{uuid}/` | Fetch a single block by UUID |
| `PATCH` | `/{page_id}/blocks/{uuid}/` | Update a block's value in-place |
| `POST` | `/{page_id}/blocks/` | Add a new block |
| `DELETE` | `/{page_id}/blocks/{uuid}/` | Remove a block |
| `POST` | `/{page_id}/blocks/{uuid}/move/` | Reorder a block |

All write endpoints require an `If-Match` ETag header, create a draft revision, and do **not** publish. The ETag is page-level (`latest_revision_created_at`).

Every write response includes `_etag` (fresh page ETag) and `_changed_blocks` (list of affected UUIDs). The `_changed_blocks` key is consumed by `chat.py` to emit SSE events; it is inert when called from the terminal.

---

### HTMX Render Endpoints — `phoxtail/cms/views.py`

HTML fragment endpoints live **outside the Ninja API** as plain Django views. This is a deliberate architectural choice:

- The Ninja API uses `PhoxtailTokenAuth` (Bearer tokens) — for machine consumers: CLI, MCP tools, agents.
- HTMX requests from the browser carry only a session cookie, not a Bearer token.
- Browser-facing HTML fragment endpoints belong under `url_mount`, the same pattern used by `phoxtail.core` for its HTMX partials.

**Two views** in `phoxtail/cms/views.py`, protected by `_require_superuser_htmx` (session auth, must be superuser):

```python
# Single block fragment (for block-level outerHTML swap)
GET /phoxtail_cms/htmx-partials/blocks/<page_id>/<block_uuid>/render/
  → render_block_fragment(request, page_id, block_uuid)

# Full body container inner (for full-body innerHTML swap after add/delete/move)
GET /phoxtail_cms/htmx-partials/body/<page_id>/render/
  → render_body_fragment(request, page_id)
```

Both use `resolve_page_for_read` (returns the latest draft revision) and `render_to_string` with the appropriate partial template.

Registered via `PhoxtailCmsConfig.url_mount = UrlMount(prefix="phoxtail_cms/", module="phoxtail.cms.urls")` in `phoxtail/cms/apps.py` — the standard wiring pattern for browser-facing views.

---

### Draft vs Published Rendering

`render_block_fragment` and `render_body_fragment` always render from the **latest draft revision** (`resolve_page_for_read`). This means:

- After an agent edit (which creates a draft), the HTMX refresh shows the draft content in-place, even if the page hasn't been published yet.
- A hard browser refresh of the live page shows the published content (which may be older).

This behaviour is intentional. The design bar is superuser-only, so editors understand they are in a preview context. The inline refresh is a "glimpse" of the pending change — the live page only updates after `phoxtail_pages_publish`. Editors learn this naturally: hard-refresh the live URL and you see what visitors see until you publish.

---

### Template Structure

**`phoxtail/cms/templates/phoxtail_cms/partials/block_fragment.html`** — single block wrapper:

```html
{% load wagtailcore_tags %}
<div id="phoxtail-block-{{ bound_block.id }}"
     class="phoxtail-block"
     hx-get="{% url 'phoxtail_cms:render_block_fragment' page_id=page_id block_uuid=bound_block.id %}"
     hx-trigger="phoxtail:block-refresh"
     hx-swap="outerHTML"
     hx-indicator="#phoxtail-block-{{ bound_block.id }}-indicator">
    <span id="phoxtail-block-{{ bound_block.id }}-indicator"
          class="phoxtail-block-refresh-indicator htmx-indicator"
          aria-hidden="true"></span>
    {% include_block bound_block %}
</div>
```

**`phoxtail/cms/templates/phoxtail_cms/partials/body_container_inner.html`** — inner content for full-body swap:

```html
{% load wagtailcore_tags %}
{% for block in stream_value %}
    {% include "phoxtail_cms/partials/block_fragment.html" with bound_block=block page_id=page_id %}
{% endfor %}
```

**`phoxtail/cms/templates/phoxtail_cms/pages/page.html`** — the page template:

```html
{% extends "phoxtail_cms/pages/base.html" %}
{% load wagtailcore_tags %}

{% block content %}
    <div id="phoxtail-page-content"
         class="phoxtail-page-body"
         hx-get="{% url 'phoxtail_cms:render_body_fragment' page_id=page.id %}"
         hx-trigger="phoxtail:page-body-refresh"
         hx-swap="innerHTML">
        {% for block in page.body %}
            {% include "phoxtail_cms/partials/block_fragment.html" with bound_block=block page_id=page.id %}
        {% endfor %}
    </div>
{% endblock %}
```

#### The `block` variable invariant

Block templates in this project (e.g. `header_section/variants/ground_state/default/template.html`) reference `{{ block.value.field_name }}`, not `{{ value.field_name }}`. The variable named `block` must be a `BoundBlock` in the template context when `{% include_block %}` runs.

`BlockVariantStructBlock.render(value, context)` calls `StructBlock.get_context(value, parent_context=dict(context))` and the resulting `template_context` includes everything from `parent_context`. If the for-loop variable is named `block`, it flows through as `parent_context["block"]` and is accessible in the compiled variant template. If you rename the loop variable (e.g. to `bound_block`), `{{ block.value.xxx }}` in block templates evaluates to empty string and nothing renders.

**Rule:** anywhere that iterates a StreamValue and calls `{% include_block %}` (or includes `block_fragment.html`), the loop variable **must be named `block`**. Pass it as `bound_block=block` to `block_fragment.html` via `{% include ... with %}`.

The same applies in the Django views: `render_block_fragment` passes `{"bound_block": bound_block, "block": bound_block, "page_id": page_id, "page": draft}` so that `{% include_block bound_block %}` in `block_fragment.html` has `block` in its context.

---

### MCP Tools — `phoxtail/mcp/content/blocks.py`

Five tools wrapping the block API:

| Tool | Description |
|---|---|
| `phoxtail_pages_get_block` | Fetch a single block by UUID; returns `{block, _etag}` |
| `phoxtail_pages_update_block` | Replace a block's value in-place; returns `{block, _etag, _changed_blocks}` |
| `phoxtail_pages_add_block` | Add a new block at a given position; returns `{block, _etag, _changed_blocks}` |
| `phoxtail_pages_delete_block` | Remove a block; returns `{deleted_uuid, _etag, _changed_blocks}` |
| `phoxtail_pages_move_block` | Reorder a block; returns `{moved_uuid, _etag, _changed_blocks}` |

`phoxtail_pages_replace_body` is retained for bulk/structural rewrites but its description steers the LLM toward the surgical tools for single-block edits.

---

### SSE Event: `blocks_changed`

`phoxtail/agent/api/v1/chat.py` emits a `blocks_changed` event after any tool call that includes `_changed_blocks` in its result:

```
event: blocks_changed
data: {"page_id": 42, "uuids": ["abc123-..."], "kind": "update"}
```

`kind` is `"update"` | `"add"` | `"delete"` | `"move"`, inferred from the tool name.

---

### Frontend Handler — `design_bar.js`

```javascript
} else if (evt === 'blocks_changed') {
    _handleBlocksChanged(data);
}

function _handleBlocksChanged(data) {
    var uuids = data.uuids || [];
    if (data.kind === 'update') {
        uuids.forEach(function (uuid) { _refreshBlock(uuid); });
    } else {
        _refreshPageBody();
    }
}
```

- **`update`**: fires `phoxtail:block-refresh` on the specific block element → HTMX `outerHTML` swap from `render_block_fragment`.
- **`add` / `delete` / `move`**: fires `phoxtail:page-body-refresh` on `#phoxtail-page-content` → HTMX `innerHTML` swap from `render_body_fragment`.

---

## Future Work

### Publish triggers a body refresh

When `phoxtail_pages_publish` is called, the live page now matches the draft. It would be useful for the design bar to automatically refresh the page body at that point, giving the editor visual confirmation that the publish landed.

**Implementation** (small, self-contained):

1. In `chat.py`, detect when the tool is `phoxtail_pages_publish` and emit a `page_published` SSE event alongside or instead of `blocks_changed`.
2. In `design_bar.js`, handle `page_published` with `_refreshPageBody()`.

The refresh content will be correct: after publish, `resolve_page_for_read` returns the now-published revision, so the HTMX refresh shows what visitors see.

---

### Nested block editing

All tools and block locators operate on top-level StreamField body blocks only. Nested StreamBlocks (blocks within blocks) are out of scope for v1.

---

### Surgical DOM add/delete/move

Currently, `add`, `delete`, and `move` all trigger a full `render_body_fragment` refresh. A v2 could do surgical DOM insertion/removal/reordering instead, eliminating the full re-render. Low priority — the current approach is correct and visible latency is minimal.
