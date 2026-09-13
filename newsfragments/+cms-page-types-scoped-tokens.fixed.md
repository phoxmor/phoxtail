`GET /api/cms/v1/page-types/` was unreachable with a narrowed token. It asks
for no permission, because what it returns is page type and field names read
out of installed code rather than from rows — but an endpoint that declares
nothing keeps the API-wide default, which refuses a scoped token, while its MCP
tool declares nothing either and so is offered to every credential. A token
minted with `wagtailcore.add_page` was therefore offered
`phoxtail_page_types_list`, called it, and got 403: the discovery step of every
agent page workflow failed for exactly the credentials scopes exist to make
useful. The endpoint now declares `authenticated()`, which says it is open on
purpose instead of leaving it to a default that means the opposite.
