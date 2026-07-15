"""Server-side markdown rendering for assistant chat prose.

The model narrates in markdown; the server renders it so the chat pane stays
a dumb display of server-produced HTML — the same invariant chat blocks
follow. Both the live stream (throttled partial re-renders) and conversation
replay go through :func:`render_chat_markdown`, so they are bit-identical.

markdown-it-py ships with Rich, which phoxtail already depends on; it is also
declared explicitly in the ``chatbot`` extra.
"""

from __future__ import annotations

from markdown_it import MarkdownIt

# The "commonmark" preset allows raw HTML (the spec does); html=False turns
# that off so source HTML comes out escaped. Assistant prose is model output
# and must never carry markup of its own into the chat DOM — only tags this
# renderer produces reach the pane.
_md = MarkdownIt("commonmark", {"html": False}).enable("table").enable("strikethrough")


def _link_open(self, tokens, idx, options, env):
    # Chat links leave the page the user is working on — open them aside.
    tokens[idx].attrSet("target", "_blank")
    tokens[idx].attrSet("rel", "noopener")
    return self.renderToken(tokens, idx, options, env)


_md.add_render_rule("link_open", _link_open)


def render_chat_markdown(text: str) -> str:
    return _md.render(text or "")
