# Sync Protocol

_Status: design in progress. This document defines the model and the vocabulary. Concrete wire format, authentication scheme, and conflict resolution rules will be filled in as the first implementation phase lands. The model itself is stable enough to design the earlier phases against._

## The problem

A variant exists in N projects. In project A it has been refined to v3. In project B it was forked from v1 and taken in a different direction. In project C — the agency's canonical project — there is a v4 that has not been shared yet. No one has a single authoritative view of what "the Hero / Centered variant" actually is.

The sync protocol gives a vocabulary and a set of operations for moving variants between projects and, optionally, through a central registry that can act as a coordinating point.

## What syncs

The following entity types are synchronizable:

- **BlockVariant** — a single implementation (HTML, CSS, JavaScript, and metadata)
- **VariantCollection** — a grouping of variants with shared design tokens, including the collection's own DTL template
- **Block** — a structural schema, synced less often because schema evolution requires care

Each synchronizable entity carries additional metadata beyond what the current models store:

- A **stable identifier** (see below) — globally unique, human-readable, namespaced
- A **version** — a content hash, monotonically updated on every change
- A **source** — the project or registry that originated the current version
- A **parent version** — the version this one was derived from, for fork tracking and conflict detection
- An **author** — who made the change
- A **license** — how downstream consumers may use it

These fields necessitate a new model (or extension of the existing ones) and a new migration. They are introduced in Phase 5 of the [roadmap](roadmap.md), not before.

## Identity

A variant's local database primary key is not stable across projects and cannot be used for cross-project identity. Instead, sync identity is composed as:

```
<namespace>/<collection-identifier>/<block-identifier>/<variant-identifier>
```

For example:

```
phoxtail/ground-state/header-section/centered-dark
mystudio/editorial/blog-post-header/prose-wide
local/hero/my-experiment
```

**Namespace** is the owner of the variant:

- `phoxtail` — variants shipped by Phoxtail itself as part of the bootstrap collection
- An organization name (`mystudio`, `acme-co`) — variants owned by a specific publisher
- An individual handle (`alice`) — variants owned by an individual author
- `local` — variants that exist only in the local project and have not yet been published

Local variants stay in the `local/` namespace until they are explicitly published. Publishing assigns them a public namespace.

## Remotes

A project configures zero or more remotes in `phoxtail.toml`:

```toml
[studio.remotes]
origin = "https://phoxtail.com"
agency = "https://agency.example.com/studio"
```

A remote is an HTTP endpoint that speaks the Studio sync protocol. `phoxtail.com` is the planned public registry, but any Phoxtail project can also act as a remote for another Phoxtail project — there is nothing special about the central instance at the protocol level, only at the product level.

This means a small agency can run its own registry for internal use without any dependency on the public registry, and a designer can sync two local projects peer-to-peer without going through any server at all.

## Operations

### Pull

```
phoxtail studio pull variant phoxtail/ground-state/header-section/centered-dark
```

The client asks the remote for the current version of the identified variant. The remote returns the row (html, css, javascript, metadata, version, parent version). The client writes it to the local database.

If a local copy already exists with the same version, the pull is a no-op. If it exists with a different version and the local version is an ancestor of the remote version, the pull is a fast-forward update. If the local version has diverged from the remote's lineage, the pull refuses and asks the user to fork, merge, or force.

### Push

```
phoxtail studio push variant local/header-section/my-experiment \
  --to origin --as mystudio/headers/minimal
```

The client sends a local variant to a remote under a specified target identity. The remote accepts, rejects (on permission, identity collision, or unresolved conflict), or asks for a merge. Push is authenticated — only identified clients can push to a namespace they own.

### Sync

```
phoxtail studio sync collection phoxtail/ground-state --with origin
```

Bidirectional reconciliation for a whole collection. For each variant in the collection, the tool pulls updates if the remote is ahead and (optionally, with `--push`) pushes updates if the local is ahead. Variants that have diverged are reported and skipped.

Sync is most useful for maintaining a local mirror of a canonical collection.

### Fork

```
phoxtail studio fork variant phoxtail/ground-state/header-section/centered-dark \
  --as local/hero/my-take
```

Creates a local copy of a remote variant with a new identity, recording the parent version. Subsequent pulls of the parent are surfaced as "upstream has updated" notifications rather than automatic updates; the fork has a life of its own.

### Publish

```
phoxtail studio publish variant local/hero/my-take \
  --to origin --as mystudio/heroes/bold
```

Promotes a local variant to a remote under a fresh public identity. This is how a designer "ships" their work. Publish is the combination of "assign a public namespace" and "push" in one atomic operation.

## Conflicts

Variants are HTML, CSS, and JavaScript text. Text merges. When two versions have a common ancestor and diverge only in disjoint regions, the sync tool attempts a textual three-way merge over each file independently. When regions overlap, the tool refuses and presents the conflict to the user in the same way git does, with conflict markers in the working copy.

This explicitly mirrors git's model because the target user already understands git. Anyone who can resolve a rebase conflict can resolve a variant sync conflict.

## Versioning

Each entity version is a content hash of its normalized contents (HTML + CSS + JavaScript + relevant metadata, canonicalized). Two projects that independently produce byte-identical variants will converge on the same hash, which means the sync layer can detect equivalence without any shared state.

Version history is tracked as a DAG, not a linear sequence. A variant can have multiple children (forks), and a merge has two parents. This is the same shape as git's commit graph, simplified because there is only one "file" per version.

## The central registry

`phoxtail.com` is planned to host a public registry instance. At the protocol level it is just another remote. At the product level it adds:

- **Discovery** — search, tagging, browsing, preview screenshots
- **Attribution** — who authored a variant, under what license
- **Curation** — endorsed collections, quality tiers, editorial collections
- **Hosting** — preview images, fonts, and any other binary assets a collection references

The protocol is designed so that:

- Projects can operate entirely peer-to-peer without any central registry.
- Multiple central registries can coexist — a public one, private agency ones, per-organization ones — and a project can be configured to consult them in a preference order.
- A central registry is not a single point of failure; it is a convenience.

## Authentication

Authentication is out of scope for the first implementation phase. The first working sync will use static bearer tokens configured per remote in `phoxtail.toml`. Later phases introduce per-user identities, signed variants, and a lightweight trust model for publishers.

## Out of scope (deliberately)

- **Real-time collaboration** — two designers editing the same variant simultaneously is not a target. Sync is asynchronous and interaction is turn-based.
- **Binary asset bundling** — images, fonts, and other assets that a variant references by URL are not themselves synced in v1. The URL is the contract; hosting is someone else's problem until a later phase.
- **Payment and licensing enforcement** — the protocol carries license metadata but does not enforce it. Marketplace phases layer enforcement on top.
- **Schema migrations across projects** — if project A's `header_section` Block has fields that project B's does not, pulling a variant will surface the mismatch as a warning. Automated schema reconciliation is a later problem.

These are reserved for later deliberately. The core protocol is designed to admit them without breaking changes.
