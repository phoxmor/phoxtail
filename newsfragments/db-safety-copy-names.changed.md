The copy that `db pull`, `db restore` and `db push` take of a database
before replacing it is now named `<project-slug>_<DJANGO_ENV>_before-<step>.sql`
(for example `mysite_production_before-push.sql`) instead of
`pre_<step>_safety.sql`, so it says which site and environment it holds.
Each step still keeps one copy, overwritten by its next run, and the copy
is written whole or not at all. The commands stop before changing anything
if `DJANGO_ENV` is missing from the `.env` next to the database they
replace. `db restore` refuses its own `before-restore` copy, since taking
the copy first would overwrite it. Old `pre_*_safety.sql` files are no longer written and can be
deleted.
