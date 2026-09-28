Typing in a `single_select_search` field no longer fails with a
`FilterFieldError` when the form narrows the field's choices: the search
looks only among the allowed choices, by id. A model searched this way
declares `index.FilterField("id")` in its `search_fields`; the user model
does.
