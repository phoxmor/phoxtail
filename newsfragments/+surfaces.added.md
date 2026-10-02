One surface model for every page: the page or drawer is the ground (`phx-ground`:
grey, near-black in dark mode), what stands on it rises (`phx-card`, white with a
light shadow; `phx-card--clickable` adds a ring on hover and keyboard focus;
`phx-card__title`, `phx-card__text`; `phx-card--flush` drops the padding for
a card whose parts reach its edges), and what floats above everything is a
`phx-popover`. Each box hands the controls it holds their fill and shadow
(`--phx-control-background`, `--phx-control-shadow` and their `-hover`), so a
button is white and lifted on the page and a quiet tint inside a card. An admin
view opts in with `{% block bodyclass %}phx-ground{% endblock %}`; one that
does not keeps Wagtail's white. The dashboard's content area is ground already.
Use these boxes; never paint a background.
