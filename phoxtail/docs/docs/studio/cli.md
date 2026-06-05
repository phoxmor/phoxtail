# CLI Reference

This page documents the `phoxtail studio` sub-app. The commands described here are the target surface. Each section is tagged with its implementation phase from the [roadmap](roadmap.md); commands tagged beyond the current phase are aspirational and may change.

All commands run in the context of a Phoxtail project — there must be a `phoxtail.toml` file in the current directory or an ancestor. Commands that need data from the database call the project's Django Ninja API at `/_studio/api/` via HTTP, which means the app must be running (`docker compose up`). Responses are near-instant because the Django process is already warm.

## Global options

```
phoxtail studio [--project <path>] [--json] <subcommand>
```

- `--project <path>` — override project root detection
- `--json` — emit raw JSON instead of Rich-formatted output (useful for scripting and for tools consuming Studio as a data source)

Any subcommand can be invoked with `--help` for Typer's auto-generated usage information.

## Inspection commands (Phase 1)

Read-only commands. Safe to run anywhere, no side effects.

### `phoxtail studio list`

List entities of a given kind.

```
phoxtail studio list variants [--block <id>] [--collection <id>]
phoxtail studio list collections
phoxtail studio list blocks
```

The `variants` subcommand supports filtering by block and/or collection. Output includes identifier, name, block, collection, and whether the variant is marked as default.

### `phoxtail studio show`

Display the full record for a single entity.

```
phoxtail studio show variant <identifier>
phoxtail studio show collection <identifier>
phoxtail studio show block <identifier>
```

For a variant, the output includes the block, collection, description, and the current HTML, CSS, and JavaScript. With `--json`, this is the format an agent should expect when reading variant contents.

### `phoxtail studio diff`

Diff a variant against another source.

```
phoxtail studio diff variant <identifier> --against default
phoxtail studio diff variant <identifier> --against <remote>:<identifier>
phoxtail studio diff variant <identifier> --against session:<session-id>
```

The three diff targets are the block's default variant, a remote variant (Phase 5+), or an active editing session (Phase 3+).

## Context command

### `phoxtail studio context`

Render the context briefing for a block variant. Assembles block schema, design tokens, variant code, and references into a context document for AI agents.

```
phoxtail studio context \
  --block <identifier> \
  --variant <identifier> \
  [--references <id>,<id>,...] \
  [--output <file>] \
  [--json] \
  [--raw]
```

- `--block` and `--variant` are required.
- `--references` is a comma-separated list of variant identifiers to include as design inspiration.
- `--output` writes to a file instead of stdout.
- `--json` emits the raw structured JSON data instead of the rendered context.
- `--raw` prints plain text without Rich formatting (for piping).

## Editing commands

Editing works through sessions. A session is a working copy of a variant on disk, under `.phoxtail/studio/<session-id>/`, containing:

- `template.html` — the variant's HTML
- `style.css` — the variant's CSS
- `script.js` — the variant's JavaScript
- `context.md` — the rendered system prompt for this variant
- `session.json` — metadata (variant identifier, started-at, parent version)

### `phoxtail studio edit`

Start an editing session on a variant.

```
phoxtail studio edit <variant-identifier> --block <block-identifier> [--collection <collection-identifier>]
```

The context briefing is assembled automatically from the API and rendered as `context.md` in the session directory.

### `phoxtail studio commit`

Write an active session's files back to the database, triggering cache invalidation.

```
phoxtail studio commit [--session <id>] [--message "..."]
```

If only one session is active, `--session` can be omitted. `--message` is recorded in the session's history for future reference.

### `phoxtail studio discard`

Drop a session without saving any changes.

```
phoxtail studio discard [--session <id>]
```

### `phoxtail studio sessions`

List active editing sessions.

```
phoxtail studio sessions
```

Output includes each session's identifier, target variant, age, and dirty state.

## Sync commands (Phase 5+)

See [Sync Protocol](sync.md) for the full semantics. Summarized here.

### `phoxtail studio pull`

Pull a variant or collection from a remote.

```
phoxtail studio pull variant <identifier> [--from <remote>]
phoxtail studio pull collection <identifier> [--from <remote>]
```

`<identifier>` is a fully-qualified sync identifier of the form `<namespace>/<collection>/<block>/<variant>`. `<remote>` defaults to `origin`.

### `phoxtail studio push`

Publish a local variant to a remote.

```
phoxtail studio push variant <local-identifier> --to <remote> --as <target-identifier>
```

### `phoxtail studio sync`

Reconcile local state with a remote for a whole collection.

```
phoxtail studio sync collection <identifier> [--with <remote>]
```

### `phoxtail studio fork`

Create a local copy of a remote variant under a new identity, preserving parentage.

```
phoxtail studio fork variant <remote-identifier> --as <local-identifier>
```

### `phoxtail studio publish`

Promote a local variant to a remote under a fresh public identity.

```
phoxtail studio publish variant <local-identifier> --to <remote> --as <public-identifier>
```

### `phoxtail studio remote`

Manage configured remotes.

```
phoxtail studio remote add <name> <url>
phoxtail studio remote list
phoxtail studio remote remove <name>
```

Remotes are stored in `phoxtail.toml` under `[studio.remotes]`.

## MCP server (Phase 4)

### `phoxtail studio mcp serve`

Start an MCP server that exposes a subset of the above commands as MCP tools. This command is intended to be launched by MCP clients (Claude Code, Claude Desktop) via their own configuration files, not by the user directly.

```
phoxtail studio mcp serve
```

The exposed tools include the inspection commands (`list`, `show`, `diff`), `prompt`, and a direct `update_variant` verb that bypasses the session workflow for agents that prefer in-conversation edits. Each MCP tool calls the corresponding `/_studio/api/` endpoint. The sync commands are intentionally excluded from the MCP surface in early phases — sync is a deliberate human decision, not something an agent should trigger autonomously.

## Exit codes

All Studio commands follow the convention:

- `0` — success
- `1` — general failure (invalid input, entity not found, conflict)
- `2` — environment problem (no `phoxtail.toml`, docker unavailable)
- `3` — permission denied (once sync auth is implemented)

Scripts and agents can rely on these.
