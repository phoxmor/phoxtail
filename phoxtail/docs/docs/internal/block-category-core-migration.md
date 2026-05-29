# BlockCategory: Add to Core Library

## Context

This document describes changes to the core Phoxtail library only. A separate downstream site will apply its own changes once this lands.

**Project root:** `/home/evangelos-pisinas/work/phoxmor/phoxtail`
**App being modified:** `phoxtail/streams`
**API being modified:** `phoxtail/api/streams/v1`
**MCP being modified:** `phoxtail/mcp/studio`
**Django management commands:** use `phoxtail manage <cmd>` (never `python manage.py`)

---

## Decision Summary (do not relitigate)

Add a `BlockCategory` model to `phoxtail/streams` alongside `Block`, `BlockVariant`, and `VariantCollection`. Add a M2M field `Block.categories` pointing to it. This represents the *purpose* of a block (e.g. Marketing, Ecommerce, Application UI) — a small, governed vocabulary of ~5–8 coarse browse buckets. It is orthogonal to `VariantCollection` (which represents design language, e.g. MD3, HIG).

No data migration is needed — this is a greenfield addition.

---

## Files to Create or Modify

| File | Action |
|------|--------|
| `phoxtail/streams/models.py` | Add `BlockCategory` model; add `Block.categories` M2M |
| `phoxtail/streams/migrations/0005_*.py` | Generated migration (run `makemigrations`) |
| `phoxtail/streams/viewsets.py` | Add `BlockCategoryViewSet`; add categories panel to `BlockViewSet` |
| `phoxtail/streams/wagtail_hooks.py` | Register `BlockCategoryViewSet` in `StreamsViewSetGroup` |
| `phoxtail/api/streams/v1/block_categories.py` | New file — Ninja router for CRUD + block↔category assignment |
| `phoxtail/api/streams/v1/__init__.py` | Mount new router at `/block-categories` |
| `phoxtail/mcp/studio/block_categories.py` | New file — MCP tools |

---

## 1 — `phoxtail/streams/models.py`

### 1a. Add `BlockCategory`

Add the class near the top of the file, before `Block`. The same mixins used by similar models elsewhere in the codebase apply here. Check existing imports before adding — `Orderable`, `index`, `models` are already there; add the missing ones from `phoxtail.core.mixins` and `wagtail.snippets.models`:

```python
from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet
from phoxtail.core.mixins import AdminURLMixin, TimestampMixin, UUIDMixin

@register_snippet
class BlockCategory(UUIDMixin, TimestampMixin, AdminURLMixin, Orderable, index.Indexed):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    slug = models.SlugField(max_length=100, unique=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
    ]

    search_fields = [
        index.AutocompleteField("name"),
        index.SearchField("description"),
    ]

    class Meta(Orderable.Meta):
        verbose_name = _("Block Category")
        verbose_name_plural = _("Block Categories")

    def __str__(self):
        return self.name
```

### 1b. Add `Block.categories` M2M

On the `Block` model, add after the `page_types` field:

```python
categories = models.ManyToManyField(
    "phoxtail_streams.BlockCategory",
    blank=True,
    related_name="blocks",
    verbose_name=_("Categories"),
    help_text=_(
        "Broad purpose groupings (e.g. Marketing, Ecommerce). "
        "Keep the vocabulary small and governed."
    ),
)
```

---

## 2 — Migration

```bash
phoxtail manage makemigrations phoxtail_streams --name blockcategory_block_categories
```

This produces `phoxtail/streams/migrations/0005_blockcategory_block_categories.py`. No data migration. Verify the generated file creates `BlockCategory` first, then adds the M2M to `Block`.

---

## 3 — `phoxtail/streams/viewsets.py`

### 3a. Import `BlockCategory`

Add to the existing import from `.models`:

```python
from .models import Block, BlockCategory, BlockVariant, SharedBlock, VariantCollection
```

### 3b. Add `BlockCategoryViewSet`

```python
class BlockCategoryViewSet(SnippetViewSet):
    model = BlockCategory
    icon = "tag"
    menu_label = _("Block Categories")
    menu_name = _("Block Categories")
    menu_order = 50
    list_display = ["name", "slug"]
    search_fields = ["name", "slug", "description"]

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
    ]
```

### 3c. Add categories panel to `BlockViewSet`

In `BlockViewSet.edit_handler`, inside the Details `ObjectList`, add after `FieldPanel("page_types")`:

```python
FieldPanel("categories"),
```

---

## 4 — `phoxtail/streams/wagtail_hooks.py`

Import `BlockCategoryViewSet` and prepend it to `StreamsViewSetGroup.items`:

```python
from .viewsets import (
    BlockCategoryViewSet,
    BlockVariantViewSet,
    BlockViewSet,
    SharedBlockViewSet,
    VariantCollectionViewSet,
)

class StreamsViewSetGroup(ModelViewSetGroup):
    ...
    items = (
        BlockCategoryViewSet,
        BlockViewSet,
        SharedBlockViewSet,
        BlockVariantViewSet,
        VariantCollectionViewSet,
    )
```

---

## 5 — `phoxtail/api/streams/v1/block_categories.py` (new file)

Mirror the conventions of `collections.py` and `blocks.py` in the same directory (Ninja `Router`, `Schema` classes, ETag pattern, 409/412/428 error handling).

### Endpoints

**Category CRUD** — mounted at `/block-categories/`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | List/search categories. Returns `{items: [{id, name, slug, description}], total}`. Supports `search`, `limit`, `offset` query params. Use `get_search_backend().autocomplete()` for search. |
| `POST` | `/` | Create. `name` and `slug` required. 409 on duplicate slug. Returns 201 + created object. |
| `GET` | `/{id}/` | Get one category. Returns object + ETag header. |
| `PATCH` | `/{id}/` | Update (partial). Requires `If-Match` ETag header. 412 on conflict, 428 if ETag missing. |
| `DELETE` | `/{id}/` | Delete. Returns 204. |

**Block↔category assignment** — also in this router:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/blocks/{block_id}/categories/` | List categories currently assigned to a block. Returns `{items: [...], total}`. |
| `PUT` | `/blocks/{block_id}/categories/` | Replace full category set. Body: `{"category_ids": [1, 2]}`. Returns updated list. |
| `POST` | `/blocks/{block_id}/categories/{category_id}/` | Add one category to a block. 404 if either doesn't exist. 409 if already assigned. Returns 201. |
| `DELETE` | `/blocks/{block_id}/categories/{category_id}/` | Remove one category from a block. 404 if not assigned. Returns 204. |

Use `Block` and `BlockCategory` from `phoxtail.streams.models`. ETags on single-object reads can be computed from `last_modified` (if available on the model via `TimestampMixin`) or a hash of relevant fields — match whatever pattern `blocks.py` uses.

---

## 6 — `phoxtail/api/streams/v1/__init__.py`

Add:

```python
from phoxtail.api.streams.v1.block_categories import router as block_categories_router
...
router.add_router("/block-categories", block_categories_router)
```

---

## 7 — `phoxtail/mcp/studio/block_categories.py` (new file)

Import the HTTP helper the same way `blocks.py` does:

```python
from phoxtail.mcp.studio._http import get_json, request
```

The helper is already bound to `/api/streams/v1`, so paths are relative (e.g. `"/block-categories/"`, `"/blocks/{id}/categories/"`).

### Tools to implement

| Tool name | HTTP call | Notes |
|-----------|-----------|-------|
| `phoxtail_studio_list_block_categories` | `GET /block-categories/` | Supports optional `search` param |
| `phoxtail_studio_create_block_category` | `POST /block-categories/` | `name`, `slug` required; `description` optional |
| `phoxtail_studio_get_block_category` | `GET /block-categories/{id}/` | Returns object + `_etag` |
| `phoxtail_studio_update_block_category` | `PATCH /block-categories/{id}/` | All fields optional; requires `etag` arg |
| `phoxtail_studio_delete_block_category` | `DELETE /block-categories/{id}/` | |
| `phoxtail_studio_set_block_categories` | `PUT /blocks/{block_id}/categories/` | Body: `{"category_ids": [...]}`. Full replacement. |
| `phoxtail_studio_add_block_category` | `POST /blocks/{block_id}/categories/{cat_id}/` | Add one |
| `phoxtail_studio_remove_block_category` | `DELETE /blocks/{block_id}/categories/{cat_id}/` | Remove one |

Tool descriptions should note: keep the category vocabulary small (~5–8 broad purpose buckets). The `list` tool description should instruct agents to call it before assigning categories to avoid creating duplicates.

### Registration

Check how other files in `phoxtail/mcp/studio/` are imported to trigger tool registration (likely via `phoxtail/mcp/studio/__init__.py` or `phoxtail/cli/mcp.py`). Mirror that pattern for `block_categories.py`.

---

## Verification

After implementing:

1. `phoxtail manage migrate` — migrations apply cleanly
2. `phoxtail manage check` — no system check errors
3. Wagtail admin → Streams → Block Categories exists and is functional
4. `GET /api/streams/v1/block-categories/` returns `{"items": [], "total": 0}`
5. Create a category, assign it to a block via the API, confirm `GET /api/streams/v1/blocks/{block_id}/categories/` returns it
6. MCP tools are registered and callable
