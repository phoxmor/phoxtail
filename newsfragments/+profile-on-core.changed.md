The profile page and its Edit drawer use core's surfaces. The page is a
bento of four cards: the member (avatar, name, Edit) standing tall, then
their personal details, their contact, and their account (member since,
username, Change password and Manage email); three columns on a wide
screen, two on a tablet, one on a phone. Each detail is its label over its
value; initials without a photo are in the surface colours. The drawer is
`modal_drawer.html` with its fields in titled cards, the avatar chosen with
a core button; a save closes it through core's `closeModal` event, a
refused one keeps it open with the errors. The page's words are
translatable and in sentence case. The buttons now live in `user_info.html`
with the cards, redrawn with them on a save; a project overriding it or
`index.html` should move its buttons there.
