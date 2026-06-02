# What Makes a Phoxtail App

A Django app is a box of models, views, and templates.
A Wagtail app adds pages, snippets, and hooks.
A phoxtail app is something with a different intention entirely.

This document is not about mechanics — those are covered in the linked references. It is about *why* phoxtail apps are structured the way they are, and what every new app is expected to commit to.

---

## The Axiom

**A phoxtail app is designed so that agents are first-class operators, directed and reviewed by humans.**

Humans prompt. Agents act. Humans review. The app must support all three roles without friction.

This one decision explains every structural choice that follows. It is not a constraint added on top of a Django app — it is the reason the app is shaped the way it is.

---

## The Five Pillars

### 1. Self-wiring: the app describes itself

A Django app must be manually registered: added to `INSTALLED_APPS`, wired into URLs, imported into routers. Every project that wants the app duplicates this ceremony.

A phoxtail app instead **declares its requirements** in `PhoxtailAppConfig`:

- what other apps it depends on (`depends_on`)
- where its API router lives (`api_version_router`)
- what page types it contributes (`page_schema_contributors`)

The project reads these declarations at startup and wires the app automatically. No central registry needs to know about the app in advance. A project that adds the app gets its full surface; a project that omits it gets nothing — no dead endpoints, no dead tools.

This is what makes portability possible. An agent can install an app into a project and the project knows what to do with it, because the app said what it needs.

See [App Contribution Model](app-contribution-model.md) for the full wiring protocol.

---

### 2. Uniform API surface: HTTP for software-to-software

Every phoxtail app that owns data exposes it through a Django Ninja router mounted at `/api/<app>/v1/`. The endpoints are the authoritative programmatic interface to the app's domain.

This is not merely convenience for frontend consumption. The uniform surface is the foundation for a larger vision: phoxtail projects that talk to each other. One project can ask another for its navigation blocks, its palette definitions, or its published content — not because a bespoke integration was written, but because every phoxtail app speaks the same HTTP language at a predictable address.

That cross-project ecosystem is the direction the architecture enables. The APIs are live; the ecosystem is what is being built toward.

See [App Contribution Model → api_version_router](app-contribution-model.md#1-api_version_router--http-surface) for the wiring detail.

---

### 3. MCP tools: the agent interface

Alongside its HTTP API, every phoxtail app exposes its operations as MCP tools. The tools mirror the API but are the surface agents use directly — named, typed, and discoverable without reading documentation.

There are two distinct surfaces because there are two distinct callers:

- **HTTP** is for software-to-software, synchronous, typically authenticated by a service token.
- **MCP** is for agents acting on behalf of a human, discoverable at conversation time, gated on `phoxtail.toml` so only relevant tools appear.

The underlying operations are the same. The surface is shaped for the caller.

MCP tools are not a nice-to-have addition. They are the primary interface by which phoxtail projects are managed day-to-day. Traditional admin interfaces remain, but they are not the priority.

See [App Contribution Model → MCP entry point](app-contribution-model.md#3-phoxtailmcp_modules-entry-point--mcp-surface) for the registration protocol.

---

### 4. Blocks: representation as data

Most applications bake their visual structure into templates and code. Changing what a page looks like requires a code change and a deploy.

Phoxtail apps make visual composition a database concern instead. **Blocks** are the unit of representation; **variants** are the unit of appearance. Both live in the database. An agent can assemble a page, apply a variant, or reconfigure a layout without touching a file.

This matters specifically in the agent era. An agent responding to "give this page a dark hero and a two-column feature section" can act directly on blocks and variants. It does not need to know the template structure, the CSS class names, or where the code lives.

`phoxtail.streams` is a core library app — present in every project — because blocks are the universal visual-composition layer for all phoxtail apps. This is an intentional commitment, not a convenience import.

Structured attributes — a page title, a category, a foreign key — remain typed model fields. Blocks govern what is composed visually; typed fields govern what is structured semantically.

See [Dynamic Blocks Architecture](../engine/streams/dynamic-blocks-architecture.md) for the full model.

---

### 5. Service layer: one home for business logic

In most Django applications, business logic accumulates wherever it was first needed — a model method here, a view utility there, inline in a serializer. When a new surface (an API endpoint, an MCP tool, an admin action) needs the same logic, it either copies it or reaches into the wrong layer.

Phoxtail apps resolve this with a clear rule: **every door leads to the same room.**

Models define structure. The service layer defines the verbs — what can happen, under what conditions, with what side effects. Views, API endpoints, and MCP tools are doors. They receive input, pass it to the service, and return the result. No business logic lives in them.

The structure is consistent across apps:

```
<app>/services/
├── base.py            # State queries, domain helpers
└── admin/
    ├── gateway.py     # Named operations for the admin domain
    └── operations/    # One file per operation: authorize → validate → perform
```

This is the current standard. Not every app has adopted it yet — adoption is in progress. But it is the target state for every new app, and for every operation that a new app ships.

See [Service Layer](service-layer-overview.md) for the full pattern.

---

## What Is Not the Essence

Shared model mixins (`UUIDMixin`, `TimestampMixin`) and shared template tags are useful plumbing. An app that uses them is more consistent; an app that omits them is still a valid phoxtail app. These are conventions, not commitments.

---

## The Short Version

A phoxtail app commits to five things:

1. **It declares itself** so projects can wire it without ceremony.
2. **It exposes its data** through a uniform HTTP API.
3. **It exposes its operations** as MCP tools for agent access.
4. **It represents visually** through blocks and variants, not baked templates.
5. **It centralizes its logic** in a service layer that every surface delegates to.

Together these make an app that a human can direct, an agent can operate, and another project can talk to — today or in the future.
