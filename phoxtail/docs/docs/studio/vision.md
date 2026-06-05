# Vision

## The grand picture

Phoxtail Studio is the beginning of a network.

Each Phoxtail project is a self-contained design environment: it has its own Blocks (structure), Variants (implementations), Collections (design systems), and System Prompts (AI playbooks). Today these live only in that project's database. Tomorrow they are addressable, versioned, and exchangeable — like packages, but for designs.

A concrete scenario:

> Project A is a client website built on Phoxtail. Project B is a central archive — `phoxtail.com` — maintained by a digital agency. Project A runs `phoxtail studio pull header-section --collection general-unsorted`. Project B returns the current authoritative version of that variant. Project A updates its local copy, renders it in a preview page, commits to its own history, and continues.

The same verbs work peer-to-peer. Any two Phoxtail projects can exchange variants directly, with or without a central registry. The central registry is a convenience and a product layer, not a protocol requirement.

## What this enables

- **One place to look.** A designer working on five client projects should not maintain five divergent copies of the same "Hero / Centered" variant. They work on one canonical version and the clients pull from it.
- **Design distribution.** A variant author — solo designer, small studio — can publish collections that other projects adopt, with attribution, versioning, and updates over time.
- **A marketplace, eventually.** Central registries can host curated collections. Designers publish; projects subscribe. Commerce, attribution, and licensing layer on top without changing the underlying protocol.
- **A real record, immediately.** Even before any of the above ships, the mere existence of a stable, queryable, diffable representation of every variant gives a studio a clean source of truth. Today that record lives half in Python files, half in the database, half in a designer's head. That is three halves.

The immediate value is the last bullet. Everything else is a door that opens once the record exists.

## First customer

The first customer is the author of Phoxtail — a digital agency that uses Phoxtail to build client sites. The agency benefits on day one from:

- A clean internal library of variants, versioned and diffable.
- Surgical AI refinement on individual variants without manual copy-paste round trips between the Wagtail admin and an external chat window.
- A `phoxtail studio publish` command that promotes a polished variant from a client project back to the agency's canonical collection, where other clients can pull it.

Every feature beyond that point is validated against this use case before it is built. If it does not help the agency, it waits.

## Why the terminal

The primary interface is the terminal for three reasons:

1. **Modern AI agents already live there.** Claude Code and similar tools have mature editing, diffing, and conversation surfaces. Re-implementing any of that inside a Django admin view would be wasted effort.
2. **The target user is a developer-designer.** The person who benefits most from Phoxtail Studio already uses git, a terminal, and an editor. Meeting them where they work is cheaper than building a new workspace for them.
3. **Composition.** Terminal-first tools compose with shells, scripts, CI, and other terminal-first tools. A variant that can be exported with one command can also be snapshotted nightly, diffed in a PR, or archived to S3 with zero additional work.

The Wagtail page in the other window is not a second interface — it is a preview. The design surface is the terminal.

## What this is not

- **Not a design tool for non-developers.** If you want a drag-and-drop editor, this is the wrong project.
- **Not a replacement for Wagtail's page editor.** Content editors continue to fill pages in Wagtail. Studio operates one layer below — the variant implementation — and uses the Wagtail page as its preview surface.
- **Not tied to any specific AI provider.** The CLI and sync commands work without any AI. AI integration is a layer on top. Swapping providers or running offline both remain possible.
- **Not a CMS.** Phoxtail Studio has nothing to say about content. It is about the templates that render content.

## The long bet

The long bet is that designs become first-class, portable, versioned artifacts — in the same way that code already is and that content management systems never quite managed. The short bet is that even a fraction of that vision, delivered as a clean CLI over the existing Phoxtail models, pays for itself in one client project.

The plan is to make both bets at once: build the short bet with an architecture that does not foreclose the long one.
