# Body Validation Gap

## The problem

`PUT /api/content/v1/pages/{id}/body/` has no validation layer between `StreamBlock.to_python()` and `page.save_revision()`. Wagtail's `to_python` is intentionally permissive (it must rehydrate historical revisions with drifted schemas), so structurally-plausible but semantically wrong JSON reaches storage unchecked.

**Observed failure:** an agent passed `variant: "default"` (string) where the StreamField expected a numeric FK integer. `to_python` accepted it, the revision was saved, and the ETag advanced. The subsequent GET returned a 500 because rendering tried to use `"default"` as a database PK. The page was in a corrupted-but-saved state.

This is not a Wagtail bug. The admin avoids it by routing through `ModelForm.full_clean()`, which calls `StreamBlock.clean()` on the way down. We bypass that entirely.

## The fix

Call `StreamBlock.clean()` between `replace_body()` and `page.save_revision()` in `put_body`:

```python
from django.core.exceptions import ValidationError

stream_value = getattr(page, field_name)
try:
    stream_value.stream_block.clean(stream_value)
except ValidationError as e:
    raise HttpError(400, ...)
```

Whether this catches a given type mismatch depends on the block class declaring that field:

- `SnippetChooserBlock(BlockVariant)` or `IntegerBlock` — `clean()` does a real FK lookup / int coercion, mismatch raises `ValidationError`. ✓
- `CharBlock` — `clean()` accepts the string, 500 still happens on render. ✗

**Before shipping:** grep the actual block definition for `variant` and any other FK-style fields, confirm the block type, then write a one-shot script or test that constructs a bad payload, calls `clean()`, and asserts `ValidationError` is raised.

**Error shape:** Wagtail raises `StreamBlockValidationError` (a `ValidationError` subclass) which wraps per-block errors indexed by position — not a flat list. The 400 translator must handle this structure or the agent gets a useless generic message.

## Broader scope

The same gap exists in the scalar PATCH path. `apply_patch` on contributions does raw `setattr` without `full_clean()`, so a wrong-type `author` ID would be silently stored. Consider `page.full_clean(exclude=["body"])` before `save_revision` in the PATCH handler.

## Partial mitigation already in place

The `id` field is now exposed on `VariantSummary` and `BlockVariantRef`, and both the `phoxtail_studio_list_variants` and `phoxtail_pages_replace_body` MCP tool descriptions explicitly state that `variant` must be the integer `id`, not the string `identifier`. This reduces the probability of the mistake but does not eliminate it.
