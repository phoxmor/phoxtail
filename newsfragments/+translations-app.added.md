phoxtail's translations live in a new app, `phoxtail.translations`.
`phoxtail.core` asks for it, so `wire_apps` installs it first; a project that
lists its apps itself must put it above every app with translations of its own
(allauth, Wagtail, Django's), or a startup warning
(`phoxtail_translations.W001`) names the apps in the way. Beside phoxtail's own
sentences it holds phoxtail's wording for sentences allauth and Django write,
where theirs reads wrong, one file per package and language
(`packages/allauth/el.po`). `make translations` gathers phoxtail's sentences
and compiles both; Django's `compilemessages` would leave the corrections out.
