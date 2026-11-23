`phoxtail.core.htmx.changed()` takes `close=False` for an action taken in
place, from a modal that stays open (a button on a row of the list the
change redraws): the change and the toast are sent as before, and the modal
is left open. `close` is keyword-only and defaults to `True`, so existing
callers are unchanged.
