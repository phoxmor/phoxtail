`GET /api/cms/v1/sites/` and `GET /api/cms/v1/sites/{id}/` asked for nothing
beyond being authenticated, listing every site in the project along with its
hostname, port and root page. Both now require `wagtailcore.view_site`, and the
create, update and delete endpoints declare `add_site`, `change_site` and
`delete_site` at the door rather than checking them partway through the body —
so a caller without the right is refused before anything about the site is
revealed, including whether it exists.

`GET /api/cms/v1/locales/` likewise now requires `wagtailcore.view_locale`.

The matching MCP tools name the same codenames, so a token narrowed to one of
them is offered exactly the tools whose doors will open.
