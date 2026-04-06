# Studio: Architecture (Legacy)

!!! warning "Removed"
    The Wagtail admin Studio interface documented here has been removed. The `BlockSystemPrompt` model, `StudioViewSet`, `StudioContextForm`, all Studio views, templates, and the `access_stream_studio` permission no longer exist.

    For the current architecture, see the [Studio Architecture](../../studio/architecture.md) documentation, which covers the CLI + MCP + API approach.

## What replaced it

- **Context assembly**: `POST /api/streams/v1/context/` assembles structured context data. A static Jinja2 template (`cli/templates/studio/context.md`) renders the context document.
- **CLI**: `phoxtail studio context`, `phoxtail studio edit`, `phoxtail studio commit`
- **MCP tools**: `phoxtail_get_context`, `phoxtail_get_variant`, `phoxtail_update_variant`, etc.
- **Design tokens**: `VariantCollection.render()` still renders collection design tokens via DTL.
