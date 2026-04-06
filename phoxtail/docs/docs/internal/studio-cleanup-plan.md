# Studio Cleanup: BlockSystemPrompt Removal & Old Admin Purge

## What we did

Replaced the database-backed `BlockSystemPrompt` rendering pipeline with a static
Jinja2 context template (`cli/templates/studio/context.md`) shipped with phoxtail.

**Why**: In the MCP/agent era, system prompts no longer need to carry task
instructions or output format directives — the agent has tools for that. The three
old prompts (`variant_generator`, `variant_refiner`, `variant_editor`) collapsed
into a single context briefing that provides pure domain knowledge: block schema,
DTL rules, CSS architecture, design tokens, and the current variant's code.

The `BlockSystemPrompt` model was the right abstraction when the admin UI was the
orchestration layer. Now that MCP tools are the orchestration layer, the prompt is
a static reference document — and a Django model managing static content is
unnecessary complexity.

**New architecture**:

- `POST /api/streams/v1/context/` — assembles structured context data (block
  schema as JSON, rendered collection design tokens, variant code, references)
- `phoxtail_get_context` (MCP tool) — calls the endpoint and renders the Jinja2
  template into the final context document
- `phoxtail studio context` (CLI) — same pipeline with Rich-formatted output
- `POST /api/streams/v1/collections/{id}/render/` — renders a collection's DTL
  template into design tokens, exposed via `phoxtail_get_collection` MCP tool

## What needs to happen next

### 1. Delete the `BlockSystemPrompt` model

**File**: `phoxtail/streams/models.py` (lines 331–395)

Remove the entire `BlockSystemPrompt` class. This requires a new migration
(`makemigrations streams`) that drops the table. The model is no longer referenced
by any live code path — the context endpoint derives design tokens from
`VariantCollection.render()` and the block schema from `Block.schema`.

### 2. Delete the old Stream Studio admin interface

The pre-MCP Wagtail admin UI for the Stream Studio is now broken (it depended on
`BlockSystemPrompt`) and superseded by the CLI + MCP tools. Delete everything:

**Views and forms** (entire files can be deleted or have Studio code removed):

- `phoxtail/streams/views.py` — all `studio_*` views and `StudioSearch*` views
- `phoxtail/streams/forms.py` — `StudioContextForm`
- `phoxtail/streams/viewsets.py` — `StudioViewSet` (lines ~177–217)

**Admin registration**:

- `phoxtail/streams/wagtail_hooks.py` — remove `StudioViewSet` import and
  registration

**Permissions**:

- `phoxtail/streams/permissions/models.py` — remove `access_stream_studio`
  permission (requires migration)

**Admin panels**:

- `phoxtail/streams/admin/panels.py` — `CodeEditorPanel` (Monaco editor for
  prompt templates in admin)

**Template tags**:

- `phoxtail/streams/templatetags/stream_studio_tags.py` — `minify` filter (was
  used by the DTL-based prompt templates, no longer needed)

**Templates** (entire directory):

- `phoxtail/streams/templates/phoxtail_streams/studio/` — index, partials,
  forms, widgets

**Static files**:

- `phoxtail/streams/static/phoxtail_streams/css/studio.css`
- `phoxtail/streams/static/phoxtail_streams/admin/panels/code_editor/` — Monaco
  editor assets

**Prompt data files**:

- `phoxtail/streams/management/data/prompts/variant_generator.md`
- `phoxtail/streams/management/data/prompts/variant_refiner.md`
- `phoxtail/streams/management/data/prompts/variant_editor.md`

**Management commands**:

- `phoxtail/streams/management/commands/populate_streams.py` — remove the
  `BlockSystemPrompt` seeding logic (the command may still be needed for seeding
  blocks/variants/collections)

**Tests**:

- `phoxtail/streams/tests/test_views.py` — `TestGetStudioForm`,
  `TestStudioIndexView`, `TestStudioContextModalView`,
  `TestStudioApplyContextView`
- `phoxtail/streams/tests/test_forms.py` — `TestStudioContextForm*` classes
- `phoxtail/streams/tests/factories.py` — `BlockSystemPromptFactory`
- `phoxtail/streams/tests/conftest.py` — Studio-specific fixtures

### 3. Clean up the API prompts endpoint

The `/api/streams/v1/prompts/` endpoints still exist and reference
`BlockSystemPrompt`. After the model is deleted:

- Delete `phoxtail/api/streams/v1/prompts.py`
- Remove `resolve_prompt`, `prompt_summary`, `prompt_detail` from `_helpers.py`
- Remove `Prompt*` schemas from `schemas.py`
- Remove the prompts router from `__init__.py`
- Remove `list_prompts`, `get_prompt`, `render_prompt`, `prompt_exists` from
  `phoxtail/cli/studio/client.py`
- Remove `phoxtail studio show prompt` and `phoxtail studio list prompts`
  commands
- Remove prompt-related Rich formatters from `format.py`
- Remove the legacy `--template` flag from `context.py`

### 4. Clean up the `edit` command's prompt cascade

`phoxtail/cli/studio/edit.py` currently has a template-cascade that tries
`variant_editor` → `variant_refiner` prompt templates for the session's
`context.md`. This should be replaced with the new context template rendering.

### 5. Update documentation

- `phoxtail/docs/docs/studio/architecture.md` — remove BlockSystemPrompt from
  the model layer description, update the four-layer diagram
- `phoxtail/docs/docs/studio/cli.md` — rename `prompt` to `context`, remove
  prompt-related commands
- `phoxtail/docs/docs/studio/tutorial-claude-code.md` — update the workflow to
  use `phoxtail_get_context` instead of `phoxtail_render_prompt`
- `phoxtail/docs/docs/studio/roadmap.md` — mark Phase 4 changes
- `phoxtail/docs/docs/engine/streams/studio-architecture.md` — update or delete
  (this documents the old admin-based architecture)

### 6. Migration

A single migration that:

1. Drops the `BlockSystemPrompt` table
2. Drops the `access_stream_studio` permission

Run `makemigrations streams` after deleting the model and permission.
