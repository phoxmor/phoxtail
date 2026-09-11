The variant-editing session tools are no longer offered to an agent reaching
this project's MCP server over HTTP. They write files to the server's own disk
and return the paths, which name nothing an agent on another machine can open
— and they do not fail saying so, they succeed and hand back directions to
somewhere else. Over a local connection they behave exactly as before.
