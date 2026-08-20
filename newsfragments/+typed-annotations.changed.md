The annotations shipped under `py.typed` are now verified rather than asserted —
the package type-checks clean, and CI fails on any error. Two signatures were
corrected against their callers in the process: `collection_id` on the studio
client's `create_variant` accepts `None`, and `Provider` subclasses now declare
their one-argument constructor on the base class.
