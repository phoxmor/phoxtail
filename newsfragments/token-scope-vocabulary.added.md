Token scopes are validated when a token is issued. A scope must name a real
Django permission — `phoxtail_streams.change_blockvariant`,
`wagtailcore.publish_page` — and a typo is refused with the correct spelling
rather than stored. There is no separate scope vocabulary to learn or maintain:
the permission table already lists every valid scope, and an app contributes
its own simply by migrating.
