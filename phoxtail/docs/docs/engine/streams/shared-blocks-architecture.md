# Shared Blocks Architecture

## Problem

The `Menu` and `Footer` models in `app/models.py` are site+locale-scoped content (defined once, shared across all pages). They need to be replaced by the dynamic block system, but:

- Blocks live inside a page's `body` StreamField — content is **per-page**
- Menus/footers need to be **per-site** — defined once, shared everywhere
- Editors shouldn't re-fill the same content on every page
- But editors **should** be able to choose different **variants** per page and place the block wherever they want in the StreamField

## Core Concept

A **shared block** separates content from presentation choice:

- **Content** is stored once at the site+locale level (in `SharedBlock`)
- **Variant selection** and **position** are per-page (in the page's StreamField)

In the page editor, a shared block appears like any other block — but with only a variant chooser, no content fields:

```
┌───────────────────────────────┐
│ Main Menu                     │
│                               │
│ Variant: [ Choose...  ▾ ]    │
└───────────────────────────────┘
```

The content comes from a separate admin record where it was filled once.

## Example

**Page A** — corporate landing page:
```
Body StreamField:
  [0] Main Menu       → variant: "Filled Background"
  [1] Hero Section    → ...
  [2] Features Grid   → ...
  [3] Site Footer     → variant: "Full Width"
```

**Page B** — video showcase page:
```
Body StreamField:
  [0] Main Menu       → variant: "Transparent Fixed"
  [1] Video Banner    → ...
  [2] Content Section → ...
  [3] Site Footer     → variant: "Minimal"
```

Both pages share the same menu and footer **content** (logo, links, CTA), but use different **variants** (visual styles). The menu on Page B uses a transparent variant that overlays the video banner below.

---

## Architecture Components

### 1. `Block.is_shared` Flag

A `BooleanField` on the existing `Block` model:

```python
class Block(models.Model):
    ...
    is_shared = BooleanField(default=False)
```

When `is_shared=True`:
- The factory generates a **lightweight block** for page StreamFields (variant chooser only)
- The block's content is expected to come from `SharedBlock`
- The block still appears in the page editor's block chooser (in a "Shared" group)

### 2. `SharedBlock` Model

Stores the filled content for shared blocks, scoped to site+locale:

```python
class SharedBlock(models.Model):
    block = ForeignKey(Block)        # Which shared block this content is for
    site = ForeignKey(Site)
    locale = ForeignKey(Locale)
    content = SchemaStreamField(     # Same StreamField experience as page body
        get_shared_blocks,
        max_num=1,
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=["block", "site", "locale"])
        ]
```

**Key design decisions:**

- `content` is a `SchemaStreamField` — admins get the **exact same editing UI** as page bodies (image choosers, list management, nested structs, etc.)
- `max_num=1` — one content record stores one filled block
- The FK to `Block` enables efficient lookup during rendering and enforces uniqueness
- Validation ensures the content's block type matches the FK

### 3. Factory: Three Generation Modes

The same Block schema generates different block classes depending on context:

| Mode | Function | Content Fields | Variant Chooser | Base Class | Used By |
|------|----------|---------------|-----------------|------------|---------|
| 1 (normal) | `create_block_from_schema` | Yes | Yes | `BlockVariantStructBlock` | Page StreamField (normal blocks) |
| 2 (shared ref) | `create_shared_block_ref` | **No** | Yes | `BlockVariantStructBlock` | Page StreamField (shared blocks) |
| 3 (shared edit) | `create_shared_block_from_schema` | Yes | **No** | `StructBlock` | SharedBlock StreamField |

**Mode 1** — Normal blocks in page StreamField (existing, unchanged):
```python
create_block_from_schema(block)
# → All content fields from schema + variant chooser
```

**Mode 2** — Shared blocks in page StreamField (new):
```python
create_shared_block_ref(block)
# → Only variant chooser, no content fields
# → Sets _is_shared=True on the class
# → Render fetches content from SharedBlock
```

**Mode 3** — Shared blocks in SharedBlock admin (new):
```python
create_shared_block_from_schema(block)
# → All content fields from schema, NO variant chooser
# → Uses plain StructBlock (no variant rendering logic)
```

**`build_dynamic_blocks` change:**
```python
for block_def in Block.objects.all():
    if block_def.is_shared:
        block_instance = create_shared_block_ref(block_def)      # mode 2
    else:
        block_instance = create_block_from_schema(block_def)     # mode 1
```

**New `build_shared_blocks`:**
```python
for block_def in Block.objects.filter(is_shared=True):
    block_instance = create_shared_block_from_schema(block_def)  # mode 3
```

### 4. Cache Layer

Two new caches in `streams/cache.py`:

**Shared block classes** (for SharedBlock StreamField):
```python
_shared_blocks_cache = None  # [(identifier, block_instance), ...]
# Cleared when Block is saved/deleted (same as _dynamic_blocks_cache)
```

**Shared block data** (for rendering):
```python
_shared_block_cache = {}  # (identifier, site_id, locale_id) → SharedBlock
# Cleared when SharedBlock is saved/deleted
```

### 5. Render Flow

`BlockVariantStructBlock.render()` handles shared blocks:

```
1. Check _is_shared flag
2. If shared:
   a. Get site from request, locale from page context
   b. Fetch SharedBlock from cache
   c. Extract content value from SharedBlock.content[0].value
   d. Use this as render_value (replaces page-level value for template context)
3. Get variant from page-level value (always from page, even for shared blocks)
4. Render variant template with render_value
```

**Template access is identical** — `{{ value.logo }}`, `{{ value.links }}`, etc. work the same whether the value came from a page's StreamField or from SharedBlock. The variant templates don't need to know or care.

### 6. Avoiding Circular Imports

The callable for SharedBlock's StreamField is defined in `streams/fields.py` (not `factory.py`) to avoid circular imports:

```
streams/models.py → streams/fields.py (import time, safe)
streams/fields.py → streams/cache.py (runtime only, via callable)
streams/cache.py → streams/blocks/factory.py (runtime only)
streams/blocks/factory.py → streams/models.py (runtime only, inside functions)
```

---

## Data Flow

### Setup (Admin, one-time)

```
1. Admin creates Block:
   ├─ name: "Main Menu"
   ├─ identifier: "main_menu"
   ├─ is_shared: True
   └─ schema: [logo, links list, cta_text, cta_link]

2. Admin creates variants:
   ├─ "Filled Background" (is_default: True)
   └─ "Transparent Fixed"

3. Admin creates SharedBlock:
   ├─ block: Main Menu
   ├─ site: mysite.com
   ├─ locale: English
   └─ content: [fills in logo, links, CTA using StreamField UI]
```

### Page Editing (Editor)

```
1. Editor opens page → clicks "Add block"
   └─ Sees "Main Menu" in the "Shared" group of block chooser

2. Adds Main Menu block:
   └─ Only sees variant chooser
   └─ Picks "Transparent Fixed"

3. Saves page
   └─ StreamField stores: [{"type": "main_menu", "value": {"variant": 8}}]
```

### Rendering (Page visit)

```
1. Wagtail renders page → encounters "main_menu" block

2. BlockVariantStructBlock.render() called:
   ├─ Detects _is_shared=True
   ├─ Gets site + locale from request/page context
   ├─ Fetches SharedBlock (cached) → extracts content value
   └─ Gets variant 8 = "Transparent Fixed"

3. Renders variant template with shared content:
   ├─ {{ value.logo }} → logo from SharedBlock
   ├─ {{ value.links }} → links from SharedBlock
   └─ CSS: position: fixed; background: transparent;

4. Returns rendered HTML + CSS + JS
```

---

## Admin UI

### SharedBlock editing

The admin fills shared block content using the same StreamField UI as page bodies:

```
┌──────────────────────────────────────────────┐
│ Shared Block                                 │
│                                              │
│ Block:  [ Main Menu ▾ ]                      │
│ Site:   [ mysite.com ▾ ]                     │
│ Locale: [ English ▾ ]                        │
│                                              │
│ Content:                                     │
│ ┌──────────────────────────────────────────┐ │
│ │ Main Menu                                │ │
│ │                                          │ │
│ │ Logo: [Choose an image]                  │ │
│ │ Links:                                   │ │
│ │   [0] Label: "Products"  Page: [▾]      │ │
│ │   [1] Label: "About"     Page: [▾]      │ │
│ │   [+ Add item]                           │ │
│ │ CTA Text: "Get Started"                  │ │
│ │ CTA Link: [Choose a page]               │ │
│ └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

### Page editing with shared block

```
┌──────────────────────────────────────────────┐
│ Body:                                        │
│ ┌──────────────────────────────────────────┐ │
│ │ Main Menu                      [Shared]  │ │
│ │                                          │ │
│ │ Variant: [ Transparent Fixed ▾ ]         │ │
│ └──────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────┐ │
│ │ Video Banner                             │ │
│ │ ...normal fields...                      │ │
│ └──────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## File Reference

| File | Changes |
|------|---------|
| `streams/models.py` | Add `is_shared` to Block, add `SharedBlock` model |
| `streams/fields.py` | Add `get_shared_blocks` callable and `SharedBlockStreamField` |
| `streams/blocks/factory.py` | Add `create_shared_block_from_schema`, `create_shared_block_ref`, `build_shared_blocks`; modify `build_dynamic_blocks` |
| `streams/cache.py` | Add shared block caches (`_shared_blocks_cache`, `_shared_block_cache`) |
| `streams/blocks/base.py` | Handle `_is_shared` in `__init__` and `render` |
| `streams/signals.py` | Add `SharedBlock` save/delete signal connections |
| `streams/viewsets.py` | Add `SharedBlockViewSet` |
| `streams/wagtail_hooks.py` | Register `SharedBlockViewSet` in `StreamsViewSetGroup` |
