`POST /api/streams/v1/context/` asked for nothing beyond being authenticated,
while returning a block's field schema and the full html, css and javascript of
every reference variant asked for. It now asks for `view_block` and
`view_blockvariant` together. The palette and font roles it also returns are a
vocabulary of names and identifiers rather than design data, so no design
permission is required for them — a caller with no design rights still gets
block context.

The studio tools that reach past this app now name what they reach:
`phoxtail_studio_render_block` and `phoxtail_studio_screenshot_page` name
`phoxtail_agent.access_chatbot`, which is what the screenshot view itself
requires, and `phoxtail_studio_capture_variant_previews` names the variant and
block it reads before returning its playbook. An MCP tool that names nothing is
offered to every credential, so leaving these bare would have put them in front
of tokens narrowed to something else entirely.
