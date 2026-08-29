Admin menu entries that shared a `menu_order` no longer sort arbitrarily. Font
Roles and Palette Roles were both 150, and Wagtail 8 orders group members by
`menu_order` rather than by their position in the group, so the tie surfaced as
Palette Roles jumping to the middle of the Design menu. The design viewsets are
renumbered to restore the intended order, and Remotes moves off 601 so it no
longer ties with API Tokens in the settings menu.
