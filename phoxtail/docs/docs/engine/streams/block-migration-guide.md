# Block Migration Guide

## Overview

This guide documents the process of migrating legacy (hardcoded) Wagtail blocks to the dynamic block system. Use this as a reference when migrating existing blocks.

---

## Prerequisites

Before migrating a block, ensure you understand:

1. **The existing block's structure** - What fields does it have? What are the types?
2. **The existing template** - How is data accessed and rendered?
3. **The schema system** - How to define blocks using schema JSON (see `DYNAMIC_BLOCKS_ARCHITECTURE.md`)

---

## Migration Steps

### Step 1: Analyze the Legacy Block

Locate the legacy block's Python class and template. Identify:

- **Fields and their types** (CharBlock, ImageChooserBlock, ListBlock, etc.)
- **Nested structures** (StructBlock within StructBlock)
- **List patterns** (ListBlock of simple fields vs ListBlock of StructBlocks)
- **Template access patterns** (how `value.field` is accessed)

### Step 2: Create the Block Directory

Create the block's directory structure:

```
streams/management/commands/data/blocks/<block-identifier>/
├── block.yaml                                  # Block metadata (required)
├── schema.json                                 # Schema definition (required)
└── variants/
    └── <collection-identifier>/                # e.g. general_unsorted
        └── <variant-identifier>/               # e.g. default
            ├── variant.yaml                    # Variant metadata (required)
            ├── description.md                  # Variant description (required)
            ├── template.html                   # HTML template (required)
            ├── styles.css                      # CSS styles (optional)
            └── script.js                       # JavaScript (optional)
```

> **Important:** `description.md` is **required**. The `import_variants` command will skip any variant directory that is missing it.

### Step 3: Create block.yaml

```yaml
name: Human Readable Name
identifier: snake_case_identifier
description: Brief description of what this block does
icon: wagtail-icon-name
```

### Step 4: Create schema.json

This is the core of the migration. Map the legacy Python block structure to JSON schema.

### Step 5: Write Scoped CSS

All styles must be pure CSS scoped to the block ID.

**The Block ID Scoping Pattern:**

Every dynamic block must scope its styles using the block ID to prevent style conflicts:

1. **CSS File Structure:**
   ```css
   /* Root selector with block ID */
   #block-identifier-{{ block.id }} {
       /* Root styles */
   }

   /* Child elements with namespaced classes */
   #block-identifier-{{ block.id }} .bi-element {
       /* Element styles */
   }
   ```

2. **Template Structure:**
   ```html
   <div id="block-identifier-{{ block.id }}" class="bi-wrapper">
       <div class="bi-container">
           <!-- Content with namespaced classes -->
       </div>
   </div>
   ```

3. **Class Naming Convention:**
   - Use a 2-3 letter prefix for your block (e.g., `hs-` for header-section, `vb-` for video-banner)
   - All classes should be scoped under `#block-identifier-{{ block.id }}`
   - This prevents style conflicts between multiple blocks

**Example:** See `streams/management/commands/data/blocks/header_section/styles.css` and corresponding template.

**Common CSS patterns:**

| Property | CSS |
|----------|-----|
| Flex row | `display: flex;` |
| Flex column | `display: flex; flex-direction: column;` |
| Center items | `align-items: center;` |
| Center content | `justify-content: center;` |
| `gap-4` | `gap: 1rem;` |
| `p-6` | `padding: 1.5rem;` |
| `mt-4` | `margin-top: 1rem;` |
| `w-full` | `width: 100%;` |
| `h-screen` | `height: 100vh;` |
| `text-white` | `color: white;` |
| `bg-black` | `background-color: black;` |
| `rounded-lg` | `border-radius: 0.5rem;` |
| `shadow-lg` | `box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);` |

For responsive styles, use media queries:
```css
/* Mobile first */
.element { font-size: 1rem; }

/* Tablet (md: 768px) */
@media (min-width: 768px) {
    .element { font-size: 1.25rem; }
}

/* Desktop (lg: 1024px) */
@media (min-width: 1024px) {
    .element { font-size: 1.5rem; }
}
```

---

## Schema Definition Reference

### Field Type Mapping

| Wagtail Block | Schema Type |
|---------------|-------------|
| `CharBlock` | `char_field` |
| `TextBlock` | `text_field` |
| `RichTextBlock` | `rich_text_field` |
| `BooleanBlock` | `boolean_field` |
| `IntegerBlock` | `integer_field` |
| `FloatBlock` | `float_field` |
| `DecimalBlock` | `decimal_field` |
| `DateBlock` | `date_field` |
| `TimeBlock` | `time_field` |
| `DateTimeBlock` | `datetime_field` |
| `URLBlock` | `url_field` |
| `EmailBlock` | `email_field` |
| `ImageChooserBlock` | `image_chooser_field` |
| `PageChooserBlock` | `page_chooser_field` |
| `DocumentChooserBlock` | `document_chooser_field` |
| `SnippetChooserBlock` | `snippet_chooser_field` |
| `EmbedBlock` | `embed_field` |
| `ChoiceBlock` | `choice_field` |
| `MultipleChoiceBlock` | `multiple_choice_field` |
| `BlockQuoteBlock` | `blockquote_field` |
| `RawHTMLBlock` | `raw_html_field` |
| `RegexBlock` | `regex_field` |

### Structure Types

| Pattern | Schema Type | Use Case |
|---------|-------------|----------|
| Group of fields | `struct` | Grouping related fields (e.g., text section with title + subtitle) |
| List of same field type | `list_field` | Simple repeating items (e.g., list of tags) |
| List of same structure | `list_struct` | Repeating structured items (e.g., team members) |
| List of different types | `stream` | Mixed content (e.g., buttons with internal OR external links) |

### Choosing Between `list_struct` and `stream` (use only stream for now due to a bug in the wagtail admin UI)

**Use `list_struct` when:**
- All items have the **same structure**
- Items are homogeneous (e.g., all features have `name` + `is_enabled`)

**Use `stream` when:**
- Items can be **different types**
- Items are heterogeneous (e.g., `internal_link` OR `external_link`)

**Template access difference:**

```django
{# list_struct - direct access #}
{% for feature in plan.features %}
    {{ feature.name }}
{% endfor %}

{# stream - access via .value and .block_type #}
{% for button_block in plan.buttons %}
    {% if button_block.block_type == 'internal_link' %}
        {% with button=button_block.value %}
            {{ button.label }}
        {% endwith %}
    {% endif %}
{% endfor %}
```

---

## Layer System for Nested Structures

The schema system uses depth-limited layers to support nested structures while preventing infinite recursion.

### Layer Hierarchy

| Layer | Block Types | Can Contain |
|-------|-------------|-------------|
| L0 (top) | `struct`, `stream`, `list_struct` | Fields + L1 blocks |
| L1 | `struct`, `stream`, `list_struct` (within L0) | Fields + L2 blocks |
| L2 (terminal) | `struct` (within L1) | Fields only |

### Naming Convention

- File: `layers.py`
- Classes: `StructSchemaBlockL1`, `StructSchemaBlockL2`, `StreamSchemaBlockL1`, `ListStructSchemaBlockL1`
- Registry: `LAYER_BLOCK_CHOICES`

### Example: Pricing Block (3 Levels Deep)

```
plans (L0 stream)
└── plan (L1 struct)
    ├── name, price, etc. (fields)
    ├── features (L1 stream)
    │   └── feature (L2 struct)
    │       └── feature, is_enabled (fields)
    └── buttons (L1 stream)
        └── internal_link | external_link (L2 struct)
            └── label, link, open_in_new_tab (fields)
```

### Schema JSON for Nested Structures

```json
{
  "type": "stream",
  "value": {
    "name": "plans",
    "blocks": [
      {
        "type": "struct",
        "value": {
          "name": "plan",
          "blocks": [
            {"type": "char_field", "value": {"name": "name", "required": true}},
            {
              "type": "stream",
              "value": {
                "name": "features",
                "blocks": [
                  {
                    "type": "struct",
                    "value": {
                      "name": "feature",
                      "blocks": [
                        {"type": "char_field", "value": {"name": "feature", "required": true}},
                        {"type": "boolean_field", "value": {"name": "is_enabled"}}
                      ]
                    }
                  }
                ]
              }
            }
          ]
        }
      }
    ]
  }
}
```

---

## Template Conversion

### Access Patterns

| Schema Type | Template Access |
|-------------|-----------------|
| Top-level field | `{{ value.field_name }}` |
| Nested struct field | `{{ value.struct_name.field_name }}` |
| List iteration | `{% for item in value.list_name %}` |
| Stream iteration | `{% for block in value.stream_name %}` |
| Stream block type | `{{ block.block_type }}` |
| Stream block value | `{{ block.value.field_name }}` |

### Common Patterns

**Simple field:**
```django
<h1>{{ value.title }}</h1>
```

**Nested struct:**
```django
<h1>{{ value.text.title }}</h1>
<p>{{ value.text.subtitle }}</p>
```

**List of structs (list_struct):**
```django
{% for feature in value.features %}
    <li>{{ feature.name }}: {{ feature.description }}</li>
{% endfor %}
```

**Stream with multiple types:**
```django
{% for button_block in value.buttons %}
    {% if button_block.block_type == 'internal_link' %}
        {% with button=button_block.value %}
            <a href="{{ button.link.url }}">{{ button.label }}</a>
        {% endwith %}
    {% elif button_block.block_type == 'external_link' %}
        {% with button=button_block.value %}
            <a href="{{ button.link }}">{{ button.label }}</a>
        {% endwith %}
    {% endif %}
{% endfor %}
```

**Image chooser:**
```django
{% if value.image %}
    {% load wagtailimages_tags %}
    {% image value.image fill-800x600 as img %}
    <img src="{{ img.url }}" alt="{{ img.alt }}">
{% endif %}
```

**Page chooser:**
```django
{% if value.link %}
    <a href="{{ value.link.url }}">{{ value.link.title }}</a>
{% endif %}
```

---

## Step 6: Create the Template

Convert the legacy template to work with the new schema structure. Remember to:
- Use the block ID scoping pattern: `id="block-identifier-{{ block.id }}"`
- Use namespaced class names (e.g., `vb-wrapper`, `vb-container`)
- Access schema fields correctly (see Template Conversion section)

---

## Step 7: Test the Migration

1. **Run the populate command:**
   ```bash
   python manage.py populate_streams --only=blocks
   ```

2. **Verify in admin:**
   - Go to Wagtail admin → Streams → Blocks
   - Find your new block
   - Check schema renders correctly

3. **Test on a page:**
   - Add the block to a page
   - Fill in all fields
   - Preview/publish and verify rendering

4. **Test edge cases:**
   - Empty optional fields
   - Maximum items in lists
   - All variants of stream blocks

---

## Common Migration Gotchas

### 1. Forgetting `.value` for Streams

**Wrong:**
```django
{% for button in value.buttons %}
    {{ button.label }}  {# Won't work! #}
{% endfor %}
```

**Correct:**
```django
{% for button_block in value.buttons %}
    {{ button_block.value.label }}
{% endfor %}
```

### 2. Using `stream` for Homogeneous Lists

If all items have the same structure, use `list_struct` instead of `stream`. It's simpler in both schema and template.

### 3. Missing `wagtailcore_tags` Load

Always include at the top of templates:
```django
{% load wagtailcore_tags %}
```

And for images:
```django
{% load wagtailimages_tags %}
```

### 4. Incorrect Nesting Depth

Remember the layer limits:
- L0 can contain L1 blocks
- L1 can contain L2 blocks
- L2 cannot contain nested structures

If you need deeper nesting, the architecture supports adding L3, but consider if your block structure is too complex.

### 5. Boolean Field Defaults

Boolean fields in Wagtail default to `False` when unchecked. In templates, check with:
```django
{% if value.is_highlighted %}...{% endif %}
```

Not:
```django
{% if value.is_highlighted == True %}...{% endif %}
```

---

## Example Migration: Image Banner Block

### Legacy Python Block

```python
class ImageBannerBlock(StructBlock):
    image = ImageChooserBlock(required=True)
    title = CharBlock(required=False, max_length=100)
    subtitle = TextBlock(required=False)
    overlay_opacity = IntegerBlock(default=50, min_value=0, max_value=100)
    buttons = ListBlock(
        StructBlock([
            ('label', CharBlock(required=True)),
            ('link', PageChooserBlock(required=True)),
        ]),
        max_num=2
    )
```

### Migration Files

**block.yaml:**
```yaml
name: Image Banner
identifier: image_banner
description: Full-width image banner with optional text overlay and CTA buttons
icon: image
```

**schema.json:**
```json
[
  {
    "type": "image_chooser_field",
    "value": {
      "name": "image",
      "required": true,
      "help_text": "Banner background image"
    }
  },
  {
    "type": "struct",
    "value": {
      "name": "text",
      "collapsed": true,
      "blocks": [
        {
          "type": "char_field",
          "value": {
            "name": "title",
            "required": false,
            "max_length": 100,
            "help_text": "Banner title"
          }
        },
        {
          "type": "text_field",
          "value": {
            "name": "subtitle",
            "required": false,
            "help_text": "Banner subtitle"
          }
        }
      ]
    }
  },
  {
    "type": "integer_field",
    "value": {
      "name": "overlay_opacity",
      "required": false,
      "min_value": 0,
      "max_value": 100,
      "help_text": "Overlay darkness (0-100)"
    }
  },
  {
    "type": "list_struct",
    "value": {
      "name": "buttons",
      "required": false,
      "collapsed": true,
      "blocks": [
        {
          "type": "char_field",
          "value": {
            "name": "label",
            "required": true,
            "help_text": "Button text"
          }
        },
        {
          "type": "page_chooser_field",
          "value": {
            "name": "link",
            "required": true,
            "help_text": "Page to link to"
          }
        }
      ],
      "min_num": 0,
      "max_num": 2
    }
  }
]
```

**template.html:**
```django
{% load wagtailcore_tags wagtailimages_tags %}
<section id="banner-{{ block.id }}" class="image-banner">
    {% if value.image %}
        {% image value.image fill-1920x800 as bg_img %}
        <div class="banner-bg" style="background-image: url('{{ bg_img.url }}');">
            <div class="banner-overlay" style="opacity: {{ value.overlay_opacity|default:50 }}%;"></div>
            <div class="banner-content">
                {% if value.text.title %}
                    <h1>{{ value.text.title }}</h1>
                {% endif %}
                {% if value.text.subtitle %}
                    <p>{{ value.text.subtitle }}</p>
                {% endif %}
                {% if value.buttons %}
                    <div class="banner-buttons">
                        {% for button in value.buttons %}
                            <a href="{{ button.link.url }}" class="banner-btn">
                                {{ button.label }}
                            </a>
                        {% endfor %}
                    </div>
                {% endif %}
            </div>
        </div>
    {% endif %}
</section>
```

---

## Checklist

Before considering a migration complete:

- [ ] `block.yaml` created with correct identifier
- [ ] `schema.json` matches all fields from legacy block
- [ ] `variant.yaml` created with `is_default: true` for the default variant
- [ ] `description.md` created (required — variant is skipped without it)
- [ ] `template.html` renders all fields correctly
- [ ] `styles.css` includes necessary styles (if any)
- [ ] Block imports successfully via `populate_streams`
- [ ] Block appears in admin block chooser
- [ ] All field types render correctly
- [ ] List/stream iterations work
- [ ] Empty optional fields don't break rendering
- [ ] Legacy block can be deprecated/removed

---

## Related Documentation

- `DYNAMIC_BLOCKS_ARCHITECTURE.md` - Full architecture overview
- `streams/blocks/schema/layers.py` - Layer system implementation
- `streams/blocks/schema/fields.py` - Available field schema blocks
