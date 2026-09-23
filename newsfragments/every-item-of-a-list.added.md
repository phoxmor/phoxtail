`phoxtail.core.paging.every_item(fetch, **filters)` reads a whole paged list,
page by page, for callers that need all of it rather than a page, and returns
it all at once. It raises `ListChanged` when it sees the list move while it
reads — the total changing, a row arriving twice, the list running out early —
and `NotAPagedList` when the server does not answer with `{"items", "total"}`. It needs no Django, so command-line tools
can use it. `DEFAULT_LIMIT` and `MAX_LIMIT` live beside it and the API takes
its bounds from there.
