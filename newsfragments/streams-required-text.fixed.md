Creating or updating a variant collection, block or block category with a
blank required field (`identifier`, `name`, `slug`, and `description` for
collections and blocks) is now refused with 422 naming the field, instead of
an opaque 400 from the model's validation, and the API documentation and MCP
tools no longer describe those fields as optional. Requests that succeeded
before are unaffected. `phoxtail studio load` reports a file refused for its
content as a warning and carries on, whether the refusal is a 400 or a 422;
before, a 422 ended the whole run.
