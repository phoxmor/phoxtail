{#- Phoxtail Studio — Block Schema Design Context

This template is rendered by the MCP prompt `design_block` to brief an
AI agent on how to design a new block schema. It is pure context — the
agent decides what to do based on the human's request and the MCP tools.

Context variables:
  description    — the user's description of the block to create
  reference_url  — optional URL for design reference (may be None)
  schema_catalog — dict with common_parameters, field_types,
                   structure_types, layer_types
-#}
You are designing a Phoxtail block schema — a data model that defines what fields content editors will fill in when using this block.

---

## Your Task

{{ description }}
{% if reference_url %}

### Reference

Fetch this URL for design inspiration: `{{ reference_url }}`

Analyze the reference to identify the superset of data fields across all visual variations. Design a schema flexible enough that simpler variations can leave optional fields empty.
{% endif %}

---

## Available Field Types

Every field type accepts these **common parameters**: `name` (required, lowercase_with_underscores), `required` (bool, default true), `help_text` (str), `icon` (str).

### Fields
{% for type_id, info in schema_catalog.field_types.items() %}
- **{{ type_id }}** — {{ info.description }}{% if info.parameters %} | Params: {% for p, meta in info.parameters.items() %}`{{ p }}`{% if not loop.last %}, {% endif %}{% endfor %}{% endif %}

{% endfor %}

### Structures
{% for type_id, info in schema_catalog.structure_types.items() %}
- **{{ type_id }}** — {{ info.description }}{% if info.parameters %} | Params: {% for p, meta in info.parameters.items() %}`{{ p }}`{% if not loop.last %}, {% endif %}{% endfor %}{% endif %}

{% endfor %}

### Nesting Layers

Schemas support up to 3 levels of nesting: L0 (top) → L1 → L2 (terminal, fields only).
{% for type_id, info in schema_catalog.layer_types.items() %}
- **{{ type_id }}** — {{ info.description }}
{% endfor %}

---

## Schema Design Principles

1. **Use `list_struct` for repeating items** — stats entries, team members, features, buttons. Each item is a structured object with multiple fields.
2. **Use `struct` for grouping related fields** — author info (name + avatar + bio), address (street + city + zip).
3. **Use `stream` for mixed-content areas** — flexible sections where editors choose from multiple block types in any order.
4. **Mark fields `"required": false`** when not all visual variations need them — this lets simpler variants ignore optional data.
5. **Use `choice_field`** for enum-like toggles (e.g., `change_type: increase|decrease|neutral`, `alignment: left|center|right`).
6. **Keep field names descriptive** — use `stat_label` not `label`, `hero_image` not `img`. They become DTL template variables (`block.value.stat_label`).
7. **Provide `help_text`** for every field — editors rely on it to understand what each field expects.
8. **Layer nesting wisely** — most blocks need at most 1 level of nesting (a `list_struct` with fields). Use L1/L2 layers only for genuinely complex structures like pricing tables.

---

## Schema JSON Format

The schema is a JSON list where each item has `type` and `value`:

```json
[
  {
    "type": "char_field",
    "value": {
      "name": "title",
      "required": true,
      "help_text": "Main heading text"
    }
  },
  {
    "type": "list_struct",
    "value": {
      "name": "items",
      "required": true,
      "help_text": "Repeating stat entries",
      "blocks": [
        {
          "type": "char_field",
          "value": {"name": "label", "required": true, "help_text": "Stat name"}
        },
        {
          "type": "char_field",
          "value": {"name": "value", "required": true, "help_text": "Stat value"}
        }
      ]
    }
  }
]
```

For `choice_field`, the `choices` parameter uses a list of `{"value": "...", "label": "..."}` objects.

---

## Expected Output

1. **Analyze** the requirements (and reference URL if provided) to identify all needed fields.
2. **Explain** your schema design — which fields, why optional vs required, what structures are used.
3. **Call `phoxtail_studio_create_block`** with the complete schema. Include appropriate `name`, `identifier`, `description`, `group`, and `icon`.
4. After creating the block, **create variants** for each visual variation using `phoxtail_studio_create_variant`.
