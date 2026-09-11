The MCP server now resolves who is calling before anything runs. A request
arriving over HTTP has its bearer introspected at `GET /api/whoami/` — the
project's API remains the only thing that reads a token — and the caller's
name and the ceiling of their credential travel with the request from there.
A request carrying no credential is now answered `401` with the standard
`WWW-Authenticate` challenge, rather than reaching the tools and failing
inside each one. Running over stdio is unchanged: there is no inbound
credential to resolve, and nothing is asked for.
