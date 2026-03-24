# Studio: AI-Powered Variant Design Interface

## Overview

Studio is a custom Wagtail admin view that provides an interface for designing and refining BlockVariants using AI assistance. It enables users to generate system prompts dynamically, interact with AI models, and preview results in real-time.

## Vision

The Studio bridges the gap between the database-driven block system and AI-powered design generation. Rather than manually writing HTML/CSS/JS for each variant, users can:

1. Select the appropriate context (Block/Variant, Collection, SystemPrompt)
2. Generate a complete system prompt that includes all relevant schema and design system information
3. Interact with an AI to iteratively design the variant
4. Preview the generated code in real-time
5. Save the result directly to the database as a new or updated BlockVariant

---

## Architecture

### Integration with Streams App

Studio lives within the `streams` app and is registered as part of the `StreamsViewSetGroup`:

```
Streams (Menu Group)
├── Blocks
├── Collections
├── Variants
├── Prompts
└── Studio  ← Custom ViewSet
```

### File Structure

```
streams/
├── constants.py          # WORKFLOW_CHOICES (TextChoices)
├── forms.py              # StudioContextForm
├── views.py              # Studio view functions
├── viewsets.py           # StudioViewSet + other SnippetViewSets
├── wagtail_hooks.py      # StreamsViewSetGroup registration
└── templates/streams/studio/
    ├── index.html                    # Main page (extends wagtailadmin/base.html)
    └── partials/
        ├── header.html               # Page header with context button
        ├── studio.html       # Prompt output panel
        └── forms/context/
            ├── modal.html            # Slide-right modal wrapper
            ├── modal_content.html    # Workflow selector + form
            ├── form_content.html     # Form fields
            └── response.html         # HTMX OOB response
```

### ViewSet Structure

Studio uses a custom `ViewSet` (not `SnippetViewSet`) with its own views and URL patterns:

```python
# streams/viewsets.py
class StudioViewSet(ViewSet):
    name = "studio"
    icon = "stylus-brush"
    menu_label = "Studio"
    menu_order = 300

    def get_urlpatterns(self):
        return [
            path("", studio_index_view, name="index"),
            path("context/", studio_context_modal_view, name="context_modal"),
            path("context/apply/", studio_apply_context_view, name="apply_context"),
        ]
```

---

## Phase 1: Context Selection & Prompt Generation (MVP) ✅

**Goal:** Allow users to select context and generate a system prompt for copy/paste to external AI.

### Unified Form Architecture

A single `StudioContextForm` handles both workflows with dynamic field configuration:

```python
# streams/constants.py
class WORKFLOW_CHOICES(models.TextChoices):
    CREATE = "create", _("Create Variant")
    EDIT = "edit", _("Edit Variant")

# streams/forms.py
class StudioContextForm(forms.Form):
    workflow = forms.ChoiceField(choices=WORKFLOW_CHOICES.choices, widget=HiddenInput)
    system_prompt = forms.ModelChoiceField(...)  # Dynamic queryset based on workflow
    block = forms.ModelChoiceField(...)          # Required for CREATE
    variant = forms.ModelChoiceField(...)        # Required for EDIT
    collection = forms.ModelChoiceField(...)     # Required for CREATE only
```

**Key behaviors:**
- `__init__` configures field requirements and querysets based on workflow
- `system_prompt` queryset filters by `_requires_variant` flag
- Edit workflow derives `block` and `collection` from selected `variant`
- `clean()` enforces mutual exclusivity (clears unused fields)

### Workflow Comparison

| Field | Create Workflow | Edit Workflow |
|-------|-----------------|---------------|
| System Prompt | Required (`_requires_variant=False`) | Required (`_requires_variant=True`) |
| Block | Required | Derived from variant |
| Variant | Not shown | Required |
| Collection | Required | Derived from variant |

### User Interface

**Modal Style:** Slide-in panel from right (`data-modal-animation="slide-right"`)

**User Flow:**
```
1. User navigates to Streams → Studio
2. Clicks "Context" button → Modal slides in from right
3. Selects workflow (Create/Edit) via toggle buttons
4. Create: Chooses SystemPrompt → Block → Collection
   Edit: Chooses SystemPrompt → Variant (block/collection derived)
5. System prompt renders in real-time on main panel
6. User copies prompt and uses in external AI
7. User manually creates/updates BlockVariant with AI output
```

### HTMX Integration

All interactions use `hx-swap="none"` with OOB (Out-of-Band) swaps:

```html
<!-- response.html -->
<div hx-swap-oob="innerHTML:#context-modal-content">
    {% include 'modal_content.html' %}
</div>
<div hx-swap-oob="innerHTML:#studio-main">
    {% include 'studio.html' %}
</div>
```

This pattern ensures:
- Modal form updates with validation state
- Main content updates with rendered prompt
- Consistent behavior for workflow toggles and field changes

### View Functions

```python
def _get_studio_form(request):
    """Create form - unbound if no data, bound if user selecting."""
    workflow = request.GET.get("workflow", WORKFLOW_CHOICES.CREATE)
    form_fields = ("system_prompt", "block", "variant", "collection")
    has_form_data = any(request.GET.get(k) for k in form_fields)

    if has_form_data:
        return StudioContextForm(request.GET)
    return StudioContextForm(initial={"workflow": workflow})

def studio_index_view(request):
    """Main Studio interface."""
    form = _get_studio_form(request)
    rendered_prompt = form.get_rendered_prompt() if form.is_bound else None
    return render(request, "studio/index.html", {"form": form, "rendered_prompt": rendered_prompt})

def studio_context_modal_view(request):
    """HTMX: Render context modal."""
    return render(request, "context/modal.html", {"form": _get_studio_form(request)})

def studio_apply_context_view(request):
    """HTMX: Apply context, return OOB updates for modal + main content."""
    form = _get_studio_form(request)
    rendered_prompt = form.get_rendered_prompt() if form.is_bound else None
    return render(request, "context/response.html", {"form": form, "rendered_prompt": rendered_prompt})
```

---

## Phase 2: Integrated Chat Interface

**Status:** Not yet implemented

**Planned features:**
- Embedded AI chat within Studio
- Real-time code preview
- Direct save to BlockVariant model
