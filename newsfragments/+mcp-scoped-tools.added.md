`phoxtail.mcp.authorization.scoped()` — the `auth=` check for an MCP tool a
scoped token may reach, named after the codename of the act it performs, as
`phoxtail.api.auth.scoped()` already is for endpoints. A tool whose codename a
credential does not cover is left out of that caller's catalogue and does not
resolve by name. An unrestricted token reaches everything, and a shortfall
names the codenames the caller would need.
