---
name: Ground State
identifier: ground_state
description: The Ground State collection houses the default variant for each block — the most natural, stable, and self-evident rendering of the block's structure. Not the most decorative, not the most minimal, but the most essential — the form that requires no justification.
---

In physics, the ground state is the lowest energy configuration of a system — not the absence of form, but the most natural, stable state that emerges from the constraints of the problem. A rectangular door at human height with a handle at hip level is not minimal for minimalism's sake; it is the shape that human anatomy, gravity, and material properties naturally converge on. It is the form that requires no justification.

Each block's ground state variant follows this principle. It answers the question: *what does this block look like when nothing has been imposed on it?* The result is not bare, not decorative — it is **resolved**. Every element present earns its place; every element absent would have been noise.

This is the baseline from which all creative departures begin. A design system variant (Material Design, Minimalist, Brutalist) is a deliberate deviation from the ground state — a set of opinions applied to a form that is, at rest, already complete.

---

## Core Principles

**Structure Dictates Form**: The ground state does not invent — it *reveals*. The block's schema already defines what fields exist and how they relate. The ground state renders these relationships in the most self-evident way. A title sits above a subtitle. An image sits beside the text or behind it. A list of items flows naturally from top to bottom, left to right.

**Content First, Always**: Every decision serves the content. If a field has data, it appears. If it doesn't, there is no gap, no placeholder, no skeleton — the layout adapts as though the absent field was never part of the design. Use conditional rendering (`{% verbatim %}{% if value.field %}{% endverbatim %}`) for every optional element.

**Nothing to Add, Nothing to Remove**: The ground state is complete when removing any element would diminish function, and adding any element would not increase it. This is not minimalism (which is an aesthetic choice) — it is sufficiency.

**No Personality**: The ground state has no opinion about brand, mood, or era. It does not try to look modern, classic, playful, or serious. It simply presents the content with clarity and proportion. Personality belongs to design system collections.

---

## Style Isolation

All styles are scoped to the block instance via its unique ID. No ground state variant may leak styles to other blocks, nor depend on styles from outside itself.

```css
#block-name-{% verbatim %}{{ block.id }}{% endverbatim %} .class-name {
    /* All styles scoped here */
}
```

Use a short, consistent class prefix per block type (e.g., `hs-` for header section, `ib-` for image banner). This prevents collisions without requiring a CSS methodology.

---

## Color Strategy

The ground state uses semantic CSS variables derived from the site's global palettes. These variables provide raw RGB triplets and must be used with the `rgb()` or `rgba()` functions.

**Naming Convention**: `--color-{role}-{shade}` (e.g., `--color-surface-800`, `--color-primary-600`).

Available semantic roles for this site:
{% for role in palette_roles %}
- **{{ role.name }}** (`{{ role.identifier }}`): {{ role.description }}
{% endfor %}

---

## Typography Strategy

The ground state uses semantic font variables. These variables handle font selection and available weights automatically.

**Variable Patterns**: 
- Family: `--font-{role}` (e.g., `--font-heading`)
- Weight: `--font-{role}-weight-{weight_slot}` (e.g., `--font-heading-weight-bold`)

Available semantic font roles for this site:
{% for role in font_roles %}
- **{{ role.name }}** (`{{ role.identifier }}`): {{ role.description }}
{% endfor %}

Available weight slots: `thin`, `light`, `regular`, `medium`, `semibold`, `bold`, `extrabold`, `black`.

**Example Usage**:
```css
.title {
    font-family: var(--font-heading);
    font-weight: var(--font-heading-weight-bold);
}
```

---

## Light/Dark Theming

Ground state variants must support both light and dark color schemes using `prefers-color-scheme`. The switching is handled entirely in the variant's CSS by selecting different palette shades per mode.

```css
{% verbatim %}#block-name-{{ block.id }}{% endverbatim %} {
    /* Light mode (default) */
    background-color: rgb(var(--color-surface-50));
    color: rgb(var(--color-surface-800));
}

@media (prefers-color-scheme: dark) {
    {% verbatim %}#block-name-{{ block.id }}{% endverbatim %} {
        background-color: rgb(var(--color-surface-800));
        color: rgb(var(--color-surface-50));
    }
}
```
