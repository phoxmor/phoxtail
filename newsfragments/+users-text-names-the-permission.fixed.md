The users MCP tool descriptions, the OpenAPI descriptions of the users and
genders endpoints, and the 403 message the tools return all said the surface
required a superuser. It has not since each endpoint started naming the
permission its act needs, and a caller holding exactly that permission was
being told by the tool itself that it would not work. The descriptions no
longer state a requirement at all — a refusal already names what is missing,
whether that is the permission or the reach of the token — and the 403 names
the two halves rather than the old rule.
