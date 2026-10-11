A toast (`showToast`) no longer closes the open modal. To close the modal an
action came from, send the new `closeModal` client event beside the toast
(`trigger_client_event(response, "closeModal")`): it closes the modal holding
the element that sent the request, at whichever level, so an action in a
stacked drawer no longer closes the drawer underneath. A permission refusal
now leaves its modal open.
