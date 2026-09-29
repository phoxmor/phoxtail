A `search` field draws a list's search bar:
`{% field "search" filterset.form.search count=page.paginator.count hx_get=search_url hx_include="#filters" %}`
gives one pill with a magnifier, the box, a clear button once there is text
and, with `count`, the number of results. Typing sends the request half a
second after the last key; Enter and the clear button send it at once,
without reloading the page. The answer is expected to redraw the list
(`hx_swap` defaults to `none`). Its look is filled and small, for toolbars.
