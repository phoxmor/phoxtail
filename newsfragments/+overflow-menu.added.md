An overflow menu for the actions that have no room of their own: a round ⋮
button and a menu beside it, from the `{% overflow_menu %}` tag
(`phoxtail_core_tags`), with one `phx-overflow-menu__item` link or button
per row. Content that renders no rows renders no button.

Under it, a `.phx-popover` with the `popover` attribute and
`data-popover-placement` (`bottom-end`, `right-start`, …) now opens beside
the button that names it (`popovertarget`): on that side, or on the other
where there is no room, and kept inside the window. Its alignment follows
the text direction, as CSS's start and end do. `--phx-popover-offset` sets
the gap. It is placed again on a resize (closed if that hides its button),
and closes on a choice (a link or button inside it) and on a scroll that
moves its button. A `.phx-popover` without the attribute is unchanged. The
dashboard sidebar's Website and language cards now open this way.
