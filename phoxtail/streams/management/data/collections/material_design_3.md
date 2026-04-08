---
name: Material Design 3
identifier: material_design_3
description: Material Design 3 (Material You) is Google's most adaptive design system, built on the idea that the UI should feel personal. It uses dynamic color to sync your interface with your wallpaper, creating a fluid, accessible experience across any screen size.
---

## Core Principles

**Material as Metaphor**: Design inspired by the physical world - surfaces reflect light and cast shadows, providing visual cues grounded in reality.

**Bold, Graphic, Intentional**: Typography, grids, space, scale, color, and imagery create hierarchy and focus.

**Motion Provides Meaning**: Motion focuses attention through subtle feedback and coherent transitions.

---

## Color Strategy

Material Design 3 variants map site-wide semantic color variables to M3 tokens. Use the site's palette roles to populate your theme by mapping `--color-{role}-{shade}` variables to M3 surface and accent tokens.

---

## Typography Strategy

Material Design 3 variants map site-wide semantic font variables to M3 type scales. Map the site's font roles (`--font-{role}`) and their weight slots (`--font-{role}-weight-{slot}`) to your components.

**Mapping Pattern**:

```css
#component-{% verbatim %}{{ block.id }}{% endverbatim %} {
    --md-sys-font-display: var(--font-heading);
    --md-sys-font-body: var(--font-body);
    
    font-family: var(--md-sys-font-body);
    font-weight: var(--font-body-weight-regular);
}

h1 {
    font-family: var(--md-sys-font-display);
    font-weight: var(--font-heading-weight-bold);
}
```

---

## Elevation & Shape

**Tonal elevation** (preferred):
- Level 0-5, higher = lighter surface tint
- Avoid drop shadows; use surface color changes

**Border radius**:
- Small (chips, buttons): 8px
- Medium (cards, dialogs): 12px
- Large (sheets, containers): 16-28px
- Full (FABs, pills): 9999px
