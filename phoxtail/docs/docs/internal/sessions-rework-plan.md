# Sessions Rework Plan

## Current broken state

`sessions_start` in `phoxtail/cli/studio/sessions.py` calls:

```python
_client.get_context(
    block=variant_data["block"]["identifier"],
    collection=variant_data["collection"]["identifier"],
)
```

`get_context` now requires `block_id: int` and `collection_id: int` (updated during the identifier→ID refactor). This call will always fail at runtime.

## Root schema gap

`GET /api/streams/v1/variants/{id}/` returns `block` and `collection` as `BlockRef`/`CollectionRef`
objects. In `phoxtail/api/streams/v1/schemas.py` these carry only:

```python
class BlockRef(Schema):
    identifier: str
    name: str

class CollectionRef(Schema):
    identifier: str
    name: str
```

There is no `id` field. So the call site can't simply be patched to
`block_id=variant_data["block"]["id"]` — the value doesn't exist in the response.

## What needs to change

### 1. Add `id` to `BlockRef` and `CollectionRef`

In `phoxtail/api/streams/v1/schemas.py`:

```python
class BlockRef(Schema):
    id: int
    identifier: str
    name: str

class CollectionRef(Schema):
    id: int
    identifier: str
    name: str
```

All variant detail endpoints that return these nested objects will then include the ID.

### 2. Fix the `get_context` call in `sessions_start`

After step 1, update `sessions_start` to:

```python
data = _client.get_context(
    block_id=variant_data["block"]["id"],
    collection_id=variant_data["collection"]["id"],
)
```

### 3. Switch session IDs from identifier to variant numeric ID

Currently session IDs are derived from the variant's string identifier:

```python
session_id = session.derive_session_id(variant_data["identifier"])
```

Switch to the variant's numeric ID so sessions are called by a stable, unambiguous key:

```python
session_id = str(variant_data["id"])
```

Update `derive_session_id` (or replace it) to handle numeric ID-based naming and collision
avoidance if the same variant is opened twice.

### 4. Update `session.json` schema

The stored `variant` block currently records the nested `block`/`collection` dicts as-is.
With `id` now present in `BlockRef`/`CollectionRef`, these will naturally carry the ID.
No structural change needed beyond step 1.

### 5. Update display code

`sessions_start` prints `variant_data["block"]["identifier"]` as a human label.
Keep this — identifier fields are intentionally informational after the rework.

## Files affected

| File | Change |
|------|--------|
| `phoxtail/api/streams/v1/schemas.py` | Add `id: int` to `BlockRef`, `CollectionRef` |
| `phoxtail/cli/studio/sessions.py` | Fix `get_context` call; switch session ID to variant numeric ID |
| `phoxtail/cli/studio/session.py` | Update `derive_session_id` for numeric ID keys |
| `phoxtail/cli/tests/test_studio_mcp.py` | Add `id` to `SAMPLE_VARIANT_SUMMARY.block` / `.collection` fixtures |
