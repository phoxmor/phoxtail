Token scopes are now enforced by the API. An endpoint declares what a
credential must permit with `auth=scoped("wagtailcore.publish_page")`, and a
token whose scopes do not cover it is refused with 403. Sessions and
unrestricted tokens are unaffected — they carry no ceiling, so there is
nothing to check, and everything that works today keeps working.

An endpoint that declares no scope admits sessions and unrestricted tokens and
refuses scoped ones, so forgetting to annotate one leaves a door closed rather
than open. Scope enforcement is the coarse half of the question only: whether
the *person* may act is still decided where it already was, often far more
finely — Wagtail resolves publishing per page subtree, and that check is
unchanged.
