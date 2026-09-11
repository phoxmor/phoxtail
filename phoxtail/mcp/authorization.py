"""What a caller may be offered, and what they may run.

fastmcp asks each component one question — its ``auth`` checks — and asks
it at both moments that matter: when the catalogue is listed, where a
failing check drops the component, and when it is addressed by name, where
the same check makes it indistinguishable from one that does not exist.
Both are enforced by the registry itself (``list_tools``, ``get_tool``,
``get_resource``, ``get_prompt``), so there is no serving path that can
skip them and no middleware anyone has to remember to install.

A check is any ``Callable[[AuthContext], bool]``. The context carries the
caller's token and the component being reached, which is enough to answer
questions that have nothing in common with each other: one tool is limited
by what a credential permits, another by the transport it arrived on, and
neither has to know the other exists. That is why the checks live here as
plain functions rather than behind a vocabulary of our own — naming the
check on the tool says the same thing with nothing in between.

**Neither moment is the last line of defence, and neither pretends to be.**
A shorter catalogue is economy and honesty, not a lock: anything reaching
the API is checked there again, by the authority, with no memory of what
was decided here.
"""

from __future__ import annotations

from fastmcp.server.auth import AuthContext

from phoxtail.mcp._http import serving_over_http


def local_only(context: AuthContext) -> bool:
    """Offer this component only to a caller sharing a machine with us.

    The sessions tools write files to this server's own disk and return
    their paths, so an agent can read and edit them in place. Reached over
    HTTP the agent is somewhere else entirely and those paths name nothing
    it can open — and the tool does not fail saying so, it succeeds and
    hands back directions to a building in another city. That is what this
    guards: not a permission, but a capability that does not survive the
    distance.

    Nothing about identity enters it. A superuser on a phone is exactly as
    far away as anyone else, so the question is answered by the transport
    and by nothing else.

    Note what it does *not* cover. A tool that takes a path as an argument,
    like uploading a staged file, asks a question about the argument rather
    than about the caller. No check standing outside the tool can answer
    that, and it belongs inside, where the path is known.
    """
    return not serving_over_http()
