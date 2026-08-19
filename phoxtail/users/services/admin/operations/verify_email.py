from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....services.base import UserService


class UserServiceAdminVerifyEmail:
    """Admin domain operation marking a user's email address as verified.

    Mirrors allauth's records: get-or-create the ``EmailAddress`` row for
    ``user.email`` and flag it verified + primary. Sends nothing — this is
    an administrative bypass of the confirmation-email flow.
    """

    def __init__(self, service: "UserService") -> None:
        self.service = service

    def authorize(self) -> None:
        pass

    def validate(self) -> None:
        pass

    def perform(self) -> str:
        from allauth.account.models import EmailAddress

        user = self.service.user
        assert user is not None, "operation requires a service bound to a user"
        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=user.email,
            defaults={"verified": True, "primary": True},
        )
        if not created and email_address.verified:
            return "already_verified"
        if not created:
            email_address.verified = True
            email_address.primary = True
            email_address.save(update_fields=["verified", "primary"])
        return "verified"

    def execute(self) -> str:
        self.authorize()
        self.validate()

        return self.perform()
