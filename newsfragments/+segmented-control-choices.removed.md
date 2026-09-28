The `segmented_control_choices` field is gone: `segmented_control` draws one
segment per choice of any `RadioSelect` field, with Django drawing each radio,
and every `hx_*` option reaches each segment. Replace
`{% field "segmented_control_choices" … %}` with `{% field "segmented_control" … %}`.
The `label_off`, `label_on` and `locked` options are gone: the segments take the
field's choice labels, and a disabled form field locks the whole control. A
field with no value ticks no segment, so give it an initial value.
