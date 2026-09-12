Phoxtail apps now declare their HTTP API and MCP tools by convention instead of
by registration: an app that subclasses `PhoxtailAppConfig` and ships `api/` or
`mcp/` is found automatically. Existing declarations keep working while apps
migrate one at a time.
