The `dashboard_icon_path` template tag is removed, and so is the `icon`
parameter of `phoxtail_core/copy_key_button.html`. Every icon is now drawn
with `{% icon "<name>" %}`, so a missing name renders nothing and logs a
warning everywhere instead of failing the page in the dashboard navigation.
Templates that used `{% dashboard_icon_path name as path %}{% include path %}`
should use `{% icon name %}`.
