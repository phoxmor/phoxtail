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

    It is also the answer to *which channel is holding this credential* —
    the actor, as distinct from its owner. For a channel there is only one
    of, the type says everything: there is a single chatbot, so
    ``CHATBOT`` identifies it completely and no reference to a row is
    needed. A channel with many instances — one credential per sibling
    project, one per connected client — needs the instance as well, and
    that is a foreign key alongside the type rather than more types.
    """

    PERSONAL = "personal", _("Personal")

    # Minted for one chat turn, held by the chatbot, owned by the person
    # chatting. Short-lived by construction: it exists for the length of a
    # single exchange and is not offered to anyone, so nothing has to be
    # kept safe and nothing has to be revoked in the ordinary case. Kept
    # apart from PERSONAL because the two differ in the ways that matter
    # most — who may see the raw string, how long it lives, and what
    # should happen if the channel itself has to be shut off.
    CHATBOT = "chatbot", _("Chatbot")
