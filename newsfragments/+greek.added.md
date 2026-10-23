Phoxtail speaks Greek. The dashboard, the authentication pages, the profile,
the admin's snippets and settings, and the page bar and chatbot follow the
active language, with one Greek catalogue in `phoxtail/translations/locale/el`;
text the bar's and chatbot's scripts build in the browser is still English.
Because phoxtail's translations come first in `INSTALLED_APPS`, its Greek also
takes over allauth's on the strings the authentication pages share with it.

Model fields and models now carry translatable labels. Each app gains a
`*_translatable_labels` migration that changes no database table. The labels on
`UUIDMixin` and `TimestampMixin` reach every model built on them, so a package
with its own models on those mixins sees a pending migration of the same kind
until it generates one; nothing changes at runtime in the meantime.
