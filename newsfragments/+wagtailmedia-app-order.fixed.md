`wagtailmedia` now sits above `wagtail.snippets` in `INSTALLED_APPS`, so a
project starts under wagtailmedia 0.19.0. That release registers the media
permission policy in its `AppConfig.ready()` while its `wagtail_hooks` module
looks the policy up at import time, and `wagtail.snippets.ready()` imports every
app's hooks. With snippets first, the lookup created a fallback policy and the
real registration was refused with `ImproperlyConfigured`. Hatched projects
carry the same ordering fix in their settings template; existing projects need
the app moved by hand.
