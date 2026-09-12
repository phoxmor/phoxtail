"""v1 of the media API.

Images, documents, video and audio — the models this app owns, which Wagtail
reaches through its swappable getters.
"""

from __future__ import annotations

from phoxtail.media.api.v1.media import router

__all__ = ["router"]
