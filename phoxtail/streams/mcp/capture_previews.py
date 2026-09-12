"""MCP orchestrator: capture preview screenshots for a BlockVariant.

Accepts a ``variant_id``, resolves the linked block, then returns a concrete
step-by-step playbook the agent executes entirely with existing MCP tools:

  1. Pick a suitable parent page and create a temporary never-published page.
  2. Add the variant block with realistic sample content.
  3. Capture 6 screenshots (desktop / tablet / mobile × light / dark).
  4. Upload them to the dedicated "Block Variant Preview Shots" collection.
  5. Attach the 6 image IDs to the BlockVariant via phoxtail_studio_update_variant.
  6. Delete the temp page and local screenshot files.
"""

from __future__ import annotations

import json

from phoxtail.mcp import mcp_server
from phoxtail.streams.mcp._http import request as studio_request

_COLLECTION_NAME = "Block Variant Preview Shots"

_CAPTURES = [
    ("desktop", "light"),
    ("desktop", "dark"),
    ("tablet", "light"),
    ("tablet", "dark"),
    ("mobile", "light"),
    ("mobile", "dark"),
]

_PREVIEW_FIELDS = {
    ("desktop", "light"): "preview_image_desktop",
    ("desktop", "dark"): "preview_image_desktop_dark",
    ("tablet", "light"): "preview_image_tablet",
    ("tablet", "dark"): "preview_image_tablet_dark",
    ("mobile", "light"): "preview_image_mobile",
    ("mobile", "dark"): "preview_image_mobile_dark",
}


@mcp_server.tool(
    name="phoxtail_studio_capture_variant_previews",
    description=(
        "Orchestrator: generate a complete step-by-step playbook for capturing "
        "preview screenshots of a BlockVariant and attaching them to the variant. "
        "Pass the integer `variant_id` "
        "(e.g. from phoxtail_studio_list_variants or phoxtail_studio_get_variant). "
        "The tool resolves the linked block automatically, then returns a "
        "ready-to-execute instruction set. "
        "Follow every numbered step in order using the listed MCP tools. "
        "Workflow summary: resolve variant/block context → create a temporary "
        "never-published photoshooting page → add the variant block with sample "
        "content → take 6 screenshots (desktop/tablet/mobile × light/dark) → "
        "upload to the '" + _COLLECTION_NAME + "' collection → attach the 6 image IDs to the BlockVariant "
        "via phoxtail_studio_update_variant → delete the temp page and local files. "
        "REQUIREMENT: this workflow calls phoxtail_studio_screenshot_page which "
        "requires Playwright + Chromium to be installed in the environment "
        "(uv add 'phoxtail[studio]' && playwright install --with-deps chromium). "
        "If the screenshot step returns a Playwright not installed error, "
        "stop and inform the user."
    ),
)
def capture_variant_previews(variant_id: int) -> str:
    # ------------------------------------------------------------------
    # 1. Fetch the variant to get block_id and names.
    # ------------------------------------------------------------------
    var_resp = studio_request("GET", f"/variants/{variant_id}/")
    if var_resp.status_code == 404:
        return json.dumps({"error": f"Variant {variant_id} not found."})
    var_resp.raise_for_status()
    variant = var_resp.json()

    variant_name = variant.get("name", f"variant-{variant_id}")
    variant_identifier = variant.get("identifier", str(variant_id))

    raw_block = variant.get("block")
    if isinstance(raw_block, dict):
        block_id = raw_block["id"]
        block_name = raw_block.get("name", f"block-{block_id}")
        block_identifier = raw_block.get("identifier", "")
        page_types: list[str] = raw_block.get("page_types") or []
    else:
        block_id = raw_block or variant.get("block_id")
        blk_resp = studio_request("GET", f"/blocks/{block_id}/")
        blk_resp.raise_for_status()
        block = blk_resp.json()
        block_name = block.get("name", f"block-{block_id}")
        block_identifier = block.get("identifier", "")
        page_types = block.get("page_types") or []

    # ------------------------------------------------------------------
    # Build the playbook.
    # ------------------------------------------------------------------
    page_types_note = (
        "\n".join(f"  - {pt}" for pt in page_types)
        if page_types
        else "  (unrestricted — any page type with a compatible body StreamField works)"
    )

    captures_steps = "\n".join(
        f"  {i + 1}. phoxtail_studio_screenshot_page("
        f'page_id=<SHOOT_PAGE_ID>, viewport="{vp}", theme="{th}")'
        f"\n     → saves to .phoxtail/vision/page-<SHOOT_PAGE_ID>-{vp}-{th}.png"
        for i, (vp, th) in enumerate(_CAPTURES)
    )

    upload_steps = "\n".join(
        f"  {i + 1}. phoxtail_images_upload("
        f'\n       file_path=".phoxtail/vision/page-<SHOOT_PAGE_ID>-{vp}-{th}.png",'
        f'\n       title="{block_name} / {variant_name} — {vp.capitalize()} {th.capitalize()}",'
        f"\n       collection_id=<COLLECTION_ID>,"
        f"\n     )"
        f"\n     → store returned image id as <IMG_{vp.upper()}_{th.upper()}>"
        for i, (vp, th) in enumerate(_CAPTURES)
    )

    variant_fields = "\n".join(
        f"    {_PREVIEW_FIELDS[(vp, th)]}_id=<IMG_{vp.upper()}_{th.upper()}>," for vp, th in _CAPTURES
    )

    delete_files = "\n".join(f"  rm .phoxtail/vision/page-<SHOOT_PAGE_ID>-{vp}-{th}.png" for vp, th in _CAPTURES)

    playbook = f"""
=============================================================
VARIANT PREVIEW CAPTURE PLAYBOOK
=============================================================

CONTEXT (pre-fetched — do not re-fetch these)
---------------------------------------------
Variant          : "{variant_name}"  (id={variant_id}, identifier={variant_identifier})
Block            : "{block_name}"  (id={block_id}, identifier={block_identifier})

Block page_types (page types that can host this block):
{page_types_note}

Target image collection : "{_COLLECTION_NAME}"

=============================================================
STEPS — execute in order, do not skip
=============================================================

STEP 1 — Pick a parent page for the temporary shooting page
------------------------------------------------------------
a) Call phoxtail_page_types_list() to see available types and their required fields.
b) Choose the most appropriate page type for the temp page based on page_types
   above.  If the list is empty or no exact match exists, pick any simple
   content page type that supports a body StreamField.
c) Call phoxtail_pages_list_pages(search="...") to find a suitable existing
   parent page that accepts the chosen child type.  A staging or sandbox
   section is ideal; otherwise any non-critical parent works.
d) Note the parent id as <PARENT_ID>.

STEP 2 — Create the temporary photoshooting page (draft, never published)
--------------------------------------------------------------------------
Call:
  phoxtail_pages_create_page(
    type="<chosen_type>",
    parent=<PARENT_ID>,
    title="[photoshoot] {variant_name}",
    slug="photoshoot-{variant_identifier}-{variant_id}",
  )

Note the returned page id as <SHOOT_PAGE_ID> and its _etag as <SHOOT_ETAG>.
⚠️  Do NOT call phoxtail_pages_publish on this page at any point.

STEP 3 — Add the variant block with realistic sample content
------------------------------------------------------------
a) Call phoxtail_studio_get_variant(variant_id={variant_id}) to inspect the
   block schema (HTML template variables) so you know what fields to fill.
b) Compose sample content that best showcases this variant:
   - Use realistic, generic copy (no Lorem ipsum, no placeholder names).
   - Fill every visible field.  Omit optional structural/boolean fields or
     leave them at sensible defaults.
   - For image fields: call phoxtail_pages_list_images() to find an existing
     image, or skip if the field is optional.
c) Call phoxtail_pages_add_block(
     page_id=<SHOOT_PAGE_ID>,
     etag=<SHOOT_ETAG>,
     block_type="{block_identifier}",
     variant={variant_id},
     value={{... sample content ...}},
   )
   Update <SHOOT_ETAG> with the new etag returned.

STEP 4 — Capture 6 screenshots
-------------------------------
The screenshot endpoint renders draft pages — no publishing needed.

{captures_steps}

Each call returns the image inline AND writes it to disk under .phoxtail/vision/.

STEP 5 — Ensure the "{_COLLECTION_NAME}" collection exists
-----------------------------------------------------------
a) Call phoxtail_collections_list() and look for a collection named
   exactly "{_COLLECTION_NAME}".
b) If found  → note its id as <COLLECTION_ID>.
   If missing → call phoxtail_collections_create(name="{_COLLECTION_NAME}")
               and note the returned id as <COLLECTION_ID>.

STEP 6 — Upload the 6 screenshots
----------------------------------
{upload_steps}

STEP 7 — Attach the images to the BlockVariant
-----------------------------------------------
a) Call phoxtail_studio_get_variant(variant_id={variant_id}) to get a
   fresh ETag for the variant.

b) Call phoxtail_studio_update_variant(
     variant_id={variant_id},
     etag=<VARIANT_ETAG>,
{variant_fields}
   )

STEP 8 — Delete the temporary photoshooting page
-------------------------------------------------
a) Call phoxtail_pages_get_page(page_id=<SHOOT_PAGE_ID>) for a fresh etag.
b) Call phoxtail_pages_delete_page(
     page_id=<SHOOT_PAGE_ID>,
     etag=<etag>,
   )
   ⚠️  Confirm page_id matches <SHOOT_PAGE_ID> — this is irreversible.

STEP 9 — Delete local screenshot files
---------------------------------------
Use the Bash tool:
{delete_files}

=============================================================
DONE — "{variant_name}" (variant_id={variant_id}) now has all 6 preview images.
=============================================================
""".strip()

    return playbook
