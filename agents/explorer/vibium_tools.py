"""Vibium wrapped as native Claude Agent SDK tools.

The explorer agent gets these instead of vibium's own MCP server so the whole
stack stays pure Python (no npx/Node dependency) and so the tool surface is
deliberately narrow -- just enough for an LLM to explore a page and reason
about locator quality, mirroring what the accessibility tree gives a human
tester: role, name, count, visibility. Nothing here executes app actions
beyond navigation and clicks needed to reach a page state.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import create_sdk_mcp_server, tool
from vibium import Browser, Element
from vibium.sync_api import browser as vibium_browser

from agents.shared.config import VIBIUM_HEADLESS

_state: dict[str, Any] = {"browser": None, "page": None}


def _get_page():
    if _state["page"] is None:
        b: Browser = vibium_browser.start(headless=VIBIUM_HEADLESS)
        _state["browser"] = b
        _state["page"] = b.new_page()
    return _state["page"]


def close_browser() -> None:
    if _state["browser"] is not None:
        _state["browser"].stop()
        _state["browser"] = None
        _state["page"] = None


def _text_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _find_kwargs(args: dict[str, Any]) -> dict[str, Any]:
    keys = ("role", "text", "label", "placeholder", "testid")
    return {k: args[k] for k in keys if args.get(k)}


@tool(
    "vibium_navigate",
    "Navigate the shared browser page to a URL. Call this first, and again "
    "any time you need to move to a different page in the same crawl.",
    {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
)
async def vibium_navigate(args: dict[str, Any]) -> dict[str, Any]:
    page = await asyncio.to_thread(_get_page)
    await asyncio.to_thread(page.go, args["url"])
    await asyncio.to_thread(page.wait_for_load)
    title = await asyncio.to_thread(page.title)
    return _text_result(json.dumps({"url": page.url(), "title": title}))


@tool(
    "vibium_get_a11y_tree",
    "Return the full accessibility tree of the current page as JSON. This is "
    "ground truth -- capture it before proposing any locator strategy.",
    {"type": "object", "properties": {}, "required": []},
)
async def vibium_get_a11y_tree(_args: dict[str, Any]) -> dict[str, Any]:
    page = await asyncio.to_thread(_get_page)
    tree = await asyncio.to_thread(page.a11y_tree)
    return _text_result(json.dumps(tree, default=str))


@tool(
    "vibium_find",
    "Find elements on the current page by semantic attributes (role, text, "
    "label, placeholder, or testid -- pass whichever you have). Returns the "
    "match count (>1 means the locator is ambiguous) and details of the "
    "first match: role, visible text, and whether it's visible.",
    {
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "text": {"type": "string"},
            "label": {"type": "string"},
            "placeholder": {"type": "string"},
            "testid": {"type": "string"},
        },
        "required": [],
    },
)
async def vibium_find(args: dict[str, Any]) -> dict[str, Any]:
    page = await asyncio.to_thread(_get_page)
    kwargs = _find_kwargs(args)
    if not kwargs:
        return _text_result(json.dumps({"error": "pass at least one of role/text/label/placeholder/testid"}))
    matches: list[Element] = await asyncio.to_thread(page.find_all, **kwargs)
    if not matches:
        return _text_result(json.dumps({"count": 0}))
    first = matches[0]
    detail = {
        "count": len(matches),
        "role": await asyncio.to_thread(first.role),
        "text": await asyncio.to_thread(first.text),
        "is_visible": await asyncio.to_thread(first.is_visible),
    }
    return _text_result(json.dumps(detail))


@tool(
    "vibium_click",
    "Click the first element matching the given semantic attributes. Use "
    "this only to reach a page state you need to explore next (e.g. open a "
    "menu, submit a login) -- never to perform destructive actions.",
    {
        "type": "object",
        "properties": {
            "role": {"type": "string"},
            "text": {"type": "string"},
            "label": {"type": "string"},
            "placeholder": {"type": "string"},
            "testid": {"type": "string"},
        },
        "required": [],
    },
)
async def vibium_click(args: dict[str, Any]) -> dict[str, Any]:
    page = await asyncio.to_thread(_get_page)
    kwargs = _find_kwargs(args)
    element: Element = await asyncio.to_thread(page.find, **kwargs)
    await asyncio.to_thread(element.click)
    await asyncio.to_thread(page.wait_for_load)
    return _text_result(json.dumps({"clicked": kwargs, "url": page.url()}))


@tool(
    "vibium_screenshot",
    "Save a screenshot of the current page to disk. Returns the file path. "
    "Use this to leave visual evidence for gap notes, not as your primary "
    "source of truth -- the accessibility tree is ground truth.",
    {
        "type": "object",
        "properties": {
            "output_dir": {"type": "string"},
            "name": {"type": "string"},
        },
        "required": ["output_dir", "name"],
    },
)
async def vibium_screenshot(args: dict[str, Any]) -> dict[str, Any]:
    page = await asyncio.to_thread(_get_page)
    png_bytes: bytes = await asyncio.to_thread(page.screenshot)
    out_dir = Path(args["output_dir"]) / "screenshots"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{args['name']}.png"
    path.write_bytes(png_bytes)
    return _text_result(json.dumps({"path": str(path)}))


vibium_server = create_sdk_mcp_server(
    name="vibium",
    version="1.0.0",
    tools=[
        vibium_navigate,
        vibium_get_a11y_tree,
        vibium_find,
        vibium_click,
        vibium_screenshot,
    ],
)
