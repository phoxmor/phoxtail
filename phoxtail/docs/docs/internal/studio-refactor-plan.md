# Stream Studio Refactor Plan

> **Status: Completed.** All steps below have been implemented. This document is retained as historical context for the design decisions. See [Studio Architecture](../engine/streams/studio-architecture.md) for the current documentation.

## Context

The Studio was built before a major refactor that moved all presentation (HTML/CSS/JS) out of the `Block` model and into `BlockVariant`. Previously, Block carried a "default" appearance directly, creating a dual source of truth. Now **all** appearance lives in variants, and every block is expected to have a default variant (the ground state).

The original Studio split its UI into two workflows — "Create" (generate a new variant from a block's default variant) and "Edit" (refine an existing variant). This distinction was enforced at the form level via `WORKFLOW_CHOICES` and the `_requires_variant` field on `BlockSystemPrompt`, which filtered which prompts appeared in each workflow.

Post-refactor, this split is artificial. Both workflows receive the same four context variables (`block`, `collection`, `variant`, `references`), and all existing prompt templates already use this same interface. The **prompt template's wording** defines the AI's purpose (generate, refine, audit, fix, etc.) — the form just assembles context. The workflow toggle, the `_requires_variant` field, and the separate `block` form field are unnecessary complexity.

This refactor simplifies Studio to a single flat form where the system prompt defines purpose and the user's field selections define context.

### Related documentation

- [Dynamic Blocks Architecture](../engine/streams/dynamic-blocks-architecture.md) — core system design; sections on `BlockSystemPrompt` and AI workflow need updating
- [Studio Architecture](../engine/streams/studio-architecture.md) — current Studio docs; will be rewritten
- [Design Tokens Architecture](../engine/design/design-tokens-architecture.md) — `VariantCollection.template` renders design tokens (palettes, fonts) for AI context
- [Single Select Search Widget](../engine/streams/single-select-search-widget.md) — pattern used by all Studio form fields
- [Multi Select Chips Widget](../engine/streams/multi-select-chips-widget.md) — pattern used by the references field
- [Permissions](../engine/core/permissions.md) — `access_stream_studio` permission; Studio views use `StreamsPermissionMixin` and `@streams_permission_required`
- [Modal System](../engine/core/modal.md) — Studio's slide-right context modal follows this system
- [Performance](../engine/streams/performance.md) — cache invalidation signals on Block/BlockVariant; relevant if Studio gains direct save in future

---

## Design Principles

### The form is a context provider, not a workflow controller

Studio's form assembles four context variables that every prompt template can use:

| Variable | Source |
|----------|--------|
| `block` | Derived from `variant.block` — never selected directly |
| `variant` | User selects any variant (default or otherwise) |
| `collection` | Auto-populated from `variant.collection`, user can override |
| `references` | Optional, filtered by selected collection |

The **system prompt template** defines what the AI does with this context. A "Variant Generator" prompt says "generate a NEW variant." A "Variant Refiner" says "refine and improve." A future "Variant Auditor" might say "find accessibility issues." The form doesn't need to know.

### User intent is expressed through selections

The combination of prompt + variant + collection communicates intent:

| Scenario | System Prompt | Variant | Collection |
|----------|--------------|---------|------------|
| Generate from ground state | Variant Generator | default variant | changed to target collection |
| Refine existing variant | Variant Refiner | the variant to refine | kept (auto-populated) |
| Cross-collection redesign | Variant Generator | any variant | changed to different collection |
| Audit a variant (future) | Variant Auditor | the variant to audit | kept |
| Fix a variant (future) | Variant Fixer | the variant to fix | kept |

No workflow toggle is needed. The form is the same in every case.

### Collection auto-population

When the user selects a variant, the collection field auto-populates to `variant.collection`. This handles the common case (working within the variant's own design system) with zero friction. If the user then changes the collection, they're signaling a cross-collection intent — the AI receives the variant's code as structural reference but the new collection's design tokens as the design direction.

---

## Step 1: Remove `_requires_variant` from `BlockSystemPrompt`

**File:** `streams/models.py`

The `_requires_variant` field exists solely to split the prompt dropdown between Create and Edit workflows. Since we're eliminating workflows, the field and all its supporting code must go.

Remove:

- The `_requires_variant` BooleanField (line 359)
- The `_detect_variant_usage()` method (lines 399-425)
- The `save()` override that calls `_detect_variant_usage()` (lines 383-386)
- The `search_fields` entry `index.FilterField("_requires_variant")` (line 372)

Update the `template` field's `help_text` (line 348) — it currently says `"variant is None for creation tasks"`. Since variant is now always provided, update to:

```python
template = models.TextField(
    help_text=_(
        "System prompt template using Django Template "
        "Language. Available context: {{ block }}, "
        "{{ collection }}, {{ variant }}, "
        "{{ references }}. All variables are always "
        "provided. references is a list (may be empty)."
    )
)
```

**Migration:** Generate a migration to drop the `_requires_variant` column. This is a straightforward `RemoveField`.

---

## Step 2: Simplify `BlockSystemPrompt.render()` signature

**Current:**

```python
def render(self, block, collection, variant=None, references=None) -> str:
```

**New:**

```python
def render(self, variant=None, collection=None, references=None) -> str:
    context = Context({
        "block": variant.block if variant else None,
        "collection": collection,
        "variant": variant,
        "references": references or [],
    })
    return Template(self.template).render(context)
```

`block` is no longer a parameter — it's derived from `variant.block`. This makes the interface match reality: the form provides a variant, and everything else flows from it.

---

## Step 3: Remove `WORKFLOW_CHOICES` and eliminate workflow concept

**File:** `streams/constants.py`

Delete the entire `WORKFLOW_CHOICES` class. There are no workflows — just a flat form.

---

## Step 4: Rewrite `StudioContextForm`

**File:** `streams/forms.py`

The form simplifies dramatically. No workflow field, no block field, no conditional field configuration.

**Fields:**

```python
class StudioContextForm(forms.Form):
    system_prompt = SingleSelectSearchField(
        queryset=BlockSystemPrompt.objects.all(),
        required=True,
        label=_("System Prompt"),
        help_text=_("AI prompt template"),
    )

    variant = SingleSelectSearchField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        required=True,
        label=_("Variant"),
        help_text=_("The variant to work with (block is derived automatically)"),
    )

    collection = SingleSelectSearchField(
        queryset=VariantCollection.objects.all(),
        required=True,
        label=_("Collection"),
        help_text=_(
            "Design system to follow. Auto-populated from variant, "
            "change to apply a different collection's design direction."
        ),
    )

    references = MultiSelectChipsField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("References"),
        help_text=_(
            "Select existing variants as design inspiration. "
            "Filtered by the selected collection."
        ),
    )
```

**Remove entirely:**

- `workflow` field
- `block` field
- `_get_workflow()` method
- `_configure_for_workflow()` method
- `_set_system_prompt_queryset()` method

**Simplify `__init__`:**

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self._set_references_queryset()
```

**Simplify `_set_references_queryset()`:**

The references filter by collection. If the user has selected a collection, show variants from that collection (excluding the selected variant itself). If no collection yet, show none.

```python
def _set_references_queryset(self):
    collection = None
    variant_to_exclude = None

    if self.is_bound:
        collection_id = self.data.get("collection")
        if collection_id:
            try:
                collection = VariantCollection.objects.get(pk=collection_id)
            except VariantCollection.DoesNotExist:
                pass

        variant_id = self.data.get("variant")
        if variant_id:
            variant_to_exclude = variant_id

    queryset = BlockVariant.objects.select_related("block", "collection")

    if collection:
        queryset = queryset.filter(collection=collection)
        if variant_to_exclude:
            queryset = queryset.exclude(pk=variant_to_exclude)
    else:
        queryset = BlockVariant.objects.none()

    self.fields["references"].queryset = queryset

    # Sanitize submitted references against current queryset
    if self.is_bound:
        submitted_refs = self.data.getlist("references")
        if submitted_refs:
            valid_pks = set(str(pk) for pk in queryset.values_list("pk", flat=True))
            sanitized = [r for r in submitted_refs if r in valid_pks]
            if len(sanitized) != len(submitted_refs):
                data = self.data.copy()
                data.setlist("references", sanitized)
                self.data = data
```

**Simplify `clean()`:**

No workflow-dependent clearing needed. All fields have straightforward requirements.

```python
def clean(self):
    return super().clean()
```

**Simplify `get_rendered_prompt()`:**

```python
def get_rendered_prompt(self):
    if not self.is_valid():
        return None

    system_prompt = self.cleaned_data.get("system_prompt")
    variant = self.cleaned_data.get("variant")
    collection = self.cleaned_data.get("collection")
    references = self.cleaned_data.get("references", [])

    if not (system_prompt and variant and collection):
        return None

    return system_prompt.render(
        variant=variant,
        collection=collection,
        references=list(references) if references else [],
    )
```

---

## Step 5: Update views

**File:** `streams/views.py`

**Simplify `_get_studio_form()`:**

No workflow parameter. The form is always the same.

```python
def _get_studio_form(request):
    form_fields = ("system_prompt", "variant", "collection", "references")
    has_form_data = any(request.GET.get(k) for k in form_fields)
    if has_form_data:
        return StudioContextForm(request.GET)
    else:
        return StudioContextForm()
```

**Simplify `_studio_form_state_context()`:**

Remove `workflow_value` and `block_value`. Add nothing — just remove what's no longer needed.

```python
def _studio_form_state_context(form):
    return {
        "system_prompt_value": form["system_prompt"].value(),
        "variant_value": form["variant"].value(),
        "collection_value": form["collection"].value(),
        "rendered_prompt": (form.get_rendered_prompt() if form.is_bound else None),
    }
```

**Search views:**

- Remove `StudioSearchBlockView` entirely (no block field in form).
- `StudioSearchVariantView` gains collection auto-population behavior (see Step 7).
- `StudioSearchCollectionView` and `StudioSearchReferencesView` remain, updated for the simplified context.
- All search views' `hx_include` becomes `"#context-parent-fields, #references-selected-values"` (unchanged).

---

## Step 6: Update prompt templates

**File:** `streams/management/data/prompts/variant_generator.md`

The `variant_generator` currently references the ground state via `{{ block.default_variant.html }}`, `{{ block.default_variant.css }}`, `{{ block.default_variant.javascript }}` (lines 121-137). Update to use `{{ variant.html }}`, `{{ variant.css }}`, `{{ variant.javascript }}`.

The "Ground State (Reference Implementation)" section becomes:

```django
{% if variant %}
Study this reference implementation carefully. You MUST preserve all
DTL rendering logic while changing only the visual design.

### HTML Template
```django
{{ variant.html|minify }}
```
...
{% else %}
No reference variant available. Create your variant based solely on the
field schema above and the design collection guidelines below.
{% endif %}
```

**File:** `streams/management/data/prompts/variant_refiner.md`

Already uses `{{ variant.* }}` — no functional changes needed. Review for consistency with the generator's structure.

Both prompts now share the exact same context interface: `{{ block }}` (derived from variant), `{{ collection }}`, `{{ variant }}`, `{{ references }}`.

**Note:** The `minify` template filter (`templatetags/stream_studio_tags.py`) is unaffected — it works on any string input.

---

## Step 7: Update Studio templates

### `modal_content.html` — Remove workflow toggle

The workflow selector tabs are eliminated entirely. The form content renders directly.

**Current:**
```html
<div class="stu-workflow-tabs">
    <button ... hx-vals='{"workflow": "create"}' ...>Create</button>
    <button ... hx-vals='{"workflow": "edit"}' ...>Edit</button>
</div>
<form id="context-form">
    {% include 'form_content.html' %}
</form>
```

**New:**
```html
<form id="context-form">
    {% include 'form_content.html' %}
</form>
```

### `form_content.html` — Flat field layout

No workflow conditionals. All fields are always visible.

**Current:**
```html
{% if form.workflow.value == 'create' %}
    {# block + collection fields #}
{% else %}
    {# variant field #}
{% endif %}
```

**New:**
```html
<div id="context-parent-fields" class="stu-form-grid">
    {% include 'single_select_search.html' with field=form.system_prompt ... %}
    {% include 'single_select_search.html' with field=form.variant ... %}
    {% include 'single_select_search.html' with field=form.collection ... %}
</div>
<div id="references-container" class="stu-form-grid">
    {% if form.collection.value %}
        {% include 'multi_select_chips.html' with field=form.references ... %}
    {% else %}
        {% include 'multi_select_chips.html' with ... is_active=False search_placeholder="Select a collection first..." %}
    {% endif %}
</div>
```

### `variant_search_response.html` — Auto-populate collection

When a variant is selected, the OOB response now also updates the collection widget to the variant's collection. This is the key UX enhancement: selecting a variant auto-fills collection, but the user can change it afterwards.

The `StudioSearchVariantView.get_extra_context()` already has access to the form. When the variant is selected, it should also pass the variant's collection for the OOB update. The template adds an OOB swap for the collection widget.

### All 5 search response templates — Simplify hidden inputs

Remove the `workflow` and `block` hidden inputs from the `#context-form-placeholder` OOB sync. The hidden inputs become:

```html
<div hx-swap-oob="innerHTML:#context-form-placeholder">
    <input type="hidden" name="system_prompt" value="{{ system_prompt_value|default:'' }}">
    <input type="hidden" name="variant" value="{{ variant_value|default:'' }}">
    <input type="hidden" name="collection" value="{{ collection_value|default:'' }}">
</div>
```

---

## Step 8: Update ViewSet URL patterns

**File:** `streams/viewsets.py`

Remove the `search_block` URL pattern from `StudioViewSet.get_urlpatterns()` since the block search view is removed.

---

## Step 9: Update documentation

**`docs/engine/streams/studio-architecture.md`** — Rewrite to reflect:
- Single flat form architecture (no workflows)
- The "form is a context provider" principle
- System prompt defines purpose, selections define context
- Collection auto-population from variant
- Updated file structure
- Updated ViewSet URL patterns
- Updated form field descriptions

**`docs/engine/streams/dynamic-blocks-architecture.md`** — Update sections:
- Section 4 "BlockSystemPrompt Model": remove `_requires_variant`, update `render()` signature to `render(self, variant=None, collection=None, references=None)` with block derived from variant
- Section "BlockSystemPrompt: Database-Driven AI Prompts": update example render call and AI workflow steps
- File reference table: mentions `CollectionPalette` and `CollectionFontFamily` which don't exist — these were replaced by the `VariantCollection.template` approach. Clean up to match reality.

---

## Step 10: Migration

Generate a single migration that:
1. Removes the `_requires_variant` field from `BlockSystemPrompt`

This is the only schema change. All other changes are code-only.

---

## File summary

| File | Change |
|------|--------|
| `streams/constants.py` | Delete `WORKFLOW_CHOICES` entirely |
| `streams/models.py` | Remove `_requires_variant` field, `_detect_variant_usage()`, `save()` override, search_fields entry; update `template` help_text; change `render()` to derive block from variant |
| `streams/forms.py` | Remove `workflow` field, `block` field, `_get_workflow()`, `_configure_for_workflow()`, `_set_system_prompt_queryset()`; simplify `_set_references_queryset()`, `clean()`, `get_rendered_prompt()`; set system_prompt queryset to `.all()` |
| `streams/views.py` | Remove workflow param from `_get_studio_form()`; remove `workflow_value`/`block_value` from `_studio_form_state_context()`; remove `StudioSearchBlockView`; add collection auto-population to `StudioSearchVariantView` |
| `streams/viewsets.py` | Remove `search_block` URL pattern |
| `streams/management/data/prompts/variant_generator.md` | Replace `block.default_variant.*` with `variant.*` |
| `streams/management/data/prompts/variant_refiner.md` | Review for consistency (already uses `variant.*`) |
| `templates/.../modal_content.html` | Remove workflow toggle tabs |
| `templates/.../form_content.html` | Remove workflow conditional, flat field layout |
| `templates/.../*_search_response.html` | Remove `workflow`/`block` hidden inputs; variant response adds collection OOB update |
| `docs/.../studio-architecture.md` | Rewrite for single-form architecture |
| `docs/.../dynamic-blocks-architecture.md` | Update BlockSystemPrompt sections and file reference table |
| New migration | `RemoveField` for `_requires_variant` on `BlockSystemPrompt` |

---

## Out of scope

### Create Block workflow

Creating new blocks (schema + default variant) is a fundamentally different process that requires schema block knowledge, structural decisions about field types and nesting, and understanding of block patterns. This is a separate tool/workflow, not a Studio concern. It may be revisited as a dedicated interface in the future.
