The cross-project sync endpoints asked for nothing beyond being authenticated.
`GET /api/streams/v1/variants/{id}/pull/` now asks for
`phoxtail_streams.view_blockvariant`, and `POST /variants/push/` asks for all
six codenames its envelope can write — add and change for the variant
collection, the block and the block variant — because which of the three it
creates or updates depends on the payload. A push carries the token of a
person on the other project, so it asks for what those acts ask for when
performed here by hand.
