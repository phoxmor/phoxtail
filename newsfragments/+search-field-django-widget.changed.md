`SingleSelectSearchField` declares Django's `HiddenInput`, the box that carries
the pick, and the `single_select_search` field lets Django draw it. The field
refuses a form field with another widget, such as a plain `ModelChoiceField`'s
dropdown, which it cannot draw.
