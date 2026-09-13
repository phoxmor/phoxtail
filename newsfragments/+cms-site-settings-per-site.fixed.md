The site-settings, font and palette endpoints asked nothing beyond being
authenticated — any account that could log in could read and rewrite a site's
branding images, font assignments and palette assignments. All twelve now ask
Wagtail who may change settings for that site.

Wagtail 8 grants settings **per site**, through `GroupSitePermission` rows, so
the check is made against the site being addressed rather than globally: a
grant on one site does not reach another. Global grants keep working, because
Wagtail's own policy honours both.

The font and palette endpoints name `view_sitesetting` and `change_sitesetting`
rather than permissions of their own. They edit `ParentalKey` children of
`SiteSetting`, through `InlinePanel`s inside its form, and Wagtail checks only
the parent — so a `change_sitesettingfont` grant is a row the admin can tick and
nothing anywhere reads. Reading asks for `change` for the same reason: Wagtail's
settings surface has no read-only view and names no view action at all.
