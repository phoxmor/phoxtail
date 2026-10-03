The dashboard home opens with its title, its cards are core's clickable
cards with the icon beside the title and stack one per row on a phone, and
each app's section heading is smaller. With no cards to show, the page says
so in a plain card, without an icon. The profile page uses the same title
and page box, without the line under its title.

A custom widget template that copied the old card markup should move to
core's card classes: `dash-widget__title`, `dash-widget__description` and the
icon tile are gone. The profile page's `usr-section`, `usr-container` and
`usr-page-header` classes are gone too.
