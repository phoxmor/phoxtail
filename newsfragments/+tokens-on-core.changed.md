The API Tokens admin uses core's list page, surfaces and drawers: a grey page
with white cards, core's search, Filters, Create and paginator, and every
drawer `modal_drawer.html`. A token's drawer shows its details in cards and
Revoke as a danger card; a revoke closes it and the list redraws itself. After
Create, the drawer gives way to a dialog in the center that only its own
buttons close: the raw token, shown once, hidden until its eye shows it, with
a copy button and "Copy and close". Cards show an Expired tag as well as
Revoked. The view's own stylesheet, its paginator and the unused revoke
dialog are gone.
