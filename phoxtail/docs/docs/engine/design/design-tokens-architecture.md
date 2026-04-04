# Design Tokens Architecture

## Overview

SiteConfig (`app.SiteConfig`) is the single source of truth for all design tokens
across the platform. It generates CSS custom properties that are injected into every
page via Wagtail's site settings mechanism, eliminating the need for custom context
processors.

---

## How It Works

### SiteConfig as the Token Source

SiteConfig is a Wagtail `BaseSiteSetting` enhanced with `ClusterableModel` to support
inline child models. It lives under **Settings > Site Config > Theme** in the Wagtail
admin.

The Theme tab exposes:

- **Fonts** -- an inline panel of `SiteConfigFont` rows pairing a `design.FontFamily`
  with a `design.FontRole` (e.g. Heading, Body).
- **Color Palettes** -- an inline panel of `SiteConfigPalette` rows pairing a
  `design.Palette` with a `design.PaletteRole`.

#### Color Tokens
Each palette-role assignment produces a full set of CSS variables:
...
#### Typography Tokens
Each font-role assignment produces:
1. A font-family variable: `--font-{role}: 'Font Name', fallbacks;`
2. Semantic weight variables: `--font-{role}-weight-{slot}: {value};`

Semantic weight slots include: `thin`, `light`, `regular`, `medium`, `semibold`, `bold`,
`extrabold`, and `black`.

**Intelligent Weight Mapping**: To prevent "faux-bolding" by the browser, the system
automatically maps each semantic slot to the *nearest available weight* physically
present in the uploaded font family.

### Template Injection

Every base template follows the same three-step pattern in `<head>`:

1. Load `core/css/main.css` as a `<link>` stylesheet — establishes fallback `:root` variables.
2. Load any additional static CSS (app-specific styles).
3. Emit an inline `<style>` block with SiteConfig values — overrides the fallbacks.

```html
<!-- Step 1: fallback defaults (all CSS vars have safe values) -->
<link rel="stylesheet" href="{% static 'phoxtail_core/css/main.css' %}" />

<!-- Step 2: other static CSS -->
<link rel="stylesheet" href="{% static 'app/css/main.css' %}" />

<!-- Step 3: SiteConfig overrides — these win because they appear later in the document -->
{% load wagtailsettings_tags %}
{% get_settings %}
<style>
    :root {
        {{ settings.app.SiteConfig.css_variables|safe }}
    }
    {{ settings.app.SiteConfig.font_face_declarations|safe }}
</style>
```

The override works purely through **CSS cascade order**: both `main.css` and the inline
`<style>` target `:root` with equal specificity, so the declaration that appears later in
the document wins. No JavaScript, no runtime logic — the browser resolves it.

If `SiteConfig` has no palettes or fonts configured (e.g. a fresh install), the inline
`<style>` emits nothing and the fallbacks from `main.css` remain in effect.

No context processor is needed for design tokens. Wagtail's `wagtail.contrib.settings`
context processor (already required by Wagtail) provides `settings.app.SiteConfig` to all
templates automatically.

#### Injection points

| Template | Serves |
|----------|--------|
| `app/templates/app/pages/base.html` | All Wagtail CMS pages |
| `dashboard/templates/dashboard/base.html` | Dashboard interface |
| `core/templates/allauth/layouts/base.html` | Auth pages (login, signup, password reset) |
| `core/templates/wagtailadmin/pages/login.html` | Wagtail admin login |
| `core/templates/wagtailadmin/pages/password_required.html` | Password-protected pages |

### CSS Fallback Defaults

`core/static/core/css/main.css` defines fallback values in `:root` so pages render
correctly even when no palettes are configured in SiteConfig:

```css
:root {
    --color-primary-50: 238 242 255;    /* indigo */
    ...
    --color-accent-50: var(--color-primary-50);  /* Falls back to primary */
    ...
    --color-surface-50: 249 250 251;    /* neutral gray */
    ...
}
```

The comment at the top of the file makes this role explicit:

```css
/* CSS Custom Properties – Fallback Defaults
   (Overridden by SiteConfig inline <style>) */
```

When SiteConfig injects its values, they override these defaults.

---

## Semantic Roles

The `design.PaletteRole` model defines semantic roles. The four core roles (seeded by
`populate_palette_roles` management command) are:

| Role | Identifier | Purpose |
|------|------------|---------|
| Surface | `surface` | Backgrounds, text, borders, dividers |
| Primary | `primary` | Main brand color, buttons, links, focus rings |
| Accent | `accent` | Secondary emphasis, badges, highlights, secondary CTAs |
| Destructive | `destructive` | Errors, dangerous actions, delete buttons |

### Font Roles

The `design.FontRole` model defines semantic typography roles. The four core roles (seeded by
`populate_font_roles` management command) are:

| Role | Identifier | Purpose |
|------|------------|---------|
| Heading | `heading` | Expressive headlines and titles |
| Body | `body` | Main reading content and paragraphs |
| UI | `ui` | Buttons, navigation, and labels |
| Monospace | `mono` | Code and technical data |

### Relationship with Streams VariantCollections

SiteConfig assigns specific palettes and fonts to semantic roles (primary, surface, heading, body, etc.).
`streams.VariantCollection` templates document these semantic roles for AI variant generation, but remain
agnostic to which specific palettes or fonts fill those roles. This separation allows block variants to
work across different site configurations—variants reference semantic CSS variables
(`--color-primary-500`, `--font-heading`), while SiteConfig determines the actual palette/font that fills
each role. Both systems use the same `PaletteRole` and `FontRole` models, ensuring consistent naming
across the platform.

---

## Elimination of Custom Context Processors

### Before: `app/context_processors.py`

The old architecture used a custom `navigation` context processor that:

1. Resolved the current site and locale from the request.
2. Queried `Menu`, `Footer`, and `SiteTheme` models.
3. Built CSS variable strings with hardcoded fallback palettes.
4. Injected `palette_css_vars`, `font_face_css`, `font_css_vars` into template context.

This had several problems:

- **Ran on every request** for every template, not just pages that needed it.
- **Hardcoded fallback palettes** duplicated in Python code rather than CSS.
- **Tightly coupled** template rendering to a specific context processor being
  registered in settings.
- **No admin UI** for managing which palette served which semantic role -- the
  primary/secondary mapping was implicit.

### After: SiteConfig + Wagtail Settings

- **Zero context processors** for design tokens. The `wagtail.contrib.settings`
  context processor (already required by Wagtail) provides `settings.app.SiteConfig`
  to all templates.
- **Fallbacks live in CSS** (`main.css` `:root`), not in Python.
- **Role assignment is explicit** -- admins choose which palette serves which semantic
  role through the InlinePanel UI.
- **Site-scoped by default** -- Wagtail's `BaseSiteSetting` handles multi-site without
  custom query logic.

The navigation models (`Menu`, `Footer`) moved to the dynamic blocks system
(`streams.SharedBlock` with `is_shared=True`), which is a separate concern from design
tokens.

---

## CSS Variable Naming Convention

All CSS custom properties use space-separated RGB values to support alpha composition:

```css
/* Definition */
--color-primary-500: 99 102 241;

/* Usage -- with alpha */
background: rgb(var(--color-primary-500) / 0.5);

/* Usage -- opaque */
color: rgb(var(--color-primary-500));
```

**Important**: Never use `rgba(var(--color-primary-500), 0.5)` -- the `rgba()` function
does not accept space-separated RGB values as a single argument.

### Naming history

| Old name | New name | Rationale |
|----------|----------|-----------|
| `--color-neutral-*` | `--color-surface-*` | Aligns with Material Design semantics and the `PaletteRole` identifier |
| `--color-secondary-*` | `--color-accent-*` | Matches the `accent` PaletteRole; avoids confusion with "secondary button" patterns |

---

## Dark Mode Strategy

Auth pages (`core/static/core/css/main.css`) use `@media (prefers-color-scheme: dark)`
to provide dark mode. The approach:

1. **CSS variable definitions stay the same** -- the palette values
   (`--color-surface-50` through `--color-surface-950`) are unchanged.
2. **Only the shade numbers referenced in rules change** -- light mode uses low shades
   for backgrounds (50, 100) and high shades for text (800, 900); dark mode inverts
   this.
3. **No JavaScript** -- purely CSS media query driven, respects OS preference.

This pattern can be extended to other areas of the site by adding dark-mode overrides
to the relevant CSS files.

Logos support dark mode through `<picture>` with `<source media="(prefers-color-scheme: dark)">`,
using the `logo_dark` image from SiteConfig when available. This is applied in all templates
that render a logo: auth pages, the dashboard sidebar, the dashboard mobile topbar, and the
mobile drawer.

---

## Key Files

| File | Role |
|------|------|
| `app/models.py` | `SiteConfig`, `SiteConfigPalette`, `SiteConfigFont` models |
| `design/models.py` | `Palette`, `PaletteRole`, `FontFamily`, `FontRole` models |
| `streams/models.py` | `VariantCollection` (documents semantic roles for AI variant generation) |
| `core/static/core/css/main.css` | CSS fallback defaults — loaded first so SiteConfig inline `<style>` can override |
| `app/templates/app/pages/base.html` | Token injection for all CMS pages |
| `dashboard/templates/dashboard/base.html` | Token injection for dashboard interface |
| `core/templates/allauth/layouts/base.html` | Token injection for auth pages |
| `core/templates/wagtailadmin/pages/login.html` | Token injection for Wagtail admin login |
