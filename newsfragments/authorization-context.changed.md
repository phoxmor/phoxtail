API endpoints now receive an `AuthorizationContext` as `request.auth` instead
of a `User`. Read `request.auth.user` for the person and `request.auth.token`
for the credential they arrived with (`None` for a browser session). Both
authentication backends resolve the same shape, so endpoints no longer differ
by how the caller logged in, and predicates passed to `Authorize` now receive
the context rather than the user.

`phoxtail.tokens.auth.authenticate()` changes with it: it returns the
`AccessToken` it looked up rather than that token's user, so callers can reach
the scopes and type that were previously discarded. Use `token.user` for the
owner. Projects with their own API endpoints, `Authorize` predicates, or direct
calls to `authenticate()` need the corresponding one-line change.
