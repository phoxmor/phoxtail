# Tutorial: Editing Variants with Claude Code

This tutorial walks through a complete variant editing session using Claude Code and the Phoxtail Studio MCP server. By the end, you will have used an AI agent to surgically edit a block variant, saved it back to the database, and seen the result in a live Wagtail page.

## Prerequisites

- A hatched Phoxtail project (`phoxtail hatch myproject`)
- The project running via Docker (`phoxtail docker up`)
- A [Claude Code](https://claude.ai/code) subscription (Pro, Max, or Team)
- Claude Code installed (`npm install -g @anthropic-ai/claude-code`)
- At least one variant in the database (the `populate_streams` management command seeds the ground-state collection on first run)

## Step 1: Register the MCP server

Every hatched Phoxtail project ships with a `.mcp.json` file in the project root. If yours is missing (projects hatched before Phase 4), create it:

```json
{
  "mcpServers": {
    "phoxtail-studio": {
      "command": "phoxtail",
      "args": ["studio", "mcp", "serve"]
    }
  }
}
```

That is the entire setup. When Claude Code starts, it reads `.mcp.json`, spawns `phoxtail studio mcp serve` as a subprocess, and gains access to every Studio tool.

!!! note
    The MCP server talks to your running Django app at `http://localhost` (the default). If your project uses a different port or you have configured `[studio] api_url` in `phoxtail.toml`, the MCP server picks that up automatically.

## Step 2: Open a Wagtail preview

Before editing, open a Wagtail page that uses the variant you plan to change. Navigate to your site in the browser — for a fresh project, `http://localhost` will render the home page with its default variants.

Keep this tab open. Every time you save a variant, Wagtail's template cache is invalidated and a browser refresh shows the updated design. If your project uses `django-browser-reload`, the tab refreshes automatically.

## Step 3: Start Claude Code

From your project root:

```bash
claude
```

Claude Code discovers the MCP server and connects. You can verify by asking:

```
What Phoxtail Studio tools do you have available?
```

Claude should list the tools: `phoxtail_list_variants`, `phoxtail_get_variant`, `phoxtail_get_context`, `phoxtail_diff_variant`, `phoxtail_update_variant`, `phoxtail_create_variant`, and the listing tools for blocks and collections.

## Step 4: Explore what is available

Ask Claude to show you what is in the project:

```
List all the variants in this project.
```

Claude calls `phoxtail_list_variants` and shows you a summary of every variant — its identifier, name, block, collection, and whether it is the default. A typical fresh project might show:

| identifier | block | collection | default |
|---|---|---|---|
| centered | header_section | ground-state | yes |
| centered-dark | header_section | ground-state | no |
| simple | blog_post_header | ground-state | yes |

You can narrow the scope:

```
Show me only the variants for the header_section block.
```

## Step 5: Read the variant you want to edit

Pick a variant. For this tutorial, we will edit `centered`:

```
Show me the full content of the "centered" variant.
```

Claude calls `phoxtail_get_variant` and returns the variant's HTML, CSS, and JavaScript, along with metadata and an ETag (the concurrency token that ensures safe saves). Study the output — this is what you are about to change.

## Step 6: Get design context (optional but recommended)

For meaningful edits, ask Claude to get the context briefing. This gives it the full design context — block schema, collection tokens, and design philosophy:

```
Get the context for the centered variant of header_section.
```

Claude calls `phoxtail_get_context` with the block and variant identifiers. The result is a detailed context document that describes the block's structure, the collection's design tokens (palettes, fonts, spacing philosophy), and the current variant's code. Claude now has deep context about what it is editing and why.

!!! tip
    You do not have to read the context document yourself. Claude uses it internally to make better editing decisions. But if you are curious about what design constraints apply, ask Claude to summarize the context.

## Step 7: Make your edits

Now tell Claude what you want to change. Be as specific or as vague as you like:

```
Change the hero heading to use a gradient text effect — dark blue
to teal, left to right. Keep everything else the same.
```

Or more surgically:

```
In the CSS, increase the section padding from 4rem to 6rem and
change the heading font-weight from 700 to 800.
```

Or structurally:

```
Add a secondary subtitle line below the main heading. It should use
the collection's body font at a smaller size, with 60% opacity.
Update the HTML and CSS accordingly.
```

Claude reads the current variant content (it already has it from Step 5), reasons about the change, and prepares the updated HTML, CSS, and/or JavaScript.

## Step 8: Preview the diff

Before saving, ask Claude to show you what will change:

```
Show me a diff of what you're about to change.
```

Claude calls `phoxtail_diff_variant` with the proposed new content and returns a unified diff:

```diff
--- a/css
+++ b/css
@@ -1,5 +1,9 @@
 .hero-section {
-    padding: 4rem 2rem;
+    padding: 6rem 2rem;
+}
+
+.hero-heading {
+    background: linear-gradient(to right, #1a365d, #0d9488);
+    -webkit-background-clip: text;
+    -webkit-text-fill-color: transparent;
 }
```

This is your chance to review before anything touches the database. If you do not like something:

```
Actually, make the gradient go from dark blue to purple instead.
```

Claude adjusts and you can diff again.

## Step 9: Save the variant

When you are happy with the changes:

```
Save these changes.
```

Claude calls `phoxtail_update_variant` with the new content and the ETag from Step 5. If no one else has modified the variant in the meantime, the save succeeds and Claude reports the new ETag.

If someone (or something) has modified the variant since you read it, the save fails with a concurrency conflict. Claude will tell you, re-fetch the current version, and you can decide how to proceed.

## Step 10: Check the result

Switch to your browser tab and refresh the Wagtail page. The variant's cache has been invalidated by the save, so you see the updated design immediately — rendered in real content, next to sibling blocks, under actual responsive conditions.

Not satisfied? Go back to Step 7 and iterate. Claude still has the conversation context and the new ETag, so further edits are a continuation, not a restart.

## Step 11: Keep going

A typical refinement session looks like this:

1. "Make the heading larger" &rarr; save &rarr; refresh &rarr; too large
2. "Scale it back to 3.5rem" &rarr; save &rarr; refresh &rarr; good, but spacing feels off
3. "Reduce the margin below the heading by half" &rarr; save &rarr; refresh &rarr; done

Each round is a few seconds. No copy-pasting between windows, no file management, no session directories. The agent reads from and writes to the database directly through the MCP tools.

## Creating a new variant

You are not limited to editing existing variants. To create one from scratch:

```
Create a new variant called "bold-dark" for the header_section block
in the ground-state collection. Start with a dark background, white
text, and bold typography. Use the design context from the collection.
```

Claude calls `phoxtail_get_context` to get the design context for the block, then `phoxtail_create_variant` with the generated HTML, CSS, and JavaScript. The new variant appears in the database immediately and can be selected in the Wagtail admin's block chooser.

## The working-copy alternative

The MCP flow described above is the direct path — the agent reads and writes to the database within the conversation. If you prefer to work with files on disk, the Phase 3 working-copy flow is still available:

```bash
phoxtail studio edit centered
cd .phoxtail/studio/centered/
claude
# ... iterate on template.html, style.css, script.js ...
phoxtail studio commit
```

Both flows use the same API endpoints and the same concurrency model. Choose whichever fits your workflow. The MCP flow is faster for quick iterations; the working-copy flow is better when you want to use git-style diffing, keep a local backup, or hand the files to a non-MCP agent.

## Troubleshooting

**"Could not reach the Phoxtail API"**

The Django dev server is not running. Start it with `phoxtail docker up` and try again.

**"Variant 'x' is ambiguous"**

The identifier exists in multiple block/collection pairs. Be more specific:

```
Show me the "centered" variant for the header_section block
in the ground-state collection.
```

**"ETag mismatch" on save**

The variant was modified between your read and your save (possibly by another user, another Claude session, or a `populate_streams` run). Claude will re-fetch automatically and you can retry.

**Claude does not list Studio tools**

Check that `.mcp.json` exists in the project root and that `phoxtail` is on your PATH. You can test manually:

```bash
phoxtail studio mcp serve
```

If this errors, the issue is in your Phoxtail installation. If it hangs waiting for input (expected — it is waiting for JSON-RPC over stdio), the server is working and the problem is in Claude Code's MCP discovery.
