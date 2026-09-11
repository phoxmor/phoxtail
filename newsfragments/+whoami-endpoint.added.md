`GET /api/whoami/` reports the identity and ceiling of the credential making
the request: email address, user uuid, superuser flag, whether the token is
unrestricted, its scopes, and its expiry. It exists for callers that hold a
token without being able to read it — the MCP server forwards an opaque Bearer
and is never the authority on what it contains. It is the one endpoint
reachable by every credential, including narrowly scoped ones, since a caller
cannot discover its own limits if the endpoint reporting them sits behind them.
