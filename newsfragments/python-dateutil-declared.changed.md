The `engine` extra now declares python-dateutil (2.8.2 or later, below 4),
which `phoxtail.users` uses to count ages. It used to arrive only because
celery depends on it. Installed versions do not change.
