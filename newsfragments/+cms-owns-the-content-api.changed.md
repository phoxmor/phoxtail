The content API moved into the CMS app and merged with the site-settings
surface: everything that was `/api/content/v1/*` is now `/api/cms/v1/*`, served
alongside `/api/cms/v1/site-settings/`. Pages, bodies, blocks, collections,
page types, locales and sites are all Wagtail entities, so the CMS app owns
them. **Breaking** for any client calling the old paths, and a site upgrading
needs `collectstatic` so the shipped page-bar JS picks up the change. The MCP
tools and the `phoxtail content` CLI were updated in the same release and keep
their names.
