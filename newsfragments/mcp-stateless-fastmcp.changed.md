The MCP server is built on `fastmcp` and speaks the stateless MCP protocol
(2026-07-28). Every request now carries its own protocol envelope instead of
negotiating a session first, so the server can be restarted or replicated
without dropping clients. `phoxtail mcp serve` and `--http` are unchanged in
use; `mcp>=1.29,<2` is replaced by `fastmcp-slim[server]`, which supplies the
server, the peer client and the caller-identity lookup as one dependency.
