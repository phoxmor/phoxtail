Wagtail 8.0 is now the supported version, raising the `engine` extra from
`wagtail>=7.4.2,<8.0` to `wagtail>=8.0,<9.0`. Django stays at `<6.0` and the
Python floor stays at 3.11: Wagtail 8 runs on Django 5.2, so neither has to
move yet. `wagtailmedia` is raised to `>=0.18.1`, which carries a permission
fix for the media chooser — it previously exposed a media item's id, title and
edit URL to users without access to it.

Two Wagtail 8 changes are worth knowing about. Image renditions no longer
convert AVIF and WebP to PNG, so sites serving those formats will now emit them
directly; set `WAGTAILIMAGES_FORMAT_CONVERSIONS` to restore the old behaviour.
And `menu_order` is now respected between viewsets inside a `ViewSetGroup`,
which reorders some admin menus.
