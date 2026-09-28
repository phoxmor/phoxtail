The `datetime` field is gone: `input` draws date-times too, with the calendar
button, and writes the value in the form the browser's picker reads. Replace
`{% field "datetime" … %}` with `{% field "input" … %}`.
