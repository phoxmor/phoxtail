The `textarea` field now lets Django draw its control, so it carries everything
the form declares — such as `maxlength`, which now stops typing at the limit
instead of rejecting the text on save — and a text that starts with a blank line
keeps it.
