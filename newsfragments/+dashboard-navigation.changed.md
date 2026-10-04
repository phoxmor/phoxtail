The dashboard's navigation is one system with its pages. On a computer the
sidebar is a card floating just off the window's edges with its logo centered,
and the top bar is gone: the site's own pages sit behind a Website row and the
language behind a row of its own, each opening a card beside the sidebar on a
click or on hover. On a phone the menu opens as a drawer like every other, the
top bar and dock sit on the page's ground with a faint edge while content
scrolls under them, the dock marks the page you are on with a pill in the
brand colour, and its More sheet and the language list follow the same
surfaces. Labels are in sentence case.

The top bar's site menu template (`phoxtail_dashboard/navigation/menu.html`)
and its `dash-menu` classes are removed; a site that overrides or styles them
should move to the sidebar's Website card.
