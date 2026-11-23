`phoxtail lint`, `phoxtail install` and `phoxtail upgrade` now run their
containers as you, as every other command that starts containers already
did. Files they wrote into the project, such as those `lint` reformats,
could end up owned by user 1000 instead of you.
