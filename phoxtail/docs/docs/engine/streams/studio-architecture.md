# Studio: AI-Powered Variant Design Interface

## Overview

Studio is a custom Wagtail admin view that provides an interface for designing and refining BlockVariants using AI assistance. Users select context (variant, collection, system prompt, optional references), generate a complete system prompt, and copy it to an external AI for iterative design work.

## Design Principles

### The form is a context provider, not a workflow controller

Studio's form assembles four context variables that every prompt template can use:

| Variable | Source |
|----------|--------|
| `block` | Derived from `variant.block` — never selected directly |
| `variant` | User selects any variant (default or otherwise) |
| `collection` | Auto-populated from `variant.collection`, user can override |
| `references` | Optional, filtered by selected collection |

The **system prompt template** defines what the AI does with this context. A "Variant Generator" prompt says "generate a NEW variant." A "Variant Refiner" says "refine and improve." The form doesn't need to know — it just assembles context.

### User intent is expressed through selections

| Scenario | System Prompt | Variant | Collection |
|----------|--------------|---------|------------|
| Generate from ground state | Variant Generator | default variant | changed to target collection |
| Refine existing variant | Variant Refiner | the variant to refine | kept (auto-populated) |
| Cross-collection redesign | Variant Generator | any variant | changed to different collection |

### Collection auto-population

When the user selects a variant, the collection field auto-populates to `variant.collection`. If the user then changes the collection, they're signaling a cross-collection intent — the AI receives the variant's code as structural reference but the new collection's design tokens as design direction.

---

## Architecture

### Integration with Streams App

Studio lives within the `streams` app and is registered as part of the `StreamsViewSetGroup`:

```
Streams (Menu Group)
├── Blocks
├── Shared Blocks
├── Variants
├── Collections
├── System Prompts
└── Studio  ← Custom ViewSet
```

### File Structure

```
streams/
├── forms.py              # StudioContextForm
├── views.py              # Studio views (FBV + CBV search views)
├── viewsets.py           # StudioViewSet + SnippetViewSets
├── wagtail_hooks.py      # StreamsViewSetGroup registration
├── permissions/          # StreamsAdminPermission, permission policy
└── templates/phoxtail_streams/studio/
    ├── index.html                    # Main page (extends wagtailadmin/base.html)
    └── partials/
        ├── header.html               # Page header with context button
        ├── studio.html               # Hidden form placeholder + prompt output panel
        ├── prompt_output.html        # Rendered prompt display or empty state
        ├── quantum_waves.html        # Animated empty state placeholder
        └── forms/
            ├── context/
            │   ├── modal.html            # Slide-right modal wrapper
            │   ├── modal_content.html    # Form wrapper
            │   ├── form_content.html     # Search widget fields
            │   └── response.html         # HTMX OOB response (modal + main)
            └── widgets/
                ├── system_prompt_search_response.html   # OOB for system prompt select
                ├── variant_search_response.html         # OOB for variant select + collection auto-populate
                ├── collection_search_response.html      # OOB for collection select + references reset
                ├── references_search_response.html      # OOB for reference add/remove
                └── reference_item_display.html          # Rich display for reference items
```

### ViewSet Structure

Studio uses a `StreamsViewSet` (permission-aware `ViewSet`) with function-based views for page-level endpoints and class-based views for HTMX search widgets:

```python
# streams/viewsets.py
class StudioViewSet(StreamsViewSet):
    name = "studio"
    icon = "flowchart"
    menu_label = "Studio"
    menu_order = 600
    required_permissions = ["access_stream_studio"]

    def get_urlpatterns(self):
        return [
            path("", studio_index_view, name="index"),
            path("context-modal/", studio_context_modal_view, name="context_modal"),
            path("apply-context/", studio_apply_context_view, name="apply_context"),
            path("search/system-prompt/", StudioSearchSystemPromptView.as_view(), name="search_system_prompt"),
            path("search/collection/", StudioSearchCollectionView.as_view(), name="search_collection"),
            path("search/variant/", StudioSearchVariantView.as_view(), name="search_variant"),
            path("search/references/", StudioSearchReferencesView.as_view(), name="search_references"),
        ]
```

---

## Form Architecture

### StudioContextForm

A single flat form with four fields — no workflow toggle, no conditional field configuration:

```python
# streams/forms.py
class StudioContextForm(forms.Form):
    system_prompt = SingleSelectSearchField(
        queryset=BlockSystemPrompt.objects.all(),
        label=_("System Prompt"),
    )
    variant = SingleSelectSearchField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        label=_("Variant"),
    )
    collection = SingleSelectSearchField(
        queryset=VariantCollection.objects.all(),
        label=_("Collection"),
    )
    references = MultiSelectChipsField(
        queryset=BlockVariant.objects.select_related("block", "collection").all(),
        required=False,
        label=_("References"),
    )
```

**Key behaviors:**

- `__init__` calls `_set_references_queryset()` to filter references by the current collection
- References show variants from the selected collection, excluding the selected variant itself
- If no collection is selected, references queryset is empty
- Submitted reference PKs are sanitized against the current queryset (guards against stale selections when collection changes)
- `get_rendered_prompt()` validates the form and delegates to `system_prompt.render(variant, collection, references)`

### User Interface

**Modal Style:** Slide-in panel from right (via the core modal system)

**User Flow:**
```
1. User navigates to Streams → Studio
2. Clicks "Configure Context" button → Modal slides in from right
3. Selects SystemPrompt, Variant, Collection (auto-populated), and optional References
4. Each selection triggers HTMX search widget → OOB updates prompt output in real-time
5. User copies rendered system prompt to external AI
6. User creates/updates BlockVariant with AI output
```

### HTMX Integration

Studio uses two HTMX patterns:

**1. Apply Context (response.html)** — Full OOB swap of both modal content and main studio panel:
```html
<div hx-swap-oob="innerHTML:#context-modal-content">
    {% include 'modal_content.html' %}
</div>
<div hx-swap-oob="innerHTML:#studio-main">
    {% include 'studio.html' %}
</div>
```

**2. Search Widget Responses** — Each field has its own OOB response template that updates:
- The field's own search widget input
- The `#context-form-placeholder` hidden inputs (state sync)
- The `#prompt-output` panel (re-rendered prompt)
- Dependent fields where applicable (variant selection updates collection and references)

The hidden `#context-form-placeholder` div in `studio.html` maintains form state between the main page and modal. When the modal opens, `hx-include="#context-form-placeholder"` sends current selections. When a search widget fires, OOB swaps keep the placeholder in sync.

### View Functions

```python
def _get_studio_form(request):
    """Create form — unbound if no data, bound if any field present in GET."""
    form_fields = ("system_prompt", "variant", "collection", "references")
    has_form_data = any(request.GET.get(k) for k in form_fields)
    if has_form_data:
        return StudioContextForm(request.GET)
    return StudioContextForm()

def studio_index_view(request):
    """Main Studio interface."""
    form = _get_studio_form(request)
    rendered_prompt = form.get_rendered_prompt() if form.is_bound else None
    return render(request, "studio/index.html", {"form": form, "rendered_prompt": rendered_prompt})
```

### Search Views

All search views extend a shared base that provides permission checking, form instantiation, and consistent `hx_include`:

```python
class _StudioSingleSelectBase(StreamsPermissionMixin, SingleSelectSearchView):
    required_permissions = ["access_stream_studio"]
    form_class = StudioContextForm
    hx_include = "#context-parent-fields, #references-selected-values"

    def get_extra_context(self, form):
        return _studio_form_state_context(form)
```

Notable behavior in `StudioSearchVariantView`: when a variant is selected, `get_extra_context()` looks up the variant's collection and passes it as `auto_collection` — the template uses this for an OOB swap to auto-populate the collection field.

---

## Permissions

Studio uses the streams permission system:

- **Model:** `StreamsAdminPermission` with `access_stream_studio` permission
- **FBV decorator:** `@streams_permission_required("access_stream_studio")`
- **CBV mixin:** `StreamsPermissionMixin` with `required_permissions = ["access_stream_studio"]`

---

## Phase 2: Integrated Chat Interface

**Status:** Not yet implemented

**Planned features:**

- Embedded AI chat within Studio
- Real-time code preview
- Direct save to BlockVariant model
