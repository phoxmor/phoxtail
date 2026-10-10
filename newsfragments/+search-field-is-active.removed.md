The `single_select_search` field no longer takes `is_active`. To make one wait,
set `disabled=True` on the form field (for example until another field is
filled in): it is drawn inactive, with nothing to open or clear, and a pick it
already has stays shown.
