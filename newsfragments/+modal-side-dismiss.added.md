`phoxtail_core/modal_drawer.html` takes where the modal sits (`side`: right,
left or center, which also decides how it moves) and how it closes
(`dismiss`: "button" leaves only its own buttons, for a secret shown once),
and its whole top part is a `header` block. `phoxtail.core.htmx.replace_modal()`
answers with a modal in place of the one the request came from, at whichever
level, after the old one leaves with its own motion. A field drawn with
`copy=True` over a password widget shows its eye and its copy button side by
side; the eye is named after its field ("Show Token"). Long modal and card
titles wrap instead of scrolling the modal sideways.
