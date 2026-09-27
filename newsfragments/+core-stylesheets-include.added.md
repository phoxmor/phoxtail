A page can load everything phoxtail's shared styles and scripts need with two
lines, `{% include "phoxtail_core/stylesheets.html" %}` and
`{% include "phoxtail_core/scripts.html" %}`; the first also applies the site's
colours and fonts. Phoxtail's admin views, dashboard, CMS pages and
authentication pages now use them.
