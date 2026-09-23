**Breaking:** the palette-set, palette, palette-role, font-family,
font-weight and font-role lists answer `{"items": [...], "total": N}` one page
at a time instead of naming the list after the resource (`{"palettes": [...]}`
and so on); pass `limit` and `offset` to read on, and the matching MCP tools
take the same two arguments. A search on these lists returns matches in list
order rather than ranked by relevance. Palette sets, palettes, font families
and font weights report `created_at` and `updated_at` in the API-wide format
(`2026-08-12T08:15:47.569Z`) instead of Python's own.
