A core drawer (`phoxtail_core/modal_drawer.html`) no longer stops clicks
inside it from reaching the page, so a page's own listeners on the document
(a menu that closes on a click elsewhere, say) hear them. Its overlay
closes it only when a click is pressed and released on the overlay itself:
a text selection dragged from inside the drawer and released outside it no
longer closes the drawer and loses what was typed. `dismissModal(el, event)`
takes the click for that check; called without one it behaves as before. A
script's `click()` on the overlay, with no press behind it, no longer closes
the drawer: close it with `closeModal(el)`.
The access tokens' Filters drawer follows the same rule.
