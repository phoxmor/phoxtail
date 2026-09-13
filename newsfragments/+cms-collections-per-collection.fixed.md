The collection endpoints refused people Wagtail permits. `POST`, `PATCH` and
`DELETE` under `/api/cms/v1/collections/` asked
`user.has_perm("wagtailcore.add_collection")` and the like, but Wagtail does not
grant collections globally — it writes `GroupCollectionPermission` rows naming a
group, a collection and an action, and a grant flows down to every descendant.
`has_perm` never reads those rows, so a user granted `add` on a branch in the
Wagtail admin was turned away by the API. They are now admitted, for the branch
they were granted on and everything beneath it, and still refused elsewhere.

Reading is narrowed rather than refused: `GET /collections/` returns the
collections you may manage, and a collection outside that set answers 404 rather
than 403, so ids cannot be swept to map a tree you cannot see. The root appears
only when you hold a grant on it, which is also when you could create top-level
collections under it.

Reparenting now asks the two further questions Wagtail's own edit view asks: the
destination must be one you may add under, and a collection that carries your
own permissions cannot be moved at all — a grant flows down, so moving the node
it names would change what it reaches.
