`phoxtail install` and `phoxtail upgrade` check for uv, and for a running
Docker unless `--no-build` is given, before they edit `pyproject.toml`.
They no longer stop halfway, with the dependency locked in but the image
never built or migrated.
