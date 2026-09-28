The `number` field now lets Django draw its control, so a decimal value in a
language that writes decimals with a comma (Greek, German) appears in the field
instead of leaving it empty, and `min`, `max` and `step` come from the form.
