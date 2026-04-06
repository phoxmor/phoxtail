# Dynamic Blocks Architecture

## Overview

This document describes the database-driven block system that allows creating and managing Wagtail StreamField blocks entirely through the admin interface, without writing Python code or template files.

## Core Concept

**Traditional Approach (Hardcoded):**
```python
# Python file: blocks.py
class HeaderBlock(StructBlock):
    title = CharBlock()
    image = ImageChooserBlock()

# Template file: header.html
<h1>{{ value.title }}</h1>
<img src="{{ value.image.url }}">
```

**Dynamic Approach (Database-Driven):**
```
Database - Block table:
├─ identifier: "header_section"
└─ schema: [StreamField defining structure]

Database - BlockVariant table (default variant):
├─ block: header_section
├─ is_default: True
└─ html/css/javascript: template code

Generated at runtime:
└─ Python class: HeaderSectionBlock (created by factory)
```

---

## Architecture Components

### 1. Block Model (`streams/models.py`)

Stores the structural definition of a block type. Block is purely structural — all presentation (html/css/javascript) lives in BlockVariant.

```python
class Block(models.Model):
    name = CharField(unique=True)      # Display name: "Header Section"
    identifier = CharField(unique=True) # Unique ID: "header_section"
    description = TextField()          # Purpose and use case
    schema = StreamField()             # Structure definition

    @property
    def default_variant(self):
        """Return the default BlockVariant (is_default=True) for this block."""
        return self.variants.filter(is_default=True).first()
```

**Fields:**
- **name**: Human-readable name shown in admin (unique)
- **identifier**: Unique identifier used in code (lowercase, underscores)
- **description**: Explains the block's purpose and use case
- **schema**: StreamField using meta-blocks to define the block's structure

**Properties:**
- **default_variant**: Returns the BlockVariant marked as default for this block (the ground state)

### 2. VariantCollection Model (`streams/models.py`)

Groups BlockVariants that share common design principles and provides design context for AI generation.

```python
class VariantCollection(models.Model):
    name = CharField(unique=True)       # "Material Design", "Minimalist", "Corporate"
    identifier = CharField(unique=True) # "material_design_3", "minimalist"
    description = TextField()           # Design principles and guidelines
    template = TextField()              # DTL template for rendering design system context
```

**Purpose:** Centralizes design system definitions, allowing variants across different blocks to share consistent styling principles.

**Design Token Integration:**
Collections leverage the global site design tokens defined in `app.SiteConfig`. This ensures that all variants generated within a collection are aware of the site's brand palettes and typography.

**Benefits:**
- **Design Consistency**: Define design principles once, apply across multiple block variants.
- **Easy Filtering**: Find all variants following a specific design system.
- **AI Context**: Provides design guidelines and actual site design tokens that AI can use when generating new variants.
- **Single Source of Truth**: SiteConfig remains the primary source for brand identity site-wide.

### Design App (`design/models.py`)

The `design` app provides reusable design tokens (Palettes, PaletteRoles, FontFamilies) that are linked to the global `SiteConfig`.

#### Palette Model
...
#### FontFamily Model
...

#### Design Tokens in Collections

The `VariantCollection.template` field uses Django Template Language (DTL) to document the semantic design token system for AI variant generation. Templates describe the INTERFACE (semantic roles and CSS variable conventions) rather than specific palette/font choices, allowing variants to work across different site configurations.

**Example Collection Template Pattern:**
```django
{# In VariantCollection.template field #}
## Color Strategy

The ground state uses semantic CSS variables derived from the site's global palettes.

**Naming Convention**: `--color-{role}-{shade}` (e.g., `--color-surface-800`, `--color-primary-600`)

Available semantic roles:
{% for role in palette_roles %}
- **{{ role.name }}** (`{{ role.identifier }}`): {{ role.description }}
{% endfor %}

## Typography Strategy

The ground state uses semantic font variables for family and weight.

**Variable Patterns**:
- Family: `--font-{role}` (e.g., `--font-heading`)
- Weight: `--font-{role}-weight-{weight_slot}` (e.g., `--font-heading-weight-bold`)

Available semantic font roles:
{% for role in font_roles %}
- **{{ role.name }}** (`{{ role.identifier }}`): {{ role.description }}
{% endfor %}

Available weight slots: `thin`, `light`, `regular`, `medium`, `semibold`, `bold`, `extrabold`, `black`.
```

**Key Insight**: Variants reference semantic CSS variables (`--color-primary-500`, `--font-heading`), while `SiteConfig` determines which actual palettes and fonts fill those semantic roles. This separation allows the same variant to work across different brand configurations.

### 3. BlockVariant Model (`streams/models.py`)

Stores template implementations for a Block within a Collection. All presentation (html/css/javascript) lives here — Block itself is purely structural.

```python
class BlockVariant(models.Model):
    block = ForeignKey(Block)              # Which block this is a variant of
    collection = ForeignKey(VariantCollection)  # Design collection it belongs to
    name = CharField()                     # "Modern", "Minimal", "Bold"
    identifier = CharField()               # "centered_dark", "split_layout"
    description = TextField()              # Design rationale and approach
    is_default = BooleanField()            # Whether this is the block's default variant

    # Template fields (split for separation of concerns)
    html = TextField()                     # HTML template with DTL tags
    css = TextField()                      # CSS styles (optional)
    javascript = TextField()               # JavaScript code (optional)

    preview_image = ForeignKey()           # Optional screenshot

    class Meta:
        constraints = [
            UniqueConstraint(fields=["block", "collection", "identifier"]),
            UniqueConstraint(fields=["block"], condition=Q(is_default=True),
                             name="unique_default_variant_per_block"),
        ]
```

**Purpose:** Stores all presentation code for blocks. Each block has exactly one default variant (its ground state) that serves as the fallback when no variant is explicitly selected.

**Key Fields:**
- **identifier**: Unique identifier within the block+collection combination
- **description**: Explains why this variant exists and what makes it different (required for AI context and team communication)
- **is_default**: Boolean flag. Only one variant per block can be default (enforced by partial unique constraint). The default variant is the block's "ground state" — its most natural rendering.
- **html/css/javascript**: Split template fields for separation of concerns
- **preview_image**: Optional screenshot of the rendered variant

### 4. Context Assembly (replaced BlockSystemPrompt)

!!! note "Removed"
    The `BlockSystemPrompt` model has been removed. AI context is now assembled via `POST /api/streams/v1/context/` and rendered through a static Jinja2 template (`cli/templates/studio/context.md`). See the [Studio Architecture](../../studio/architecture.md) docs for details.

### 5. Schema Definition Blocks (`streams/blocks/schema.py`)

Special blocks used to DEFINE the structure of other blocks. Each block type is now specialized for its purpose.

#### Field Schema Blocks (23 Types)

Instead of a generic FieldDefinitionBlock, we now have **23 specialized field schema blocks** - one for each Wagtail field type. This provides better type safety, clearer admin UI, and field-specific parameters.

**Organized by Category:**

| Category | Field Schema Blocks |
|----------|---------------------|
| **Text Fields** | CharSchemaBlock, TextSchemaBlock, EmailSchemaBlock, URLSchemaBlock, BlockQuoteSchemaBlock, RawHTMLSchemaBlock |
| **Numeric Fields** | IntegerSchemaBlock, FloatSchemaBlock, DecimalSchemaBlock |
| **Boolean** | BooleanSchemaBlock |
| **Date/Time** | DateSchemaBlock, TimeSchemaBlock, DateTimeSchemaBlock |
| **Rich Content** | RichTextSchemaBlock |
| **Advanced** | RegexSchemaBlock, ChoiceSchemaBlock, MultipleChoiceSchemaBlock |
| **Choosers** | PageChooserSchemaBlock, DocumentChooserSchemaBlock, ImageChooserSchemaBlock, ImageSchemaBlock, SnippetChooserSchemaBlock |
| **Embed** | EmbedSchemaBlock |

**Example - CharSchemaBlock:**
```python
{
    "type": "char_field",
    "value": {
        "name": "title",
        "required": True,
        "help_text": "Main heading",
        "max_length": 255  # Field-specific parameter
    }
}
```

**Example - BooleanSchemaBlock:**
```python
{
    "type": "boolean_field",
    "value": {
        "name": "highlighted",
        "required": False,
        "help_text": "Highlight this item"
    }
}
```

**Key Advantages:**
- Direct mapping: `"char_field"` → `CharBlock` (no type lookup)
- Field-specific parameters (e.g., `max_length` for char, `choices` for choice fields)
- Organized by `Meta.group` in admin for easy discovery
- Type-safe schema definitions

#### StructSchemaBlock
Describes a nested group of fields:
```python
{
    "type": "struct",
    "value": {
        "name": "text",
        "fields": [
            {"type": "char_field", "value": {"name": "title", ...}},
            {"type": "text_field", "value": {"name": "subtitle", ...}},
        ]
    }
}
```

#### ListFieldSchemaBlock
Describes a repeating list of simple field items:
```python
{
    "type": "list_field",
    "value": {
        "name": "tags",
        "field_type": "char_field",  # Must match a field schema block type
        "min_num": 0,                # Optional
        "max_num": 10                # Optional
    }
}
```

**Use Cases:**
- Gallery images (list of image_chooser_field)
- Tags (list of char_field)
- Links (list of url_field)
- Any collection of the same field type

#### ListStructSchemaBlock
Describes a repeating list of structured items:
```python
{
    "type": "list_struct",
    "value": {
        "name": "features",
        "struct_fields": [
            {"type": "char_field", "value": {"name": "title", ...}},
            {"type": "text_field", "value": {"name": "description", ...}},
            {"type": "image_chooser_field", "value": {"name": "icon", ...}},
        ],
        "min_num": 1,    # Optional
        "max_num": 20    # Optional
    }
}
```

**Use Cases:**
- Pricing plans (title, price, features list, highlighted flag)
- Feature lists (icon, title, description)
- Team members (name, role, photo, bio)
- Any collection of structured objects

#### StreamSchemaBlock
Describes a free-form mixed-content stream where editors can choose from multiple block types and mix them in any order (equivalent to Wagtail's StreamBlock):
```python
{
    "type": "stream",
    "value": {
        "name": "content_blocks",
        "stream_blocks": [
            {"type": "char_field", "value": {"name": "heading", ...}},
            {"type": "rich_text_field", "value": {"name": "paragraph", ...}},
            {"type": "image_chooser_field", "value": {"name": "image", ...}},
            {"type": "embed_field", "value": {"name": "video", ...}},
            {"type": "struct", "value": {"name": "quote", "fields": [...]}},
        ],
        "min_num": 1,       # Optional
        "max_num": 20,      # Optional
        "block_counts": {}  # Optional per-block-type limits
    }
}
```

**Use Cases:**
- Media galleries with mixed content (images OR videos OR captions)
- Flexible content sections (heading, paragraph, image, embed in any order)
- Page builders where block type and order vary per page
- Any scenario requiring heterogeneous repeating content

**Key Difference from ListBlock:**
- `ListBlock`: All items are the same type (homogeneous)
- `StreamBlock`: Items can be different types (heterogeneous)

### 6. Factory (`streams/blocks/factory.py`)

Dynamically generates Python block classes from database definitions.

#### `create_block_from_schema(block)`

Reads `Block.schema` and creates a Wagtail `StructBlock` class at runtime.

**Process:**
1. Read schema from database
2. For each item in schema:
   - If `block_type.endswith("_field")` → create Wagtail field block (direct mapping)
   - If `block_type == "struct"` → create nested StructBlock
   - If `block_type == "list_field"` → create ListBlock with simple field items
   - If `block_type == "list_struct"` → create ListBlock with StructBlock items
   - If `block_type == "stream"` → create StreamBlock with mixed block types
3. Store `_block_identifier` on the class
4. Return block instance

**Field Type Mapping (Direct, No Lookup):**
```python
block_map = {
    "char_field": CharBlock,
    "text_field": TextBlock,
    "email_field": EmailBlock,
    "url_field": URLBlock,
    "boolean_field": BooleanBlock,
    "integer_field": IntegerBlock,
    "float_field": FloatBlock,
    "date_field": DateBlock,
    "rich_text_field": RichTextBlock,
    "image_chooser_field": ImageChooserBlock,
    # ... all 23 field types
}
```

**Example - Pricings Block:**
```python
# Database
Block(
    identifier="pricings",
    schema=[
        {"type": "char_field", "value": {"name": "title", ...}},
        {"type": "text_field", "value": {"name": "subtitle", ...}},
        {"type": "list_struct", "value": {
            "name": "plans",
            "struct_fields": [
                {"type": "char_field", "value": {"name": "title", ...}},
                {"type": "char_field", "value": {"name": "price", ...}},
                {"type": "text_field", "value": {"name": "description", ...}},
                {"type": "list_field", "value": {
                    "name": "features",
                    "field_type": "char_field",
                    "min_num": 1,
                    "max_num": 20
                }},
                {"type": "boolean_field", "value": {"name": "highlighted", ...}},
            ],
            "min_num": 1,
            "max_num": 6
        }}
    ]
)

# Generated at runtime
class PricingsBlock(BlockVariantStructBlock):
    _block_identifier = "pricings"  # Stored for render lookup
    title = CharBlock()
    subtitle = TextBlock()
    plans = ListBlock(
        StructBlock([
            ("title", CharBlock()),
            ("price", CharBlock()),
            ("description", TextBlock()),
            ("features", ListBlock(CharBlock(), min_num=1, max_num=20)),
            ("highlighted", BooleanBlock()),  # Note: BooleanBlock, not CharBlock!
        ]),
        min_num=1,
        max_num=6
    )
    variant = SnippetChooserBlock("BlockVariant")
```

#### `get_dynamic_blocks()`

Queries all Blocks and generates them for use in StreamFields.

**Returns:** `[(identifier, block_instance), ...]`

### 7. SchemaStreamField (`streams/fields.py`)

Custom StreamField that generates blocks from schema definitions.

**Problem Solved:** Normal StreamField expects static block list at field definition time. This class allows blocks to be generated from schemas stored in the database, enabling a schema-driven architecture.

**Implementation:**
```python
class SchemaStreamField(StreamField):
    @property
    def stream_block(self):
        # Calls the callable fresh each time
        # Returns StreamBlock with current blocks from database schemas
```

**Usage:**
```python
BodyStreamField = SchemaStreamField(
    get_dynamic_blocks,  # Callable that generates blocks from schemas
    use_json_field=True,
    ...
)
```

### 8. BlockVariantStructBlock (`streams/blocks/base.py`)

Base class for all dynamically-generated blocks. Handles template rendering with split fields.

**render() Logic:**
```python
def render(self, value, context=None):
    # 1. Check if user selected a variant
    variant = value.get("variant")

    if variant:
        # Use variant's split template fields
        html = variant.html
        css = variant.css or ""
        javascript = variant.javascript or ""
    elif hasattr(self, "_block_identifier"):
        # No variant selected - use default variant (cached)
        default_variant = get_default_variant(self._block_identifier)
        if default_variant:
            html = default_variant.html
            css = default_variant.css or ""
            javascript = default_variant.javascript or ""

    # 2. Render the HTML template
    template = Template(html)
    rendered_html = template.render(Context(...))

    # 3. Assemble output with CSS and JS
    parts = [rendered_html]
    if css:
        parts.append(f"<style>{css}</style>")
    if javascript:
        parts.append(f"<script>{javascript}</script>")

    return mark_safe("\n".join(parts))
```

**Key Features:**
- Removes `_block_identifier` from child_blocks (it's metadata, not a field)
- Moves `variant` field to the end
- Single rendering path: always through a variant (selected or default)
- Uses split template fields (html, css, javascript)
- Assembles final output with proper wrapping of CSS and JS
- Falls back to parent if no variant or html available

---

## Data Flow

### Block Creation (One-time, by developers/admins)

```
1. Admin creates Block in Wagtail admin:
   ├─ name: "Simple Hero"
   ├─ identifier: "simple_hero"
   └─ schema: [Define structure using meta-blocks]

2. Admin creates default variant (ground state):
   ├─ block: Simple Hero
   ├─ collection: Ground State
   ├─ is_default: True
   ├─ html: "<div>{{ value.text.title }}</div>..."
   ├─ css: ".hero { padding: 2rem; }..."
   └─ javascript: "" (optional)

3. Server starts/restarts:
   └─ Factory generates SimpleHeroBlock class in memory
```

### Content Creation (By content editors)

```
1. Editor edits page → clicks "Add block" in Body field
   └─ Sees "Simple Hero" in block chooser

2. Fills in fields:
   ├─ text.title: "Welcome!"
   ├─ text.subtitle: "Great to see you"
   ├─ image: [uploads image]
   └─ variant: [optional - selects "Modern" variant]

3. Saves page
```

### Rendering (When user visits page)

```
1. Wagtail renders page → encounters SimpleHeroBlock

2. BlockVariantStructBlock.render() is called

3. Checks for variant:
   ├─ If variant selected → uses variant.html, variant.css, variant.javascript
   └─ If no variant → uses default variant's html, css, javascript (via get_default_variant cache)

4. Compiles Django template with user's data:
   HTML Template: "<div>{{ value.text.title }}</div>"
   Data: {"text": {"title": "Welcome!"}}
   Rendered HTML: "<div>Welcome!</div>"

5. Assembles final output:
   └─ rendered_html + <style>css</style> + <script>javascript</script>

6. Returns complete HTML to page
```

---

## The `_block_identifier` Pattern

### Why It's Needed

When rendering, the block class needs to know which `Block` record in the database it came from to fetch the default variant.

**The Problem:**
```python
# Factory creates this class
class SimpleHeroBlock(BlockVariantStructBlock):
    text = TextBlock()
    image = ImageChooserBlock()

# Later, during render:
def render(self, value, context):
    # How do I know this is identifier="simple_hero"?
    # I need to fetch the default variant for this block
```

**The Solution:**
```python
# Factory stores identifier as class attribute
fields["_block_identifier"] = block.identifier

# Generated class
class SimpleHeroBlock(BlockVariantStructBlock):
    _block_identifier = "simple_hero"  # ← Stored here!
    text = TextBlock()
    image = ImageChooserBlock()

# In render:
def render(self, value, context):
    default_variant = get_default_variant(self._block_identifier)  # ← Cached!
    html = default_variant.html
    css = default_variant.css
    javascript = default_variant.javascript
```

**In `__init__`:** The identifier is removed from `child_blocks` so it doesn't appear as a field in the admin.

---

## AI Integration

### Why Database Schema Matters for AI

With block structure in the database, AI can read it programmatically and generate template code that correctly accesses fields.

### Collections as AI Design Context

VariantCollections provide centralized design principles that guide AI generation. Collections can include both textual guidelines and concrete design tokens (palettes and fonts).

```python
# Example: Collection with design guidelines and linked design tokens
VariantCollection(
    name="Minimalist",
    description="""
    Design Principles:
    - Maximum whitespace, minimal visual elements
    - Single accent color only
    - Typography-focused hierarchy
    - No shadows or gradients
    - Subtle borders (1px, light gray)
    """,
    template="""
## Design Tokens

### Color Palettes
{% for cp in object.palettes.all %}
**{{ cp.palette.title }}**:
{{ cp.palette.get_css_variables }}
{% endfor %}

### Typography
{% for cf in object.fonts.all %}
**{{ cf.font_family.name }}** ({{ cf.font_family.category }}):
- CSS: font-family: {{ cf.font_family.get_css_font_family }};
- Weights: {{ cf.font_family.get_available_weights }}
{% endfor %}
"""
)
# Plus linked: CollectionPalette, CollectionFontFamily records
```

When generating a new variant, AI receives:
1. The block schema (available fields and structure)
2. The collection's design principles (description)
3. **Rendered design tokens** via `collection.render()` - actual color values and font definitions

This ensures AI-generated variants use the exact colors and fonts defined for that design system.

### AI Context Assembly

The `BlockSystemPrompt` model has been removed. AI context is now assembled via the streams API and rendered through a static Jinja2 context template (`cli/templates/studio/context.md`). The context includes block schema, design tokens, variant code, and references.

**Using the context API:**
```python
# Context is now assembled via the API and rendered through a Jinja2 template.
# See: POST /api/streams/v1/context/
# CLI: phoxtail studio context --block <block> --variant <variant>
# MCP: phoxtail_get_context tool
```

### AI Workflow

```
1. User runs `phoxtail studio edit <variant>` or uses MCP tools
2. Context is assembled automatically:
   - block → schema, available fields and structure
   - variant → reference HTML/CSS/JS implementation
   - collection → design guidelines + rendered design tokens (palettes, fonts)
   - references → other variants as design inspiration
3. Agent uses the context to make informed edits
4. Changes are saved via `phoxtail studio commit` or `phoxtail_update_variant` MCP tool
```

---

## File-Based Data Seeding

### Overview

The `populate_streams` management command provides a file-based approach to seed the database with blocks, collections, and variants. This enables version-controlled block definitions that can be shared across environments and tracked in Git.

### Directory Structure

```
streams/management/commands/data/
├── collections/                          # Variant collections
│   ├── ground_state.md                   # Ground State collection (default variants)
│   └── *.md                              # YAML frontmatter + markdown body
└── blocks/                               # Block definitions
    └── <block-identifier>/               # One directory per block
        ├── block.yaml                    # Metadata (required)
        ├── schema.json                   # Schema definition (required)
        └── variants/                     # Block variants
            ├── ground_state/             # Ground State collection
            │   └── default/              # Default variant (is_default: true)
            │       ├── variant.yaml      # Includes is_default: true
            │       ├── description.md    # Design rationale
            │       ├── template.html     # HTML template
            │       ├── styles.css        # CSS styles (optional)
            │       └── script.js         # JavaScript (optional)
            └── <collection-identifier>/  # Other collections
                └── <variant-identifier>/
                    ├── variant.yaml      # Variant metadata (required)
                    ├── description.md    # Design rationale (required)
                    ├── template.html     # HTML template (required)
                    ├── styles.css        # CSS styles (optional)
                    └── script.js         # JavaScript (optional)
```

**Key Design Decision:** The variant folder structure mirrors the database constraint `(block, collection, identifier)`. This ensures:
- Each variant is uniquely identified by its position in the hierarchy
- The same variant identifier can exist in different collections
- No ambiguity about which collection a variant belongs to

### File Formats

#### System Prompts (`prompts/*.md`)

Markdown files with YAML frontmatter. The markdown body becomes the `template` field.

```markdown
---
name: Variant Generator
identifier: variant_generator
description: Generates new block variants based on design collection principles
---
You are an expert frontend developer creating Wagtail block templates.

## Block: {{ block.name }}
...
```

#### Collections (`collections/*.md`)

Markdown files with YAML frontmatter. The markdown body becomes the `description` field.

```markdown
---
name: Material Design 3
identifier: material_design_3
---
## Design Principles

- Use Material Design 3 color system with dynamic color
- Rounded corners (16px for cards, 8px for buttons)
- Elevation through shadow layers
...
```

#### Blocks (`blocks/<block-identifier>/`)

Directory-based structure. Block directories contain only structural metadata — all presentation code lives in variant directories.

**block.yaml** (required):
```yaml
name: Header Section
identifier: header_section
description: A versatile header block with title, subtitle, image, and CTA buttons
icon: title
```

**schema.json** (required):
```json
[
  {
    "type": "struct",
    "value": {
      "name": "text",
      "blocks": [
        {"type": "char_field", "value": {"name": "title", "required": true}},
        {"type": "text_field", "value": {"name": "subtitle", "required": false}}
      ]
    }
  }
]
```

#### Variants (`blocks/<block>/variants/<collection>/<variant>/`)

**variant.yaml** (required):
```yaml
name: Centered Dark
identifier: centered_dark
is_default: false  # Optional, defaults to false. Set true for ground state variants.
```

Note: The `collection` is derived from the folder path, not specified in the YAML.

**description.md** (required):
```markdown
A dark-themed centered variant following Material Design 3 principles.
Uses surface container colors with high-emphasis text.
```

### Usage

```bash
# Import all entities
python manage.py populate_streams

# Import specific entity types
python manage.py populate_streams --only=prompts
python manage.py populate_streams --only=collections
python manage.py populate_streams --only=blocks
python manage.py populate_streams --only=variants
```

### Behavior

- **Idempotent**: Skips records that already exist (matched by `identifier`)
- **Order-aware**: Import order matters for dependencies (prompts → collections → blocks → variants)
- **Validation**: Reports missing required files and invalid YAML/JSON

### Benefits

- **Version Control**: Block definitions tracked in Git alongside code
- **Environment Sync**: Same blocks across development, staging, production
- **Code Review**: Template changes can be reviewed in PRs
- **Separation of Concerns**: HTML, CSS, JS in separate files for easier editing
- **IDE Support**: Syntax highlighting and linting for each file type

---

## Ground State & Ground State Collection

In physics, the *ground state* is the lowest energy configuration of a system — not the absence of form, but the most natural, stable state that emerges from the constraints of the problem. A rectangular door at human height with a handle at hip level is not minimal for minimalism's sake; it is the shape that human anatomy, gravity, and material properties naturally converge on. It is the form that requires no justification.

Each block's default variant — its ground state — follows this principle. It is the most stable, useful, and self-evident rendering of the block's structure. Not the most decorative, not the most minimal, but the most *natural*: the form that would emerge if you asked "what is this block at its most essential?" The ground state demonstrates the block's capabilities through the simplest means that still feels complete. It is the baseline from which all creative departures begin.

The **Ground State** collection (`identifier: ground_state`) houses these default variants. It is not a design system in the traditional sense — it is the set of canonical forms that blocks assume when no other design context is applied.

**Implementation:**
- Each block has exactly one default variant (`is_default=True`), enforced by a partial unique constraint
- Default variants are typically placed in the Ground State collection with identifier `default`
- The `Block.default_variant` property provides convenient access
- The `get_default_variant()` cache function ensures efficient lookups during rendering
- When no variant is explicitly selected by a content editor, the default variant is used automatically

---

## Advantages

### ✅ No Code Deployment for New Blocks
- Create blocks through admin
- No Git commits, no deployments
- Changes take effect immediately (after server restart)

### ✅ AI-Friendly
- Schema is machine-readable
- AI knows exactly what fields exist
- Can generate templates with correct field access
- Collections provide design guidelines for AI-generated variants

### ✅ Design System Consistency
- VariantCollections centralize design principles
- All variants in a collection follow the same guidelines
- Easy to maintain consistent branding across block types
- Filter and find variants by design system

### ✅ Multi-Tenancy Ready
- Different sites can have different blocks
- Block definitions tied to site/locale (future)

### ✅ Version Control for Templates
- Template changes tracked in database
- Can revert to previous versions
- Variants provide A/B testing capability

### ✅ Designer-Friendly
- Non-developers can create design variations
- Preview variants before applying
- No need to edit Python files

---

## Future Enhancements

### 1. Deeper Nesting
Allow recursive nesting by making `StructDefinitionBlock` reference itself.

### 2. Visual Block Builder
UI for composing blocks with drag-and-drop field arrangement.

### 3. Block Preview
Live preview of block rendering in admin before saving.

### 4. Template Validation
Syntax checking for `code` field to catch errors before save.

### 5. Auto-Generate Default Templates
Automatically create basic template from schema:
```python
def auto_generate_template(schema):
    # For each field, output it in simple HTML
    # Returns basic but functional template
```

### 6. Block Marketplace
Share/import blocks between projects or from community.

---

## File Reference

| File | Purpose |
|------|---------|
| `streams/models.py` | Block, VariantCollection, BlockVariant, and SharedBlock models |
| `streams/blocks/factory.py` | Dynamic block class generation |
| `streams/blocks/base.py` | BlockVariantStructBlock base class |
| `streams/blocks/schema.py` | Meta-blocks for schema definition |
| `streams/fields.py` | SchemaStreamField implementation |
| `streams/viewsets.py` | Wagtail admin configuration (BlockViewSet, VariantCollectionViewSet, BlockVariantViewSet) |
| `streams/management/commands/populate_streams.py` | File-based data seeding command |
| `streams/management/commands/data/` | Data files for seeding (blocks, collections, variants) |
| `design/models.py` | FontFamily, FontWeight, and Palette models for design tokens |
| `design/viewsets.py` | Wagtail admin configuration (FontFamilyViewSet, PaletteViewSet) |
| `design/wagtail_hooks.py` | Registers DesignViewSetGroup in Wagtail admin menu |
| `app/streams.py` | StreamField definitions using dynamic blocks |

---

## Example: Complete Workflow

### Step 1: Define Block in Admin

```
Name: Rich Text
Identifier: rich_text
Schema:
  + rich_text_field: content (required)
```

### Step 1b: Create Default Variant (Ground State)

```
Block: Rich Text
Collection: Ground State
Name: Default
Identifier: default
Is Default: True

HTML:
{% load wagtailcore_tags %}
<section id="richtext-{{ block.id }}" class="richtext-block">
    <div class="richtext-container">
        {{ value.content|richtext }}
    </div>
</section>

CSS:
#richtext-{{ block.id }} {
    padding: 2rem 1rem;
}
#richtext-{{ block.id }} .richtext-container {
    max-width: 65ch;
    margin: 0 auto;
    line-height: 1.7;
    color: #374151;
}
/* ... additional styles ... */
```

**Key Features Demonstrated:**
- **Block is purely structural**: Only name, identifier, description, and schema
- **All presentation in variants**: HTML, CSS, JavaScript live in BlockVariant
- **Default variant as ground state**: The most natural rendering of the block

### Step 2: Block Available Immediately

The factory dynamically generates `RichTextBlock` class when needed:
- `content` → RichTextBlock

No server restart required - the block appears immediately in any page editor using SchemaStreamField.

### Step 3: Use in Page

Editor adds "Rich Text" block to page:
- Writes content using the rich text editor
- Adds headings, paragraphs, lists, links
- Publishes page

### Step 4: Create Collection (One-time setup)

Admin creates a VariantCollection to define design principles:
```
Name: Minimalist
Description:
  Design Principles:
  - Clean layouts with generous whitespace
  - Simple typography hierarchy
  - Subtle colors, no gradients
  - Focus on content readability
```

### Step 5: Create Variant (Optional)

Admin creates BlockVariant within the "Minimalist" collection:
```
Block: Rich Text
Collection: Minimalist
Name: Narrow Column
Description: "A narrower reading column with increased line height for better readability"

HTML:
{% load wagtailcore_tags %}
<section id="richtext-{{ block.id }}" class="richtext-minimal">
    <div class="richtext-narrow">
        {{ value.content|richtext }}
    </div>
</section>

CSS:
#richtext-{{ block.id }} .richtext-narrow {
    max-width: 50ch;
    margin: 0 auto;
    line-height: 1.9;
    padding: 3rem 1rem;
}

JavaScript:
(empty)

Preview HTML:
<section class="richtext-minimal">
    <div class="richtext-narrow">
        <p>Clean, minimal text layout with generous whitespace...</p>
    </div>
</section>
```

### Step 6: Editor Selects Variant

Editor edits page, selects "Narrow Column" variant from the "Minimalist" collection, publishes with simpler design.

---

## Conclusion

This architecture transforms Wagtail blocks from hardcoded Python classes to dynamic, database-driven entities. VariantCollections provide a centralized way to define and enforce design principles across multiple block variants, ensuring consistency and enabling AI to generate templates that follow established design systems. This enables rapid iteration, AI-assisted design, and democratizes block creation for non-developers while maintaining the power and flexibility of Wagtail's StreamField system.
