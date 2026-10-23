phoxtail now needs django-allauth 65.20.1 or later, which brings allauth's
fixes since 65.18: rate limits that hold under concurrent requests, safer
redirects when `ALLOWED_HOSTS` allows every host, and a cancelled login by
code that no longer carries over into the next one. Relock with
`uv lock --upgrade-package django-allauth`.
