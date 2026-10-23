The authentication pages — login, signup, password reset, login codes,
email verification, reauthentication, sign out, email addresses, change and
set password — are now django-allauth's own pages, drawn with phoxtail's
look, so they follow allauth's behaviour and wording as it is upgraded. Pages
phoxtail never restyled (phone, passkey signup, password reset by code) get
the same look. The private-page login, the page password prompt and the consent
page share the same frame and card. A site that overrides one of allauth's
`account/` templates keeps its copy.

The card sits in the middle of the page, with the site's logo in the top
left corner and, on a site with more than one language, a language menu in
the top right. Fields use phoxtail's outlined fields; none takes the focus on
arrival, as in allauth. A wrong email or password is said inside the
card, above the fields; other ways in, such as a login code, sit under a
line that reads "or". Signed-in pages keep their buttons at the normal size
and set a second part, such as adding an email address, apart with a line.

Signup asks for the person first, then how to reach them, then the password.
The extra buttons phoxtail used to add ("Return to Login", "Go back to
homepage", "Cancel and Return to Homepage") are gone, as allauth draws none.
Change password no longer shows "Forgot your password?" twice.
