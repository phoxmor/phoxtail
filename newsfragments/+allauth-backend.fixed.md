Confirming your password on the "Confirm Access" page no longer always fails
for a user who has a username, and a deactivated user who logs in now sees
the "Account Inactive" page instead of being told the password is wrong.
`phoxtail.users` now adds allauth's authentication backend beside Django's,
as allauth's installation asks; a project that sets its own
`AUTHENTICATION_BACKENDS` keeps them and should add
`allauth.account.auth_backends.AuthenticationBackend`.
