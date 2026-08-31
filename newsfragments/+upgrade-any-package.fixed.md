`phoxtail upgrade` now works for any package in the project's dependency graph.
It matched a name in `pyproject.toml` only when a closing quote or an extras
bracket followed it, so every pinned dependency — `wagtail>=7.4.2,<8.0` and the
like — was refused as "not listed in pyproject.toml". Packages are now resolved
through `uv.lock`, which also covers transitive dependencies a project never
declares itself. When the lockfile does not move, the command says why and
stops instead of rebuilding and restarting the stack for an unchanged
resolution.
