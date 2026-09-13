The internal-link endpoints at `/api/core/v1/internal-links/` asked for nothing
beyond being authenticated, so any account with a session or an unrestricted
token could rename or delete a link that menus across the project point at.
Each endpoint now names the permission its act needs —
`phoxtail_core.view_internallink`, `add_internallink`, `change_internallink`,
`delete_internallink` — and a refusal names the permission missing, so an
administrator can see what to grant. The model is a registered snippet, so
Wagtail's Groups form already offers `add`, `change` and `delete`; it does not
offer `view` for any model, which is a gap in the admin rather than in these
endpoints — the permission exists and is checked, and granting it needs an
interface that offers it.
