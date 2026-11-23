Escape in a core drawer closes only what is open inside it first: a
popover or a modal `<dialog>`, a field's open panel (single select search),
the language menu. Before, the same press also closed the drawer. A held
Escape closes one drawer, not every level. The modal now listens for the key
going down on the window and leaves alone any Escape a listener has already
taken with `preventDefault()`, which is how a page's own script keeps a press
for itself (a script that relied on `stopPropagation()` on keyup must move to
keydown). The variant drawer's image viewer does this now.
