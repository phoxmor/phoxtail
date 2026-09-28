The `select` field now lets Django draw the dropdown and its options: grouped
choices work, the chosen option is marked by its value, and `required` follows
the HTML rule. A field template refuses a form field whose widget it cannot
draw — radio buttons given to `select`, a checkbox to `input` — with an error
naming the field, instead of drawing a broken field.
