`{% languages %}` (in `phoxtail_core_tags`) lists the languages a page can be
read in, each with that page's address in it, and
`phoxtail_core/language_menu.html` draws them as a small button that opens a
menu. Both are empty on a site that serves one language, and the menu draws
nothing until the site publishes Django's `set_language` view.
