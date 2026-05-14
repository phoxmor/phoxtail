# Block Variant Scenarios — Implementation Plan

## Problem

The `phoxtail_studio_render_block` MCP tool captures a static screenshot of a block at load time. This is enough for most blocks, but fails for anything that requires a prior interaction to reach a meaningful visual state:

- A **navbar** on mobile — the hamburger menu is closed at load time; the agent needs to screenshot the open sidebar state to verify it.
- A **carousel** — the agent may want to verify slide 3, not slide 1.
- A **accordion** — the first panel is open by default; the agent needs to see panel 2 open.
- A **dark mode toggle** — the block is rendered in the system color scheme, but the designer wants to verify the explicit dark variant.

Without a way to declare these states, the agent would have to guess Playwright selectors and action sequences. That produces brittle, hallucinated automation that breaks the moment a class name changes.

## Proposed Solution: Scenarios on BlockVariant

Add a `scenarios` JSON field to the `BlockVariant` model. Each scenario describes a named visual state and the sequence of Playwright actions needed to reach it.

```python
# phoxtail/streams/models.py (future addition)
class BlockVariant(Orderable):
    ...
    scenarios = models.JSONField(
        default=list,
        blank=True,
        help_text="Named interaction sequences for screenshot automation.",
    )
```

### Scenario shape

```json
[
  {
    "name": "mobile-sidebar-open",
    "description": "Hamburger menu open on mobile viewport",
    "viewport": "mobile",
    "actions": [
      {"type": "click", "selector": "[data-action='open-sidebar']"}
    ]
  },
  {
    "name": "dark",
    "description": "Dark color scheme active",
    "viewport": "desktop",
    "theme": "dark"
  }
]
```

### Action types (initial set)

| type | required fields | description |
|------|----------------|-------------|
| `click` | `selector` | Click an element within the block |
| `hover` | `selector` | Hover over an element |
| `wait` | `ms` | Wait a fixed number of milliseconds |
| `wait_for` | `selector`, `state` | Wait until an element reaches a given state (`visible`, `hidden`) |

`selector` values are scoped to the block wrapper (`#phoxtail-block-{uuid}`) to prevent cross-block interference.

### Tool changes

Extend `phoxtail_studio_render_block` with an optional `scenario` parameter:

```python
async def render_block(
    page_id: int,
    block_uuid: str,
    viewport: str = "desktop",
    theme: str = "light",
    scenario: str | None = None,   # <-- new
) -> Any:
    ...
```

When `scenario` is given, the tool:

1. Fetches the `BlockVariant` record by looking up the block's active variant for the page.
2. Finds the matching scenario entry in `variant.scenarios`.
3. Overrides `viewport` and `theme` from the scenario if set.
4. Executes the action sequence inside the Playwright page before taking the screenshot.

The agent never writes selectors — it only passes a `scenario` name declared by the block author.

## What NOT to build

Do not let the agent compose action sequences from free text or synthesise selectors on the fly. The whole point of this system is that the block author declares the canonical states once, and the agent picks from that fixed menu. Arbitrary agent-authored Playwright scripts would reintroduce the hallucination problem.

Do not expose `scenarios` as a public API surface. They are an authoring tool for developers who know the block internals; they live in the admin only.

## Where scenarios are authored

Scenarios live in the Django admin / Wagtail panel on the `BlockVariant` inline — same place as `variant_identifier`, `is_default`, and `sort_order`. Long-term they could get a structured panel editor instead of raw JSON.

For ground-state data, the management command that seeds block variants (`phoxtail/streams/management/commands/`) can include `scenarios` in the fixture JSON alongside the variant identifier.

## Concrete example: navbar mobile sidebar

The default navbar variant would ship with:

```json
{
  "name": "mobile-sidebar-open",
  "description": "Sidebar drawer open (hamburger tapped)",
  "viewport": "mobile",
  "actions": [
    {"type": "click", "selector": "[data-action='toggle-sidebar']"},
    {"type": "wait_for", "selector": "[data-sidebar]", "state": "visible"}
  ]
}
```

Agent usage:

```
phoxtail_studio_render_block(page_id=4, block_uuid="57c197...", scenario="mobile-sidebar-open")
```

The tool resolves the viewport to `mobile`, opens the sidebar, waits for it to be visible, then screenshots — no selector guessing required.

## When to build this

Build it when the first block genuinely needs it. The screenshot tool already works for static states and dark/light mode. The scenario system only earns its complexity when a real variant requires an interaction to reach its canonical visual state and the current workaround (asking the user to screenshot manually) becomes a friction point.
