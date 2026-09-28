The `null_boolean_select` field is gone: draw a yes/no filter with
`{% field "select" … %}` and give its form field
`widget=phoxtail.core.fields.BooleanFilterSelect`, a dropdown of All, Yes and No.
Its first choice is now translated with the page; the old field showed
"Unknown" in any language but English.
