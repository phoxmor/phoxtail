A field template can draw its control with Django's own widget and phoxtail's
attributes on top, using `{% widget field class="…" %}` (from
`phoxtail_core_tags`). Any `hx_*` option becomes an `hx-*` attribute, written
only when the control makes a request (`hx_get`, `hx_post`, `hx_put`, `hx_patch`
or `hx_delete`).
