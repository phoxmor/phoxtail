The field stylesheet moved from `phoxtail_core/css/widgets.css` to
`phoxtail_core/css/forms/fields.css`. Pages that link the core sheets with
`{% include "phoxtail_core/stylesheets.html" %}` need no change; a page that
links `widgets.css` itself must switch to the new path.
