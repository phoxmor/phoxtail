**Breaking:** the page, collection, locale, site and site-setting font and
palette lists now answer `{"items": [...], "total": N}` instead of naming the
list after the resource (`{"pages": [...]}`, `{"locales": [...]}`,
`{"sites": [...]}`, `{"fonts": [...]}`, `{"palettes": [...]}`). Pass `limit`
and `offset` to read on, as on every paged list; the matching MCP tools take
the same two arguments. Collections, locales, sites and site-setting
assignments used to arrive all at once and now arrive 50 at a time by
default. A page search returns its matches in tree order rather than ranked
by relevance.
