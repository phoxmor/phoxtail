"""Reading a client's own document, and what this server takes from it.

A client that identifies by URL publishes what it is: its name, where it
listens, and which grants it can use — everywhere, not only here. The
library's resolver refuses a document that names more than one grant
type besides refresh, where the standard lets a server use the grants it
supports and ignore the rest (RFC 7591 §2). The library's fetcher is a
replaceable class, so the document is read by the library's own
hardened fetcher and then narrowed to what this server offers before
the library judges it.
"""

from __future__ import annotations

from oauth2_provider.cimd import GRANT_TYPE_MAP, IGNORED_GRANT_TYPES, SafeMetadataFetcher

# What a client may ask this server for: the grants it maps, and the one
# it handles alongside them. Anything else a document declares is the
# client's business with other servers.
OFFERED_GRANT_TYPES = frozenset(GRANT_TYPE_MAP) | IGNORED_GRANT_TYPES


def narrow_grant_types(metadata: dict) -> dict:
    """The document, with only the grant types this server offers.

    A document naming no grant type is left alone: the library reads
    that as the authorization code grant. One naming only grants this
    server lacks is left alone too, so the library refuses it in its own
    words rather than ours.
    """
    declared = metadata.get("grant_types")
    if not isinstance(declared, list):
        return metadata
    offered = [grant for grant in declared if grant in OFFERED_GRANT_TYPES]
    if not offered:
        return metadata
    return {**metadata, "grant_types": offered}


class MetadataFetcher(SafeMetadataFetcher):
    """The library's fetcher, narrowing what it fetched to what is offered."""

    def fetch(self, client_id):
        metadata, max_age = super().fetch(client_id)
        return narrow_grant_types(metadata), max_age
