`phoxtail.core.testing` calls `wire_apps()` itself: every dependency, default
setting, middleware and context processor an app declares lands in the test
settings through the same pass a hatched project runs, without being copied
out by hand. A package that appends its own app to
`INSTALLED_APPS` after importing the base calls `wire_apps(globals())` once
more, as the module's docstring shows.
