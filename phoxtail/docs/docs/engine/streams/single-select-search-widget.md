# Single Select Search Widget

A reusable HTMX-powered widget for selecting a single item from a model queryset. Features a searchable dropdown that collapses into a selected-item display with a clear button.

## Visual Layout

```
Unselected state (search bar with dropdown):

┌─────────────────────────────────────────────┐
│ 🔍 Search...                                │  <- Search bar (focus to show dropdown)
├─────────────────────────────────────────────┤
│ Option A                                    │  <- Dropdown (appears on focus)
│─────────────────────────────────────────────│
│ Option B                                    │
│─────────────────────────────────────────────│
│ Option C                                    │
└─────────────────────────────────────────────┘

Selected state (item display with clear button):

┌─────────────────────────────────────────────┐
│ Selected Item Name                       ✕  │  <- Click ✕ to clear
└─────────────────────────────────────────────┘
```

## Architecture Overview

The widget consists of **2 layers**:

1. **Template Layer** - Django templates that render the UI (pure presentation)
2. **View Layer** - A generic CBV (`SingleSelectSearchView` in `core/views.py`) handles all HTMX requests (search/select/clear) using Wagtail's search backend. New usages subclass it with only the app-specific parts.

A custom form field (`SingleSelectSearchField` in `core/fields.py`) provides **self-derivation**: its bound field exposes `.selected_item` and `.available_items` as properties. Templates access these directly from the field on initial render, so views don't need to compute and pass item data. Only the search view passes explicit items (using Wagtail's search backend for filtered results).

### File Structure

```
core/
├── fields.py                                 # SingleSelectSearchField + SingleSelectSearchBoundField
├── views.py                                  # SingleSelectSearchView generic CBV
└── templates/core/forms/widgets/htmx/
    ├── single_select_search.html             # Main widget (label + container)
    └── single_select_search/
        ├── input.html                        # The actual widget UI (search bar OR selected item)
        └── results_content.html              # Dropdown results (swapped during search)
```

---

## How It Works

### 1. Initial Render

Use `SingleSelectSearchField` in the form — the field auto-derives `selected_item` and `available_items` from its queryset and current value. Include the widget with just `field` and `search_url`:

```django
{% include 'phoxtail_core/forms/widgets/htmx/single_select_search.html' with
    field=form.my_field
    search_url=search_url
    item_template="myapp/widgets/my_item_display.html"
    hx_include="#my-other-fields"
%}
```

By default, items render using `{{ item }}` (`__str__`). For rich display, pass an `item_template` — a small template that receives `item` and renders model-specific content. The `item_template` is used for both dropdown items and the selected item display.

### 2. User Interaction Flow

1. **Focus searchbar** -> JavaScript shows dropdown with available items
2. **Type to search** -> HTMX request filters available items (300ms debounce)
3. **Click a dropdown item** -> HTMX request selects item, widget switches to selected-item display
4. **Click clear (✕) button** -> HTMX request clears selection, widget switches back to search bar

### 3. HTMX Request Handling

All interactions (search/select/clear) hit the same endpoint. The view detects the action from request parameters:

- `{widget_id}_search` - Search query text
- `{widget_id}_select` - PK of item to select (when clicking dropdown item)
- `{widget_id}_clear` - Clear flag (when clicking ✕ button)
- `{field.html_name}` - Currently selected PK (from hidden input)

### 4. Split Swap Architecture

Search and selection changes use different swap strategies to preserve input focus:

- **Search**: Swaps only the `#results` container (`innerHTML`), keeping the search input focused
- **Select/Clear**: Swaps the entire `#container` (`innerHTML`), refreshing the full widget state (toggling between search bar and selected item)

---

## State Preservation with Modals

When using this widget inside a modal, the same patterns from the Multi-Select Chips Widget apply:

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

When the widget updates (select/clear), use OOB swaps to sync:
1. The hidden form placeholder (for state persistence)
2. Any dependent UI (like a rendered prompt)

Example from a search response template:

```django
{# Primary response: update the widget #}
{% include 'phoxtail_core/forms/widgets/htmx/single_select_search/input.html' %}

{# OOB update: sync hidden form placeholder #}
<div hx-swap-oob="innerHTML:#context-form-placeholder">
    <input type="hidden" name="workflow" value="{{ workflow_value|default:'' }}">
    <input type="hidden" name="my_field" value="{{ selected_item.pk|default:'' }}">
</div>

{# OOB update: re-render dependent UI #}
<div hx-swap-oob="innerHTML:#prompt-output">
    {% include 'path/to/prompt_output.html' %}
</div>
```

---

## Implementation Guide

To implement this widget for a new model, you need **3 things**:

### Step 1: Use `SingleSelectSearchField` in the Form

```python
# myapp/forms.py
from core.fields import SingleSelectSearchField

class MyForm(forms.Form):
    my_field = SingleSelectSearchField(
        queryset=MyModel.objects.all(),
        required=False,
        label=_("My Item"),
    )
```

The field's bound field auto-exposes `.selected_item` and `.available_items` — no view computation needed for initial render.

### Step 2: Create the Search View

Subclass `SingleSelectSearchView` from `core/views.py`. The generic CBV handles all the search/select/clear boilerplate — you only provide configuration and app-specific overrides.

**Minimal example** (3 required attributes):

```python
# myapp/views.py
from core.views import SingleSelectSearchView
from .forms import MyForm

class MyFieldSearchView(SingleSelectSearchView):
    form_class = MyForm
    field_name = "my_field"
    search_url_name = "myapp:my_field_search"
```

This gives you working search, select, and clear with items rendered via `__str__()`. On selection change, the default `input.html` template is returned (no OOB updates).

**Full example** (all options, with OOB updates):

```python
class MyFieldSearchView(SingleSelectSearchView):
    form_class = MyForm
    field_name = "my_field"
    search_url_name = "myapp:my_field_search"

    # Optional attributes
    widget_id = "my_field"                                    # defaults to field_name
    item_template = "myapp/widgets/my_item_display.html"      # rich item rendering
    hx_include = "#my-parent-fields, #my_field-selected-value"
    oob_response_template = "myapp/widgets/my_search_response.html"

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
| `field_name` | Yes | — | Name of the `SingleSelectSearchField` on the form |
| `search_url_name` | Yes | — | URL name for `reverse()` (e.g. `"myapp:search"`) |
| `widget_id` | No | `field_name` | HTML ID prefix for the widget |
| `item_template` | No | `None` | Path to rich item display template |
| `hx_include` | No | `None` | CSS selector for extra fields to include in HTMX requests |
| `oob_response_template` | No | `None` | Template for selection-change responses with OOB updates. When `None`, returns `input.html` |

**Override hooks:**

| Method | Default | Description |
|--------|---------|-------------|
| `get_form(data)` | `self.form_class(data)` | Build form from mutated QueryDict |
| `get_extra_context(form)` | `{}` | Additional context for OOB template |

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
{% include 'phoxtail_core/forms/widgets/htmx/single_select_search.html' with
    field=form.my_field
    search_url=my_search_url
    item_template="myapp/widgets/my_item_display.html"
    hx_include="#my-other-fields"
%}
```

No need to pass `selected_item` or `available_items` — the field derives them automatically.

### Step 4 (Optional): Create a Rich Item Template

```django
{# myapp/templates/myapp/widgets/my_item_display.html #}
<span class="flex flex-col flex-1 min-w-0">
    <span class="text-sm font-medium truncate">{{ item.name }}</span>
    <span class="text-xs text-neutral-500 truncate">{{ item.category.name }}</span>
</span>
```

This template is used for both dropdown items and the selected item display. Without it, items render as `{{ item }}` (`__str__`).

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
| `selected_item` | Model instance | Auto-derived from field | Currently selected item (override for search view results) |
| `available_items` | QuerySet | Auto-derived from field | Items available for selection (override for search view results) |
| `widget_id` | string | `field.html_name` | Unique identifier (used for HTML IDs and request params) |
| `item_template` | string | `None` | Path to template for rich item rendering in both dropdown and selected display (receives `item` in context) |
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
| `{widget_id}_select` | PK of item to select (when clicking dropdown item) |
| `{widget_id}_clear` | Clear flag (when clicking ✕ button) |
| `{field.html_name}` | Currently selected PK (from hidden input) |
| Any fields from `hx_include` | Additional form data |

---

## Key Implementation Details

### Hidden Input for Form Submission

The selected value is stored in a hidden input inside `#{widget_id}-selected-value`:

```html
<div id="mywidget-selected-value" class="hidden">
    <input type="hidden" name="my_field" value="42">
</div>
```

This is included in every HTMX request via `hx-include`.

### Two-State UI

Unlike the multi-select widget which always shows a search bar, the single-select toggles between two mutually exclusive states:

- **Unselected**: Search bar with dropdown (type to filter, click to select)
- **Selected**: Item display with clear button (click ✕ to return to search)

The entire `#container` swaps on select/clear, naturally transitioning between states.

### JavaScript Dropdown Behavior

The dropdown show/hide is handled client-side:

- **Show**: On input focus
- **Hide**: On input blur (with 150ms delay to allow clicking items)

### Search Value Leak Prevention

When the search input is inside a container that `hx-include` references (e.g. `#context-parent-fields`), its value leaks into select/clear requests. The view handles this by only applying search filtering for non-selection-change requests:

```python
if search_value and not selection_changed:
    s = get_search_backend()
    available_items = s.autocomplete(search_value, available_items)
```

---

## Troubleshooting

### Selected item not preserved when modal reopens

- Ensure `core/views.py` `_build_modal_context` uses `getlist()` for multi-value params
- Check that `hx-include` on the modal trigger includes the hidden form placeholder

### Dropdown doesn't appear

- Check that JavaScript is running (no console errors)
- Ensure `widget_id` is consistent across all usages

### Item doesn't get selected/cleared

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

### Widget shows stale data after select/clear

- The view delegates to `field.selected_item` and `field.available_items` — ensure the form is built with the mutated QueryDict (with the updated value)
- Check that `SingleSelectSearchField` (not plain `ModelChoiceField`) is used in the form
