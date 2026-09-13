The block, category, collection, variant and shared-block endpoints at
`/api/streams/v1/` asked for nothing beyond being authenticated, so any account
could rewrite every block and variant the site is built from. Each endpoint now
names the permission its act needs — `phoxtail_streams.view_block` and its
add/change/delete siblings, and the equivalents for block categories, variant
collections, block variants and shared blocks — and a refusal names the
permission missing.

Putting a block in a category asks for `change_block`, not for any permission
over the category: the act changes the block, and the category is only
referenced. Without `view_blockcategory` a caller can use category ids they
already know but cannot discover them, which is deliberate.

`/schema-catalog/` and `/page-types/` name no permission. Neither returns
project data — the first describes this app's own schema field types, the
second lists the app labels installed in the project — and an endpoint naming
no scope is already closed to a narrowed token.
