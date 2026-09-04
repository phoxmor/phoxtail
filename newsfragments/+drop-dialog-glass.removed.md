Removed the `.phoxtail-dialog--glass` CSS class. It provided the glass surface
for centered dialogs, but its only consumer became a right-to-left drawer and
switched to `.phoxtail-drawer--glass`, leaving nothing using it. Pages styling
a centered dialog with it will lose the background, border, and shadow; add
those to the consumer's own class, or reuse `.phoxtail-drawer--glass` if a
drawer suits.
