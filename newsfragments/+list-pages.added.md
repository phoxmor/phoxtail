Core draws a list page: `components/lists.css` (loaded by
`phoxtail_core/stylesheets.html`) holds the page column (`phx-list`), the card
grid (`phx-grid`) with a card's meta rows and the button that makes the whole
card open its drawer, the empty state (`phx-empty`), a filter's label and a
form card's fields.
`{% paginator %}` (`phoxtail_core_tags`) draws the paginator for any list,
given the page, the view that answers a page, what the request carries and
the page's query name. It is First, Previous, five page numbers around the
current page, Next and Last, each its own circle (`components/paginator.css`):
the window slides at either end, so every page draws as many buttons and the
paginator keeps its width. The ends are icons named for screen readers (new
`first_page` and `last_page` icons); where there is nowhere to go, the circle
stays and its icon dims. A phone keeps the three numbers nearest the current
page, the narrowest screens only the current one. Asking for a page from below
the list scrolls the list's top back into view (`paginator.js`).
