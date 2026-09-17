"""Whose door a key was minted for, and whether it is ours.

A client asks for a key *for* one server and names it; the authorization
server records the name on the key. The library then refuses the key
anywhere the request's own address does not begin with that name — right
for a resource server that is the audience, and never true here, where
the API stands one hop behind the MCP server the key names. So the
library's replaceable check is replaced with the question that fits:
does this key name this project's MCP server?
"""

from __future__ import annotations

from collections.abc import Iterable

from phoxtail.cli.utils.config import canonical_url, get_public_mcp_resource


def names_this_server(request_uri: str, audiences: Iterable[str]) -> bool:
    """The library's resource validator, for a resource server behind the door.

    ``request_uri`` is the API's own address and is ignored on purpose: no
    request to the API is ever addressed to the MCP server, and the key
    was minted for the MCP server. Both sides are compared in canonical
    form — a client names a resource lowercased, without a default port
    or a trailing slash, while ours is built from a domain someone typed.
    Called only for a key that carries a resource; one that carries none
    is accepted by the library before this is asked. That precondition is
    the library's: handed an empty list, this answers no, and every key
    without a resource would be refused.
    """
    door = canonical_url(get_public_mcp_resource())
    return any(canonical_url(audience) == door for audience in audiences)
