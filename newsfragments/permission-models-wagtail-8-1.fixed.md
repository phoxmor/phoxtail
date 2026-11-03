Upgrading to Wagtail 8.1 no longer makes `makemigrations` offer to delete
three phoxtail permission tables (remotes, streams and access tokens). If
you already generated such a migration, delete it; do not apply it.
