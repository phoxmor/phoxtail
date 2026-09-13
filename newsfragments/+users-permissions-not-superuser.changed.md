The users and genders endpoints now ask for the Django permission each act
needs — `phoxtail_users.view_user`, `add_user`, `change_user`, `delete_user`
and the gender equivalents — instead of requiring a superuser account for the
whole surface. Superusers are unaffected, since Django answers `has_perm` True
for them; what changes is that a person granted the permission, through a group
or directly, can now be given exactly that much. A refusal names the permission
missing, so an administrator can see what to grant, and a token narrowed to
scopes must still cover the codename.
