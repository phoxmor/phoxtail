"""MCP tools for rendering pages and blocks as screenshots via Playwright."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Image as MCPImage

from phoxtail.mcp import mcp_server
from phoxtail.mcp._http import api_base_url, outbound_token

_VIEWPORTS: dict[str, dict] = {
    "desktop": {"width": 1440, "height": 810},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 390, "height": 844},
}

_VISION_DIR = ".phoxtail/vision"


def _resolve_save_path(stem: str, viewport: str) -> Path | None:
    """Return .phoxtail/vision/<stem>-<viewport>.png if a project root is found."""
    from phoxtail.cli.utils.config import find_config_file

    config = find_config_file()
    if config is None:
        return None
    vision_dir = config.parent / _VISION_DIR
    vision_dir.mkdir(parents=True, exist_ok=True)
    return vision_dir / f"{stem}-{viewport}.png"


@mcp_server.tool(
    name="phoxtail_studio_render_block",
    description=(
        "Take a screenshot of a specific block on a page and return it as an image. "
        "Use this after making variant changes to visually verify the result — "
        "no need to ask the user for a screenshot. "
        "Pass the same identifiers from the block chip: page_id and block_uuid. "
        "viewport: 'desktop' (default, 1440px), 'tablet' (768px), 'mobile' (390px), "
        "or 'all' to get a side-by-side contact sheet of all three viewports. "
        "theme: 'light' (default) or 'dark' to render in the given color scheme. "
        "The block is rendered in real page context (real surrounding blocks, "
        "real CSS, real fonts). "
        "Screenshots are saved to .phoxtail/vision/ in the project root and also "
        "returned inline so you can see them immediately."
    ),
)
async def render_block(
    page_id: int,
    block_uuid: str,
    viewport: str = "desktop",
    theme: str = "light",
) -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return json.dumps(
            {"error": ("Playwright is not installed. Run: uv add playwright && playwright install chromium")}
        )

    token = outbound_token()
    if not token:
        return json.dumps(
            {"error": "No bearer token. Local: run phoxtail auth login. Remote: send an Authorization header."}
        )

    base = api_base_url().rstrip("/")
    screenshot_url = f"{base}/phoxtail-agent/screenshot/{page_id}/{block_uuid}/?token={token}"
    selector = f"#phoxtail-block-{block_uuid}"

    viewports_to_capture = list(_VIEWPORTS.keys()) if viewport == "all" else [viewport]
    if viewport not in _VIEWPORTS and viewport != "all":
        return json.dumps({"error": f"Unknown viewport '{viewport}'. Use: desktop, tablet, mobile, all"})

    captures: list[bytes] = []
    color_scheme = "dark" if theme == "dark" else "light"

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for vp_name in viewports_to_capture:
            ctx = await browser.new_context(viewport=_VIEWPORTS[vp_name], color_scheme=color_scheme)
            page = await ctx.new_page()
            resp = await page.goto(screenshot_url)
            if resp and resp.status == 403:
                await browser.close()
                return json.dumps({"error": "Access denied. Check that the token has chatbot access."})
            await page.wait_for_load_state("load")
            await page.evaluate("document.fonts.ready")
            element = page.locator(selector)
            await element.wait_for(state="visible", timeout=10_000)
            captures.append(await element.screenshot())
            await ctx.close()
        await browser.close()

    if len(captures) == 1:
        image_bytes = captures[0]
    else:
        # Contact sheet: stitch all three viewports side-by-side
        try:
            import io

            from PIL import Image as PILImage

            images = [PILImage.open(io.BytesIO(c)) for c in captures]
            total_width = sum(img.width for img in images)
            max_height = max(img.height for img in images)
            sheet = PILImage.new("RGB", (total_width, max_height), (255, 255, 255))
            x = 0
            for img in images:
                sheet.paste(img, (x, 0))
                x += img.width
            buf = io.BytesIO()
            sheet.save(buf, format="PNG")
            image_bytes = buf.getvalue()
        except ImportError:
            image_bytes = captures[0]

    save_path = _resolve_save_path(block_uuid, f"{viewport}-{theme}")
    if save_path:
        save_path.write_bytes(image_bytes)

    return MCPImage(data=image_bytes, format="png")


@mcp_server.tool(
    name="phoxtail_studio_screenshot_page",
    description=(
        "Take a viewport screenshot of a full page and return it as an image. "
        "Use this to capture what a page looks like at a given breakpoint — "
        "desktop (1440px), tablet (768px), or mobile (390px). "
        "Unlike phoxtail_studio_render_block this captures the entire viewport, "
        "not a single block element. "
        "theme: 'light' (default) or 'dark'. "
        "The page is rendered with its real site context (correct palette, fonts, "
        "shared blocks). "
        "Screenshots are saved to .phoxtail/vision/page-<page_id>-<viewport>-<theme>.png "
        "and also returned inline."
    ),
)
async def screenshot_page(
    page_id: int,
    viewport: str = "desktop",
    theme: str = "light",
) -> Any:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return json.dumps(
            {"error": "Playwright is not installed. Run: uv add playwright && playwright install chromium"}
        )

    if viewport not in _VIEWPORTS:
        return json.dumps({"error": f"Unknown viewport '{viewport}'. Use: desktop, tablet, mobile"})

    token = outbound_token()
    if not token:
        return json.dumps(
            {"error": "No bearer token. Local: run phoxtail auth login. Remote: send an Authorization header."}
        )

    base = api_base_url().rstrip("/")
    screenshot_url = f"{base}/phoxtail-agent/screenshot/{page_id}/?token={token}"
    color_scheme = "dark" if theme == "dark" else "light"

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport=_VIEWPORTS[viewport], color_scheme=color_scheme)
        page = await ctx.new_page()
        resp = await page.goto(screenshot_url)
        if resp and resp.status == 403:
            await browser.close()
            return json.dumps({"error": "Access denied. Check that the token has chatbot access."})
        await page.wait_for_load_state("load")
        await page.evaluate("document.fonts.ready")
        image_bytes = await page.screenshot()
        await ctx.close()
        await browser.close()

    save_path = _resolve_save_path(f"page-{page_id}", f"{viewport}-{theme}")
    if save_path:
        save_path.write_bytes(image_bytes)

    return MCPImage(data=image_bytes, format="png")
