The password field's show/hide button is driven by one shared script,
`phoxtail_core/js/fields.js`, loaded by `phoxtail_core/scripts.html`, instead of
an inline script repeated next to every password field. A page that draws a
password field must include `phoxtail_core/scripts.html` for the button to work.
