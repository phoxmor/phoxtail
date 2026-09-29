A template can draw a form field with one of phoxtail's field templates using
`{% field "input" form.email %}` (from `phoxtail_core_tags`), and a view with
`phoxtail.core.fields.render_field("input", form["email"])`; both draw it with
Django's own field rendering. Options are passed by name, as in
`{% field "select" form.status show_label=False %}`; the field sees only what it
is given, so values set elsewhere on the page cannot change it. A misspelled form
field, an option the field does not take (the error lists the ones it does) or a
template name with a folder fails with an error instead of drawing a broken
field.
`manage.py check` (and so `runserver` and `migrate`) reads every installed
template and reports a `{% field %}` call with an unknown field or option,
with its file and line, before its page is ever drawn.
