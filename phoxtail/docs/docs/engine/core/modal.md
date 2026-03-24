# Modal System

This page documents the core modal system — a generic, HTMX-driven modal infrastructure used across the entire platform. All modals (admin drawers, filter panels, confirmation dialogs, public-facing overlays) use the same system.

---

## Overview

The modal system provides two levels of modals: a **base modal** and a **level 1 modal** (for nesting a modal on top of an existing one). Both work identically — content views are resolved server-side and delivered with the modal shell in a single HTTP request.

### Key Files

| File | Purpose |
|------|---------|
| `core/views.py` | Modal endpoint views and helper functions |
| `core/urls.py` | URL routing (`core:modal`, `core:modal_level_1`) |
| `core/templates/core/modal.html` | Base modal shell template |
| `core/templates/core/modal_level_1.html` | Nested modal shell template |
| `core/static/core/js/modal.js` | Close handlers, animation configuration, keyboard support |
| `core/static/core/css/modal.css` | Overlay and content animations |

---

## How It Works

### Single-Request Pattern

Opening a modal takes one HTTP request:

1. A button sends an HTMX `GET` to `core:modal` with a `content_url` parameter pointing to the actual content view.
2. The server resolves `content_url` internally using `django.urls.resolve()`, calls the content view function directly, and renders the modal shell (`modal.html`) with the content already embedded.
3. HTMX swaps the complete modal (overlay + content) into the wrapper element.

The content view runs in the same request context — it receives the same `request` object (user, session, cookies, headers). The only difference is that `request.GET` is temporarily set to the content URL's query parameters so the content view reads the correct data.

### Server-Side Content Fetching

`core/views.py` uses two helpers:

**`_build_content_url(request)`** — Extracts `content_url` from request params. Any extra query parameters in the request are merged into the content URL. Returns `(content_url, error_response)`.

**`_fetch_modal_content(request, content_url)`** — Resolves the URL path to a view function, calls it, and returns the response. If the view raises `PermissionDenied`, it catches it and returns `HttpResponse(status=403)`.

### Error Handling

If the content view returns a 4xx or 5xx status code, the error response is returned directly to the client. HTMX does not swap on error status codes by default — no modal overlay appears. This integrates naturally with the permission system: unauthorized HTMX requests get a silent 403 (visible in the browser console).

### TemplateResponse Compatibility

The server-side fetch calls `.render()` on `TemplateResponse` objects before extracting content. Standard `HttpResponse` objects (from `render()`) work as-is. This is transparent to content views.

---

## Template Structure

### Wrapper Elements

Every page that uses modals must include empty wrapper elements where the modal shells get swapped in:

```html
<div id="core-modal-placeholder-wrapper"></div>
<div id="core-modal-level-1-placeholder-wrapper"></div>
```

These exist in all base templates: `app/pages/base.html`, `dashboard/base.html`, and each admin `index.html`.

### Modal Shell

The shell template (`modal.html`) renders:

```html
<div id="base-modal" class="fixed inset-0 z-[9999]" role="dialog" aria-modal="true" tabindex="-1">
    <div class="modal-underlay absolute inset-0 cursor-pointer z-[9999]"
         onclick="closeModal()" aria-label="Close modal">
        <div class="absolute inset-0 bg-black/50"></div>
    </div>
    <div id="core-modal-placeholder" class="relative z-[10000]"
         role="document">{{ content_html|safe }}</div>
</div>
```

The level 1 modal is identical but uses higher z-index values (`z-[19999]` / `z-[20000]`) and a transparent overlay background.

### Closing Modals

Modals can be closed by:

- Clicking the overlay
- Pressing Escape (closes the topmost modal first)
- Calling `closeModal()` or `closeModalLevel1()` from JavaScript

Closing adds a `.closing` CSS class that triggers the exit animation, then removes the modal from the DOM on `animationend`.

---

## Using Modals

### 1. Create the content view

Write a standard Django view that returns an HTML fragment. This view knows nothing about the modal shell — it just renders its own template.

```python
@booking_permission_required("access_booking_management")
def my_form_view(request):
    form = MyForm()
    return render(request, "myapp/partials/my_form.html", {"form": form})
```

### 2. Set the animation on the content template

The content template's **root element** must have a `data-modal-animation` attribute:

```html
<div class="my-drawer" data-modal-animation="slide-right">
    <h2>My Form</h2>
    <form>{{ form.as_p }}</form>
</div>
```

If `data-modal-animation` is omitted, the modal defaults to `fade`.

### 3. Trigger the modal from a button

Use HTMX to hit the `core:modal` endpoint with a `content_url` parameter:

```html
{% url 'myapp:my_form' as form_url %}
<button type="button"
        hx-get="{% url 'core:modal' %}"
        hx-vals='{"content_url": "{{ form_url }}"}'
        hx-target="#core-modal-placeholder-wrapper"
        hx-swap="innerHTML">
    Open Form
</button>
```

### 4. Pass extra parameters

Any query parameters besides `content_url` are merged into the content URL automatically:

```html
<button hx-get="{% url 'core:modal' %}"
        hx-vals='{"content_url": "{{ form_url }}", "event_id": "{{ event.pk }}"}'
        hx-target="#core-modal-placeholder-wrapper"
        hx-swap="innerHTML">
    Open Form
</button>
```

The content view receives `event_id` in `request.GET` as if the client had hit the URL directly.

You can also use `hx-include` to send the current state of other form fields along with the request — the included values get merged into the content URL as well:

```html
<button hx-get="{% url 'core:modal' %}"
        hx-vals='{"content_url": "{{ form_url }}"}'
        hx-include="#filters-form-placeholder"
        hx-target="#core-modal-placeholder-wrapper"
        hx-swap="innerHTML">
    Open Filters
</button>
```

### 5. Nested modals (level 1)

For modals that open on top of an existing modal, use the level 1 endpoint and target:

```html
<button hx-get="{% url 'core:modal_level_1' %}"
        hx-vals='{"content_url": "{{ nested_form_url }}"}'
        hx-target="#core-modal-level-1-placeholder-wrapper"
        hx-swap="innerHTML">
    Open Nested
</button>
```

### 6. Closing from the content view

After a successful form submission, close the modal by swapping the wrapper to empty via OOB:

```html
{# In the success response template #}
<div hx-swap-oob="innerHTML:#core-modal-placeholder-wrapper"></div>
```

For level 1 modals, target `#core-modal-level-1-placeholder-wrapper` instead.

---

## Animation System

### How Animations Work

The animation system works in two phases:

1. **Shell insertion.** HTMX swaps the modal HTML into the DOM. The overlay (`#base-modal`) gets a `fadeIn` animation via CSS.

2. **JS configuration.** The `htmx:afterSwap` event fires. `_configureModalAnimation` reads `data-modal-animation` from the content's first child element and sets `data-animation-type` on the placeholder. CSS rules keyed on `data-animation-type` trigger the content animation.

On close, `closeModal()` adds `.closing` to the modal. CSS rules for `.closing` + `data-animation-type` play the exit animation. An `animationend` listener removes the modal from the DOM.

### Available Animations

| `data-modal-animation` | Enter | Exit | Use case |
|-------------------------|-------|------|----------|
| `slide-right` | Slides in from right | Slides out to right | Drawers, side panels |
| `fade` | Fades in | Fades out | Dialogs, confirmations |
| `slide-down` | Slides down from top | Slides up to top | Dropdown panels |
| `slide-up` | Slides up from bottom | Slides down to bottom | Bottom sheets |
| `none` | No animation | No animation | Instant swap |
| *(not set)* | `fade` (default) | `fade` (default) | Fallback |

All animations use `0.3s ease-out` timing.

---

## URL Routes

| URL | Name | View | Purpose |
|-----|------|------|---------|
| `/core/htmx-partials/core-modal/` | `core:modal` | `get_core_modal_with_htmx` | Base modal |
| `/core/htmx-partials/core-modal-level-1/` | `core:modal_level_1` | `get_core_modal_level_1_with_htmx` | Nested modal |

Both endpoints require HTMX requests (`HX-Request` header). Non-HTMX requests receive a 400 response.

---

## Z-Index Stacking

| Element | Z-Index |
|---------|---------|
| Base modal overlay | `9999` |
| Base modal content | `10000` |
| Level 1 modal overlay | `19999` |
| Level 1 modal content | `20000` |

---

## What's Not Supported

- **POST content views** — the server-side fetch always uses `GET`. POST-based form submissions should go directly to their own endpoint, not through the modal system. The modal is for loading the initial form; the form's `hx-post` submits directly to the action URL.
- **Content views that read `request.META['PATH_INFO']`** — this reflects the modal endpoint's path, not the content URL's path.
