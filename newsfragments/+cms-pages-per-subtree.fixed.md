Reading pages asked for nothing. `GET /api/cms/v1/pages/`, `GET /pages/{id}/`,
`GET /pages/{id}/body/` and `GET /pages/{id}/blocks/{uuid}/` served every page in
the project to any account that could log in — and served it as its *latest
draft*, so unpublished and unreviewed edits were readable by anyone with a
login. All four now narrow to the pages the caller holds a Wagtail grant on, and
a page outside that set answers 404 rather than 403 so ids cannot be swept.

The `parent=` filter on the listing is resolved within the same set. Narrowing
only the results would have left the filter able to tell a real page from an
absent one, which maps the tree the narrowing exists to hide.

The screenshot views under `/phoxtail-agent/screenshot/` had the same hole and a
wider one: they checked `access_chatbot` and then rendered any page by id, so
anyone able to drive the renderer could photograph an unpublished draft in a
subtree they were never granted. They now ask the same question the page read
asks.

The write endpoints already asked Wagtail per page and are unchanged. Every page
endpoint and every page MCP tool now also names the codename of its act, so a
token can be narrowed to reading, editing, publishing or creating pages.
