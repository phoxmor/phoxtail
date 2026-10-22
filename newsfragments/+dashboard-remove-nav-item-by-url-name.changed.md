`DashboardModule.remove_nav_item()` now takes the item's `url_name` instead of
its label. Labels are translated, so removing an item by its English label
failed on a site in another language.
