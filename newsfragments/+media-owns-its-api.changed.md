Images, documents, video and audio moved to their own surface at
`/api/media/v1/`, out of `/api/content/v1/media/`. They are `phoxtail.media`'s
models, reached through Wagtail's swappable getters, so the media app now
serves them. **Breaking**: update any client calling the old paths, and run
`collectstatic` so the shipped JS picks up the change. The MCP tools and the
`phoxtail content` CLI were updated in the same release and need nothing from
you; the tool names are unchanged.
