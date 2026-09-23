**Breaking:** the streams variant, block, collection, block-category,
shared-block and block's-categories lists answer `{"items": [...], "total": N}`
one page at a time instead of `{"variants": [...]}`, `{"blocks": [...]}`,
`{"collections": [...]}` and `{"shared_blocks": [...]}`; pass `limit` and
`offset` to read on. Block categories now arrive 50 at a time by default
instead of 100, and a search on these lists returns matches in list order
rather than ranked by relevance. Replacing a block's categories
(`PUT /blocks/{id}/categories/`) answers with the resulting list itself
instead of `{"items", "total"}`. Shared blocks report `created_at` and
`updated_at` in the API-wide format, and the block they embed now carries its
real `source_app` and `page_types` instead of empty values.
`phoxtail studio dump` and `load`, and the admin sync screens, read every page
of a list, so a project with more than one page of variants or blocks is
dumped, loaded and compared whole; they stop with a message if the list
changes while it is read, or if a remote runs a phoxtail from before lists
were paged. `phoxtail studio list` takes `--limit` and `--offset` and titles
a partial page "Variants (50 of 120)". The streams MCP list tools take
`limit` and `offset`.
