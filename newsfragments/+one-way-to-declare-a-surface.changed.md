An app declares its HTTP API and its MCP tools one way only: subclass
`PhoxtailAppConfig` and ship `api/` declaring `versions` and `mcp/`. The three
superseded mechanisms are gone — the `api_version_router` attribute, the
`phoxtail.mcp_modules` entry-point group, and `[mcp] extra_modules` in
`phoxtail.toml`. **Breaking** for any package still declaring one; each is
replaced by moving the surface into the app's own `api/` or `mcp/` package.
