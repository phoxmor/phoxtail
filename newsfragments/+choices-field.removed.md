The `checkbox_multiple` and `radio_select` fields are gone: one `choices` field
draws a group of options as radio buttons or checkboxes, as the form's widget
says, with Django drawing each option — grouped choices get their heading, and
every `hx_*` option reaches each input. Replace `{% field "checkbox_multiple" … %}`
and `{% field "radio_select" … %}` with `{% field "choices" … %}`. The
`label_slice_index` option is gone: give the form field the short labels it
should show, e.g. Django's translated `django.utils.dates.WEEKDAYS_ABBR`. A
required radio group is marked `required`, so the browser asks for a choice
before sending.
