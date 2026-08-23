`phoxtail upgrade phoxtail` now compares the project's phoxtail-owned
declarations in `pyproject.toml` against the current project template and
offers to apply the difference before locking. Previously it only advanced
the lockfile, so a project kept declaring whatever extras it was hatched
with even after the template moved a dependency to a different one.
