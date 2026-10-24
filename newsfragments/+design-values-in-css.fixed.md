Security: a font's name or fallback list, or a font or palette role's
identifier, could close the `<style>` element every page carries and run a
script for every visitor, on the authentication pages too. Each value is now
escaped as the CSS is built, and the admin, the API and the MCP tools refuse
values that are not font names, lists of names or identifiers; the API also
checks palette colours, and the palette list escapes its swatches.
