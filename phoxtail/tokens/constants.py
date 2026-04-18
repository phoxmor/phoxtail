from django.db import models
from django.utils.translation import gettext_lazy as _


class TokenType(models.TextChoices):
    """Choices for AccessToken type.

    The type is a category discriminator — it answers "how was this token
    issued and who does it represent?" — not "what can it do?" (that is
    what `scopes` answers).

    PERSONAL tokens are issued by a human from the admin UI for their own
    machines (CLI, MCP server, ad-hoc scripts). Other types (service,
    oauth, sync) will be added when concrete callers exist.
    """

    PERSONAL = "personal", _("Personal")
