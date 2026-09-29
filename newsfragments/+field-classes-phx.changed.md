The field classes are renamed from `fw-` to `phx-`, named block, part and
modifier: the frame every field shares is `phx-field` (`phx-field__box`,
`__control`, `__label`, `__supporting`, `phx-field--error`), and each field's
own parts carry its name (`phx-toggle__track`, `phx-phone__prefix`,
`phx-single-select-search__panel`, `phx-segmented-control--filled`). One
option row of `checkbox` and `choices` is `phx-choice`, and the seven-column
weekday grid is `grid_modifier="phx-choices--7col"`. `--fw-field-gap` is
`--phx-field-gap`. A stylesheet that overrides an `fw-` class must switch to
its new name.
