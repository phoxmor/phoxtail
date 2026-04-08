{#- Phoxtail Studio — Block + Collection Context

This template is rendered by the MCP server / CLI to brief an AI agent on
the domain objects it will be working with. It is pure context — no task
instructions, no output format, no orchestration. The agent decides what
to do based on the human's request and the MCP tools available to it.

Context variables:
  block         — dict with name, identifier, description, field_schema
  collection    — dict with name, identifier, description,
                  design_guidelines (plain markdown)
  design_tokens — dict with palette_roles and font_roles lists
  references    — list of variant dicts (may be empty)
-#}
You are working with a Phoxtail block variant — a self-contained UI component made of HTML (Django Template Language), scoped CSS, and optional JavaScript.

---

## Block: {{ block.name }}

**Identifier:** `{{ block.identifier }}`
**Purpose:** {{ block.description }}

### Field Schema

```json
{{ block.field_schema }}
```

Fields are accessed via `block.value.<field_name>` in DTL. Fields with `"required": false` must be wrapped in `{% raw %}{% if block.value.<field> %}{% endraw %}` conditionals.

---

## DTL Reference

Templates use Django Template Language, not raw HTML. Key rules:

- **Variables:** `{% raw %}{{ block.value.title }}{% endraw %}`, `{% raw %}{{ block.value.title|default:"Untitled" }}{% endraw %}`
- **Conditionals:** `{% raw %}{% if block.value.subtitle %}{% endraw %}...{% raw %}{% endif %}{% endraw %}`
- **Loops:** `{% raw %}{% for item in block.value.items %}{% endraw %}...{% raw %}{% endfor %}{% endraw %}`
- **Stream type checks:** `{% raw %}{% if item.block_type == "image" %}{% endraw %}`
- **Wagtail images:** `{% raw %}{% load wagtailimages_tags %}{% endraw %}` then `{% raw %}{% image block.value.photo width-800 as img %}{% endraw %}`
- **Rich text:** `{% raw %}{{ block.value.body|richtext }}{% endraw %}`
- **Nested blocks:** `{% raw %}{% include_block child %}{% endraw %}`

### CSS Scoping

Every CSS rule **must** be scoped to the block instance's unique ID to prevent collisions when multiple blocks coexist on a page:

```css
#my-element-{% raw %}{{ block.id }}{% endraw %} { /* styles */ }
#my-element-{% raw %}{{ block.id }}{% endraw %} .child { /* styles */ }
```

### Dark Mode

All variants must support `prefers-color-scheme: dark` via CSS custom properties:

```css
#my-element-{% raw %}{{ block.id }}{% endraw %} {
    --color-surface: 255, 255, 255;
    --color-on-surface: 28, 27, 31;
}

@media (prefers-color-scheme: dark) {
    #my-element-{% raw %}{{ block.id }}{% endraw %} {
        --color-surface: 28, 27, 31;
        --color-on-surface: 230, 225, 229;
    }
}
```

### Width Patterns

| Pattern | CSS | When to use |
|---------|-----|-------------|
| Full-bleed | `width: 100%` | Heroes, banners, full-width media |
| Container | `max-width: 1280px; margin: 0 auto; padding: 0 1rem` | Cards, content sections |
| Narrow | `max-width: 1024px; margin: 0 auto; padding: 0 1rem` | Forms, focused content |
| Prose | `max-width: 65ch; margin: 0 auto` | Long-form text, articles |

---

## Design System: {{ collection.name }}

**Identifier:** `{{ collection.identifier }}`
**Philosophy:** {{ collection.description }}

{% if collection.design_guidelines %}{{ collection.design_guidelines }}{% endif %}

---

## Design Tokens

### Color Palette Roles

Colors use semantic CSS variables: `--color-{role}-{shade}` (e.g., `--color-surface-800`, `--color-primary-600`). Values are raw RGB triplets used with `rgb()` or `rgba()`.

Available shades per role: `50`, `100`, `200`, `300`, `400`, `500`, `600`, `700`, `800`, `900`, `950`.
{% for role in design_tokens.palette_roles %}
- **{{ role.name }}** (`{{ role.identifier }}`): {{ role.description }}
{%- endfor %}

### Font Roles

Fonts use semantic CSS variables:
- Family: `--font-{role}` (e.g., `--font-heading`)
- Weight: `--font-{role}-weight-{slot}` (e.g., `--font-heading-weight-bold`)

Available weight slots: `thin`, `light`, `regular`, `medium`, `semibold`, `bold`, `extrabold`, `black`.
{% for role in design_tokens.font_roles %}
- **{{ role.name }}** (`{{ role.identifier }}`): {{ role.description }}
{%- endfor %}

---
{% if references %}

## Reference Variants

{% for ref in references %}
### {{ ref.name }} ({{ ref.block.name }})

{{ ref.description }}

```django
{{ ref.html }}
```
{% if ref.css %}```css
{{ ref.css }}
```{% endif %}
{% if ref.javascript %}```javascript
{{ ref.javascript }}
```{% endif %}

{% endfor %}
---
{% endif %}
