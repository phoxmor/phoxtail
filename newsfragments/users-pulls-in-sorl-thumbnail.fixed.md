`phoxtail.users` now brings `sorl.thumbnail` into `INSTALLED_APPS` when settings
are wired, so a project or test settings module that installs the users app can
draw avatar thumbnails without listing sorl by hand.
