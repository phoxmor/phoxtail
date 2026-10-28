`phoxtail db backup` now names its files `<project-slug>_<DJANGO_ENV>_<UTC
time>.sql`, for example `mysite_production_2026-10-28_10-19-28.sql`, so a
backup says which site and which environment it holds even after it is
copied elsewhere. The environment is read from the `.env` next to the
database that is dumped, and the command stops with an error if
`DJANGO_ENV` is missing. A failed dump leaves no file behind. Existing
backups keep their names and `db restore` still accepts them.
