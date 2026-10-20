Core draws a list page: `components/lists.css` (loaded by
`phoxtail_core/stylesheets.html`) holds the page column (`phx-list`), the
toolbar (`phx-toolbar`: title, search and buttons), the card
grid (`phx-grid`) with a card's meta rows and the button that makes the whole
card open its drawer, the empty state (`phx-empty`), the paginator
(`phx-paginator`), a filter's label and a form card's fields.
`{% paginator %}` (`phoxtail_core_tags`) draws the paginator for any list,
given the page, the view that answers a page, what the request carries and
the page's query name.
