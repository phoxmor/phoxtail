The `number` field is gone: `input` draws numbers too, taking the box type from
the form's widget. Replace `{% field "number" … %}` with `{% field "input" … %}`
and `render_field("number", …)` with `render_field("input", …)`.
