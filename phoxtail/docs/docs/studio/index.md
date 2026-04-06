# Phoxtail Studio

Phoxtail Studio is the tooling — CLI, agent integration, and sync protocol — for designing, refining, and exchanging block variants across Phoxtail projects.

It is the successor to the Wagtail-admin-embedded "Stream Studio" and lives entirely in the terminal. A designer iterates on variants locally with an AI agent, previews the result in a normal Wagtail page in a browser tab, and eventually pushes polished designs to a central archive where other projects can pull them.

## Status

**This documentation is a living design document.** It describes a system that is being built. Parts of it are aspirational and will solidify as the implementation lands. Sections marked _planned_ are not yet implemented. Where this documentation conflicts with the code, the code wins until the next doc update.

The intent is that these pages grow up alongside the implementation, so that by the time Phoxtail Studio is feature-complete, this section doubles as the user-facing manual.

## The three pillars

1. **A variant is data, not a file.** A `BlockVariant` is a row in a database with three text fields (HTML, CSS, JavaScript) and some metadata. Every layer above it — editors, agents, sync — treats it as such.
2. **Agents edit, humans review.** AI agents perform surgical edits on that data through a well-defined CLI surface. The human stays in the loop through the Wagtail page as a live preview and the terminal as the conversation.
3. **Designs are portable.** Any variant created in one project can be published, versioned, and pulled into another project — eventually through a public registry.

## How to read these docs

- **[Vision](vision.md)** — why this exists and what it enables
- **[Architecture](architecture.md)** — the technical shape of the system
- **[CLI Reference](cli.md)** — the `phoxtail studio <subcommand>` surface
- **[Sync Protocol](sync.md)** — how designs move between projects
- **[Roadmap](roadmap.md)** — what we are building, in what order

New readers should go through them in that order. Returning readers can jump straight to the CLI reference or the roadmap.

## Relationship to the existing Studio

The Wagtail-admin Stream Studio (see [Studio Architecture](../engine/streams/studio-architecture.md)) is being deprecated. Its valuable pieces — the `BlockSystemPrompt` model, the prompt templates, `VariantCollection.render()` — are retained and reused here. The UI layer (views, forms, modal, HTMX widgets) is being replaced by a Django Ninja API layer (`/api/streams/v1/`) consumed by CLI commands and, eventually, an MCP server and remote sync peers. The recently completed [Studio Refactor Plan](../internal/studio-refactor-plan.md) was the last investment in the admin UI; it cleaned the API surface so this migration could happen cleanly. The deprecation itself is staged; see the [roadmap](roadmap.md).

## Name

The working name is **Phoxtail Studio**, entered as `phoxtail studio <subcommand>` on the command line. The name is not yet final, but the CLI surface is, and the documentation will track the CLI shape regardless of how the product is branded.
