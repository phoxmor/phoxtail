`phoxtail install` no longer adds plain libraries to `INSTALLED_APPS`. It
treated any importable top-level module as a Django app, so installing
something like `httpx` or `redis` registered it and left Django importing a
non-app at startup. A package now has to carry an `AppConfig`, models, or
migrations to be registered. The module name is also read from the installed
distribution's metadata rather than guessed from the package name, so apps
whose names differ — `django-taggit` installs `taggit` — are registered
instead of silently skipped.

Its dependency handling shared `phoxtail upgrade`'s blind spot for pinned
entries and would append a second, unconstrained entry for a package already
declared with a version specifier. It also inserted new dependencies into
`dependency-groups.dev` rather than `project.dependencies`, so anything
installed into a hatched project was dropped from the production image by
`uv sync --no-dev`. When it cannot find a dependencies array to append to, it
now stops with an actionable message rather than reporting a successful
install of a package it never declared, and `--url` installs into a freshly
hatched project create the `[tool.uv.sources]` table instead of quietly
dropping the git source and resolving against PyPI — and when the table
already exists, the source is inserted into it rather than appended to the
end of the file, where it could land in whichever table came last. A package
declared only in the dev dependency group no longer counts as installed,
since the production image drops that group.
