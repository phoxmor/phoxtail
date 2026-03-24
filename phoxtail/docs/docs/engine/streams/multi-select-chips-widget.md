# Multi-Select Chips Widget

A reusable HTMX-powered widget for selecting multiple items from a model queryset. Features a searchable dropdown with selected items displayed as clickable rows.

## Visual Layout

```
┌─────────────────────────────────────────────┐
│ Search...                                   │  <- Search bar (focus to show dropdown)
├─────────────────────────────────────────────┤
│ Option A                                    │  <- Dropdown (appears on focus)
│─────────────────────────────────────────────│
│ Option B                                    │
│─────────────────────────────────────────────│
│ Option C                                    │
└─────────────────────────────────────────────┘

After selecting items:

┌─────────────────────────────────────────────┐
│ Search...                                   │
└─────────────────────────────────────────────┘
│ Selected A                                  │  <- Click anywhere on row to deselect
│─────────────────────────────────────────────│
│ Selected B                                  │
```

## Architecture Overview

The widget consists of **2 layers**:

1. **Template Layer** - Django templates that render the UI (pure presentation)
2. **View Layer** - A generic CBV (`MultiSelectChipsSearchView` in `core/views.py`) handles all HTMX requests (search/add/remove) using Wagtail's search backend. New usages subclass it with only the app-specific parts.

A custom form field (`MultiSelectChipsField` in `core/fields.py`) provides **self-derivation**: its bound field exposes `.selected_items` and `.available_items` as properties. Templates access these directly from the field on initial render, so views don't need to compute and pass item lists. Only the search view passes explicit items (using Wagtail's search backend for filtered results).

### File Structure

```
core/
├── fields.py                                 # MultiSelectChipsField + MultiSelectChipsBoundField
├── views.py                                  # MultiSelectChipsSearchView generic CBV
└── templates/core/forms/widgets/htmx/
    ├── multi_select_chips.html               # Main widget (label + container)
    └── multi_select_chips/
        ├── compact_input.html                # The actual widget UI (search + dropdown + selected)
        └── results_content.html              # Dropdown results (swapped during search)
```

---

## How It Works

### 1. Initial Render

Use `MultiSelectChipsField` in the form — the field auto-derives `selected_items` and `available_items` from its queryset and current value. Include the widget with just `field` and `search_url`:

```django
{% include 'core/forms/widgets/htmx/multi_select_chips.html' with
    field=form.my_field
    search_url=search_url
    item_template="myapp/widgets/my_item_display.html"
    hx_include="#my-other-fields"
%}
```

By default, items render using `{{ item }}` (`__str__`). For rich display, pass an `item_template` — a small template that receives `item` and renders model-specific content (name, subtitle, images, etc.). The `item_template` is used for both dropdown items and selected items.

### 2. User Interaction Flow

1. **Focus searchbar** -> JavaScript shows dropdown with available items
2. **Type to search** -> HTMX request filters available items (300ms debounce)
3. **Click a dropdown item** -> HTMX request adds item to selection, returns updated widget
4. **Click a selected item** -> HTMX request removes item from selection, returns updated widget

### 3. HTMX Request Handling

All interactions (search/add/remove) hit the same endpoint. The view detects the action from request parameters:

- `{widget_id}_search` - Search query text
- `{widget_id}_add` - PK of item to add
- `{widget_id}_remove` - PK of item to remove
- `{field.html_name}` - List of currently selected PKs (from hidden inputs)

### 4. Split Swap Architecture

Search and selection changes use different swap strategies to preserve input focus:

- **Search**: Swaps only the `#results` container (`innerHTML`), keeping the search input focused
- **Add/Remove**: Swaps the entire `#compact-input` container (`outerHTML`), refreshing the full widget state

---

## State Preservation with Modals

When using this widget inside a modal that can be opened/closed, state preservation requires special handling.

### The Problem

When a modal opens, it fetches content via HTMX. The hidden form placeholder on the main page holds the current selections, but passing multi-value parameters (like multiple `references`) to the modal content URL can lose values if not handled correctly.

### The Solution

The `_build_modal_context` function in `core/views.py` uses `getlist()` to preserve all values:

```python
# CORRECT: Preserves multi-value parameters
params = {key: request.GET.getlist(key) for key in request.GET.keys()}

# WRONG: Only keeps one value per key
params = dict(request.GET.items())  # Don't do this!
```

### Hidden Form Placeholder Pattern

On the main page, include a hidden form placeholder that holds all form state:

```django
<div id="context-form-placeholder" class="hidden">{{ form }}</div>
```

When opening the modal, include this placeholder in the HTMX request:

```django
<button hx-get="{{ modal_url }}"
        hx-include="#context-form-placeholder"
        hx-target="#modal-wrapper">
    Open Modal
</button>
```

### OOB Updates for Real-Time Sync

When the widget updates (add/remove items), use OOB swaps to sync both:
1. The hidden form placeholder (for state persistence)
2. Any dependent UI (like a rendered prompt)

Example from `references_search_response.html`:

```django
{# Primary response: update the widget #}
{% include 'core/forms/widgets/htmx/multi_select_chips/compact_input.html' %}

{# OOB update: sync hidden form placeholder #}
<div hx-swap-oob="innerHTML:#context-form-placeholder">
    <input type="hidden" name="workflow" value="{{ workflow_value|default:'' }}">
    <input type="hidden" name="system_prompt" value="{{ system_prompt_value|default:'' }}">
    {% for pk in selected_pks %}<input type="hidden" name="references" value="{{ pk }}">{% endfor %}
</div>

{# OOB update: re-render dependent UI #}
<div hx-swap-oob="innerHTML:#prompt-output">
    {% include 'path/to/prompt_output.html' %}
</div>
```

---

## Implementation Guide

To implement this widget for a new model, you need **3 things**:

### Step 1: Use `MultiSelectChipsField` in the Form

```python
# myapp/forms.py
from core.fields import MultiSelectChipsField

class MyForm(forms.Form):
    my_field = MultiSelectChipsField(
        queryset=MyModel.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("My Items"),
    )
```

The field's bound field auto-exposes `.selected_items` and `.available_items` — no view computation needed for initial render.

### Step 2: Create the Search View

Subclass `MultiSelectChipsSearchView` from `core/views.py`. The generic CBV handles all the search/add/remove boilerplate — you only provide configuration and app-specific overrides.

**Minimal example** (3 required attributes):

```python
# myapp/views.py
from core.views import MultiSelectChipsSearchView
from .forms import MyForm

class MyFieldSearchView(MultiSelectChipsSearchView):
    form_class = MyForm
    field_name = "my_field"
    search_url_name = "myapp:my_field_search"
```

This gives you working search, add, and remove with items rendered via `__str__()`. On selection change, the default `compact_input.html` template is returned (no OOB updates).

**Full example** (all options, with OOB updates):

```python
class MyFieldSearchView(MultiSelectChipsSearchView):
    form_class = MyForm
    field_name = "my_field"
    search_url_name = "myapp:my_field_search"

    # Optional attributes
    widget_id = "my_field"                                    # defaults to field_name
    item_template = "myapp/widgets/my_item_display.html"      # rich item rendering
    hx_include = "#my-parent-fields, #my_field-selected-values"
    oob_response_template = "myapp/widgets/my_search_response.html"

    def get_selected_items_queryset(self, model):
        """Customize queryset for selected items (e.g. select_related)."""
        return model.objects.select_related("category")

    def get_extra_context(self, form):
        """Extra context passed to oob_response_template on selection change."""
        return {
            "some_value": form["some_field"].value(),
        }
```

**Class attributes reference:**

| Attribute | Required | Default | Description |
|-----------|----------|---------|-------------|
| `form_class` | Yes | — | The form class to instantiate |
| `field_name` | Yes | — | Name of the `MultiSelectChipsField` on the form |
| `search_url_name` | Yes | — | URL name for `reverse()` (e.g. `"myapp:search"`) |
| `widget_id` | No | `field_name` | HTML ID prefix for the widget |
| `item_template` | No | `None` | Path to rich item display template |
| `hx_include` | No | `None` | CSS selector for extra fields to include in HTMX requests |
| `oob_response_template` | No | `None` | Template for selection-change responses with OOB updates. When `None`, returns `compact_input.html` |

**Override hooks:**

| Method | Default | Description |
|--------|---------|-------------|
| `get_form(data)` | `self.form_class(data)` | Build form from mutated QueryDict |
| `get_extra_context(form)` | `{}` | Additional context for OOB template |
| `get_selected_items_queryset(model)` | `model.objects.all()` | Base queryset for selected items (e.g. for `select_related`) |

Wire the URL with `permission_required` (since CBVs don't use the decorator directly):

```python
# myapp/urls.py
from wagtail.admin.auth import permission_required

path(
    "search/",
    permission_required("wagtailadmin.access_admin")(
        MyFieldSearchView.as_view()
    ),
    name="my_field_search",
)
```

### Step 3: Include Widget in Template

```django
{% include 'core/forms/widgets/htmx/multi_select_chips.html' with
    field=form.my_field
    search_url=my_search_url
    item_template="myapp/widgets/my_item_display.html"
    hx_include="#my-other-fields"
%}
```

No need to pass `selected_items` or `available_items` — the field derives them automatically.

### Step 4 (Optional): Create a Rich Item Template

```django
{# myapp/templates/myapp/widgets/my_item_display.html #}
<span class="flex flex-col flex-1 min-w-0">
    <span class="text-sm font-medium truncate">{{ item.name }}</span>
    <span class="text-xs text-neutral-500 truncate">{{ item.category.name }}</span>
</span>
```

This template is used for both dropdown items and selected items. Without it, items render as `{{ item }}` (`__str__`).

---

## Context Variables Reference

### Required Variables

| Variable | Type | Description |
|----------|------|-------------|
| `field` | BoundField | Form field (widget derives `widget_id` from it) |
| `search_url` | string | URL for the HTMX search endpoint |

### Optional Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `selected_items` | QuerySet | Auto-derived from field | Currently selected items (override for search view results) |
| `available_items` | QuerySet | Auto-derived from field | Items available for selection (override for search view results) |
| `widget_id` | string | `field.html_name` | Unique identifier (used for HTML IDs and request params) |
| `item_template` | string | `None` | Path to template for rich item rendering in both dropdown and selected list (receives `item` in context) |
| `hx_include` | string | `None` | CSS selector for additional fields to include in requests |
| `search_placeholder` | string | `"Search..."` | Placeholder text for search input |
| `search_value` | string | `""` | Current search query (for preserving state) |
| `show_label` | bool | `True` | Whether to show field label |
| `show_help_text` | bool | `True` | Whether to show help text tooltip |
| `is_active` | bool | `True` | Whether the widget is interactive (pass `False` to deactivate) |

---

## Request Parameters Reference

The search endpoint receives these GET parameters:

| Parameter | Description |
|-----------|-------------|
| `{widget_id}_search` | Search query text |
| `{widget_id}_add` | PK of item to add (when clicking dropdown item) |
| `{widget_id}_remove` | PK of item to remove (when clicking selected item) |
| `{field.html_name}` | List of currently selected PKs |
| Any fields from `hx_include` | Additional form data |

---

## Key Implementation Details

### Hidden Inputs for Form Submission

Selected items are stored in hidden inputs inside `#{widget_id}-selected-values`:

```html
<div id="mywidget-selected-values" class="hidden">
    <input type="hidden" name="my_field" value="1">
    <input type="hidden" name="my_field" value="2">
</div>
```

These are included in every HTMX request via `hx-include`.

### JavaScript Dropdown Behavior

The dropdown show/hide is handled client-side:

- **Show**: On input focus
- **Hide**: On input blur (with 150ms delay to allow clicking items)

### Custom Item Display with `item_template`

For rich item rendering, pass an `item_template` path. The template receives `item` in its context and can render any model-specific content:

```django
{# myapp/templates/myapp/widgets/my_item_display.html #}
<span class="flex flex-col flex-1 min-w-0">
    <span class="text-sm font-medium truncate">{{ item.name }}</span>
    <span class="text-xs text-neutral-500 truncate">{{ item.category.name }}</span>
</span>
```

The same template is used for both dropdown items and selected items. Dropdown items highlight on hover with a primary color, while selected items highlight with a red tint to signal removal.

---

## Troubleshooting

### Selected items not preserved when modal reopens

- Ensure `core/views.py` `_build_modal_context` uses `getlist()` for multi-value params
- Check that `hx-include` on the modal trigger includes the hidden form placeholder

### Dropdown doesn't appear

- Check that JavaScript is running (no console errors)
- Ensure `widget_id` is consistent across all usages

### Items don't get added/removed

- Verify the search URL is correct and matches `search_url_name` on the view
- Check that `hx_include` selector matches existing elements
- Ensure `widget_id` is consistent between the view class and template

### Dependent UI not updating

- Set `oob_response_template` on the view and add OOB swaps in that template
- Override `get_extra_context()` to pass required context (like `rendered_prompt`)

### Search not working

- Check that the model defines `search_fields` with `AutocompleteField` entries
- Verify `{widget_id}_search` is being read correctly in the view
- Ensure the search index is up to date (`./manage.py update_index`)
