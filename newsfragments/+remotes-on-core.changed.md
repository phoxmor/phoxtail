The Remotes admin uses core's list page, surfaces and drawers: a grey page
with white cards, its icon before its title, core's search, Connect and
paginator, and every drawer `modal_drawer.html`. Connect and a remote's
drawer show its fields in cards; the remote's drawer is titled by its name
and offers Disconnect as a danger card. A connect, save or disconnect closes
the drawer and the list redraws itself; a refused one keeps the drawer open
with its errors. The view's own stylesheet and the unreachable disconnect
dialog are gone.
