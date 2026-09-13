`GET /api/streams/v1/schema-catalog/` and `GET /api/streams/v1/page-types/` were
unreachable with a narrowed token. Both return names read out of installed code
— the schema field types a block may use, and the app labels page types come
from — so neither asks for a permission. But an endpoint that declares nothing
keeps the API-wide default, which refuses a scoped token, so "asks for nothing"
was being served as "closed to everyone narrowed".

Both now declare `authenticated()`. An agent reads the schema catalogue before
it can phrase a block schema at all, and the CLI reads the page-type labels
before loading a studio dump; neither could do so with a token minted for the
job. Anonymous callers still get 401.
