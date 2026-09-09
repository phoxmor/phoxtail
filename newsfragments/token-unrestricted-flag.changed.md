Access tokens now say explicitly whether they are unrestricted. A token
either carries scopes — Django permission codenames such as
`phoxtail_streams.change_blockvariant` — or is marked `unrestricted`, and
issuing one requires choosing. The `"*"` wildcard is gone: it granted
capabilities that did not exist when the token was issued, so installing an
app silently widened every token already in circulation. Existing tokens
keep working; re-issue any you want narrowed.
