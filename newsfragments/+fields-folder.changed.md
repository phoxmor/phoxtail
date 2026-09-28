Phoxtail's field templates moved from `phoxtail_core/forms/widgets/` to
`phoxtail_core/forms/fields/`, and the `htmx/` copies are gone: `input`,
`select`, `number` and `datetime` take the `hx_get`, `hx_target`, `hx_swap`,
`hx_trigger`, `hx_include` and `hx_vals` options themselves, and the fields that
lived only under `htmx/` (`toggle`, `segmented_control`,
`segmented_control_choices`, `choice_dropdown`, `null_boolean_select`,
`single_select_search`, `multi_select_chips`) sit beside the others. A template
that includes the old paths must switch to `{% field "select" form.status … %}`,
and a view to `render_field("select", form["status"], …)`.
