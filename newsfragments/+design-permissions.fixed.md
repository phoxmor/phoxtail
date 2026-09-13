The thirty design endpoints at `/api/design/v1/` asked for nothing beyond being
authenticated, so any account could rewrite the palettes and fonts every page on
the site renders with. Each endpoint now names the permission its act needs —
`phoxtail_design.view_palette` and its add/change/delete siblings, and the
equivalents for palette sets, palette roles, font families, font roles and font
weights — and a refusal names the permission missing, so an administrator can
see what to grant.
