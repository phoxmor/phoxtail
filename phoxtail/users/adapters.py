from allauth import utils as allauth_utils
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return settings.PHOXTAIL_ALLOW_SIGNUP

    def populate_username(self, request, user):
        # Guard against names that are purely non-ASCII (e.g. Greek) with
        # hyphens: after ASCII normalisation allauth is left with only "-",
        # which is a valid Django username but meaningless.  When that would
        # happen, strip the name fields so allauth falls through to the email
        # local part instead.
        from allauth.account.utils import user_username

        if not user_username(user):
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            email = user.email or ""
            basename = allauth_utils._generate_unique_username_base([first_name, last_name, email, "user"])
            if len(basename.strip("-_.")) < 2:
                # Fall back: derive username from email only.
                user.username = self.generate_unique_username([email, "user"])
                return

        super().populate_username(request, user)
