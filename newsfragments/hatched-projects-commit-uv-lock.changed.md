A hatched project now commits its `uv.lock`: the template's `.gitignore` no
longer ignores it, so the exact version of every installed package is in the
project's history and each upgrade shows as a diff. An existing project picks
this up by removing the `uv.lock` line from its own `.gitignore`.
