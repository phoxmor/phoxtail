**Breaking:** the dashboard menu list answers `{"items": [...], "total": N}` one
page at a time instead of `{"menus": [...], "total": N}`; pass `limit` and
`offset` to read on, and the `phoxtail_dashboard_list_menus` MCP tool takes the
same two arguments. Menus report `created_at` and `updated_at` in the API-wide
format. With this, every list the phoxtail API serves comes back in pages.
