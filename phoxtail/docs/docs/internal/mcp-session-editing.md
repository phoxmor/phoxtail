# MCP Session-Based Variant Editing

## Why sessions exist

The direct `phoxtail_studio_get_variant` → `phoxtail_studio_update_variant` route
works, but it has a structural token inefficiency that compounds with variant size:

- **Get** loads the complete `html`, `css`, and `javascript` payload into the agent's
  context window as a tool result.
- **Update** requires the agent to re-emit the *complete* new content as tool
  parameters — partial field updates are not possible because the API takes whole fields.

For a 50-line CSS change in a 2 000-line variant, the agent re-types roughly
2 000 lines of unchanged code.  This makes every iteration slower and more
expensive, and introduces drift risk (agents silently regress unchanged code when
reconstructing large blobs from context).

Sessions resolve this by writing the variant's files to the local filesystem once,
then letting the agent use its native `Read` / `Edit` tools for subsequent changes.
`Edit` sends only `old_string` / `new_string`, so a 50-line change costs roughly
50 lines of tokens regardless of how large the file is.  The permission prompt
also shows a focused before/after diff rather than a full parameter blob.

---

## Architecture

```
┌─────────────────────────────────────┐
│           Claude Code agent          │
│                                     │
│  open_variant ──► session on disk   │
│  Read / Edit ───► local files       │
│  commit_variant ► PUT /variants/{id}│
└─────────────────────────────────────┘
         │                   ▲
    filesystem         ETag + If-Match
         │                   │
~/.phoxtail/projects/        │
  <project-key>/sessions/    │
    <session-id>/            │
      session.json  ─────────┘  (stores ETag)
      template.html
      style.css
      script.js
      context.md
```

Sessions are a **purely client-side convention**.  The API knows nothing about
them.  The session directory is a working copy: changes accumulate locally until
`commit_variant` pushes them back in a single PUT with an `If-Match` header.

The project key is derived from the absolute path of the directory containing
`phoxtail.toml`, matching the convention used by Claude Code for project-scoped
state:

```
/home/user/work/mysite  →  home-user-work-mysite
```

---

## MCP tools

All five tools live in `phoxtail/mcp/studio/sessions.py`.

### `phoxtail_studio_open_variant(variant_id)`

Opens a variant for session-based editing.

1. GETs the variant and its ETag.
2. Renders `context.md` via the `/context/` endpoint and the
   `variant_design_context.md` Jinja template (fails silently if context is
   unavailable).
3. Writes `template.html`, `style.css`, `script.js`, and `context.md` to
   `~/.phoxtail/projects/<key>/sessions/<variant-id>/`.
4. Stores the ETag in `session.json` for later use by `commit_variant`.

**Idempotent**: if a session for this variant is already open the existing path
is returned without overwriting local edits.

Returns `{session_id, path, status, files, variant, next_steps}`.

The `files` dict contains absolute paths keyed by `html`, `css`, `javascript`,
and `context`.  The agent should use its `Read` / `Edit` tools on these paths
directly.

### `phoxtail_studio_commit_variant(session_id?, clean?)`

Reads the local working files and PUTs them to the API with `If-Match: <etag>`.

- `session_id` — optional when exactly one session is active.
- `clean` — if `true`, deletes the session directory after a successful commit
  (default: `false`, session is kept).

On success, updates `session.json` with the new ETag returned by the server.

On a **412 conflict** the session is preserved and an error envelope is returned
— call `phoxtail_studio_refresh_session` to re-sync the ETag, then retry.

### `phoxtail_studio_discard_variant(session_id?)`

Deletes the session directory without saving.  Use when abandoning an editing
attempt or cleaning up after `commit_variant --clean` was forgotten.

### `phoxtail_studio_list_sessions()`

Lists all open sessions for the current project.  Useful at the start of a
conversation to discover sessions left open from previous interactions.

### `phoxtail_studio_refresh_session(session_id?)`

Re-fetches the server ETag for a session's variant and updates `session.json`
without touching the local files.  Call this after a 412 conflict to bring the
stored ETag back in sync, then inspect the local files for conflicts before
retrying `commit_variant`.

---

## When to use sessions vs. direct update

| Scenario | Recommended route |
|---|---|
| Surgical edit (change specific lines) | `open_variant` + Edit + `commit_variant` |
| Complete rewrite (regenerate whole variant) | `get_variant` + `update_variant` |
| Read-only inspection | `get_variant` |
| No filesystem access (remote MCP client) | `get_variant` + `update_variant` |

The direct `get_variant` / `update_variant` tools remain available and are not
deprecated.  Tool descriptions steer agents toward sessions for the common
surgical-edit case.

---

## Risks and mitigations

### Filesystem co-location

Sessions live at `~/.phoxtail/projects/<key>/sessions/` on the machine running
the MCP server.  The agent's `Read` / `Edit` tools must resolve the same paths.

**When it works**: Claude Code running locally — the MCP server and the agent
both operate on the same filesystem.

**When it breaks**: MCP server running inside a container or on a remote host
while the agent's filesystem tools point at the host.  In this case `open_variant`
returns a path that the agent cannot open.

**Mitigation**: run the MCP server on the same machine as the agent.  If you
deploy the MCP server in a container, mount `~/.phoxtail` as a volume so the
session directory is reachable from both sides.

### Stale sessions from previous conversations

Agents can leave sessions open across conversations.  A session for variant `42`
opened on Monday is still on disk on Friday.

**Mitigation**: call `phoxtail_studio_list_sessions` at the start of a design
conversation to discover open sessions.  The tool descriptions on `open_variant`
and `list_sessions` both encourage this.  The session directory holds the last
committed content plus any pending local edits, so an old session is rarely
harmful — it just takes up disk space until `discard_variant` is called.

### ETag conflict (412) after parallel edits

If someone updates a variant via the direct `update_variant` route (or the Django
admin) while a session is open, `commit_variant` will return a 412 conflict error.
The session is always preserved.

**Mitigation** (in order):
1. Call `phoxtail_studio_refresh_session` to update the stored ETag.
2. Compare the current server content (`get_variant`) with the local working files
   to identify what changed on the server.
3. Merge the server changes into the local files manually via `Edit`.
4. Retry `commit_variant`.

The error envelope from `commit_variant` explains this recovery path.

### Session directory permissions

The session root (`~/.phoxtail/`) is created with default umask permissions.  On
shared machines this may expose working copies to other users.

**Mitigation**: ensure `~/.phoxtail/` has `700` permissions on shared hosts.
For CI/CD pipelines that run MCP-driven edits, set `$HOME` to a workspace-private
directory so sessions never land under a shared home.

### Large variant content

Even with sessions, the initial `open_variant` call loads the full HTML/CSS/JS
into the response payload (once, to write it to disk).  Very large variants
(several thousand lines) still incur that one-time cost.

**Mitigation**: this is unavoidable for the initial fetch.  All subsequent
iterations only pay for the lines changed via `Edit`, so the cost amortises
quickly across multi-step editing sessions.

---

## Implementation notes

- `phoxtail/mcp/studio/sessions.py` — five MCP tools; no new logic beyond what
  already exists in `phoxtail/cli/studio/session.py`.
- `phoxtail/cli/studio/session.py` — owns all filesystem operations; imported
  directly by both the CLI commands and the MCP tools.  Single source of truth.
- `phoxtail/mcp/__init__.py` — imports `phoxtail.mcp.studio.sessions` to
  trigger tool registration alongside the other studio tools.
- Tool descriptions on `phoxtail_studio_get_variant` and
  `phoxtail_studio_update_variant` were updated to note the session-based
  alternative for surgical edits.
