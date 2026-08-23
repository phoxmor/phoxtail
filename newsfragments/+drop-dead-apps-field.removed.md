Removed the `apps` field from `phoxtail.toml` and `phoxtail hatch` no longer
writes it. It was left behind by an internal mechanism (deciding whether a
project needed a Celery service) that was replaced by a different approach
in June 2026; nothing has read this field since, and setting it never had any
effect.
