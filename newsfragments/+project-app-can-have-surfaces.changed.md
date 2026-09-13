A new project's own app subclasses `PhoxtailAppConfig`, so it can grow an HTTP
API and MCP tools the same way an installed package does — add `api/` declaring
`versions` or an `mcp/` package and they are found. Existing projects keep the
plain `AppConfig` their template gave them and are unaffected; convert it when
you want a surface.
