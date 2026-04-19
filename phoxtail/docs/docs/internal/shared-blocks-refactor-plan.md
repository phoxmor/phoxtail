# Shared Blocks Refactor — Abandoned

## Status

**Not proceeding.** Attempted 2026-04-19, reverted the same day. Keeping this
note so the next person asking "why don't we just…" has the answer.

## What we tried

Replace `SharedBlock.content` (a `SchemaStreamField(max_num=1)`) with a plain
`JSONField` + a custom `SharedBlockContentPanel` that renders the block's
form inline via a dynamically-built `StructBlock`. Goal: remove the
two-fields-one-fact smell (FK + first stream item both encoding the block
identity) and the `clean()` reconciliation between them.

Full original design is in the git history if anyone wants it.

## Why we stopped

The plan's load-bearing premise was "`StructBlock`'s form API is public and
stable — we can render it via `BlockWidget` outside a `StreamField`." That
turned out to be false at the layer we needed:

1. **Wagtail's `BlockWidget` + `w-block` Stimulus controller assumes the
   top-level block exposes `.element` on its rendered instance.** Only
   `StreamBlock` and `FieldBlock` set that. `StructBlockDefinition.render()`
   returns an object with `.container` but no `.element`, so the controller
   throws `TypeError: Cannot set properties of undefined (setting 'id')` on
   connect. Non-fatal (the form still renders), but it means the controller's
   post-render setup never runs — a silent trap for future Wagtail versions
   that add behavior there.
2. **The refactor traded a small semantic smell for a pile of framework
   internals we'd own forever** — `BlockWidget`, `js_context`, telepath
   packing, the `field_panel.html` template, widget/field coupling. Every
   Wagtail upgrade becomes a risk.
3. **`StructBlock.render_form()` was removed** in favour of `BlockWidget`, so
   the "legacy form API" escape hatch doesn't exist either.

## What we did instead

The concrete bug the refactor was motivated by — `RelatedObjectDoesNotExist`
when `clean()` runs with `block` unset — is a two-line guard:

```python
if self.block_id and self.content and len(self.content) > 0:
    ...
```

That shipped. The `max_num=1` StreamField stays. Cosmetic smell, paved road.

## If you're tempted to try again

Wait until Wagtail ships first-class single-struct field support (or until
`BlockWidget` supports `StructBlock` top-levels without the `.element`
assumption). Until then, the cure is worse than the disease.
