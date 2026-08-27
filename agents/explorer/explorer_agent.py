"""Explorer agent: an LLM-driven Vibium session that maps a live page's
interactive elements into the shared ElementRecord schema.

Writer never gets browser tools -- this is the only agent allowed to touch
the live DOM. Its output is the sole source of truth everything downstream
reads from.
"""

import argparse
import asyncio
import json

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, ToolUseBlock, query

from agents.explorer.vibium_tools import close_browser, vibium_server
from agents.shared.config import MODELS, TARGET_BASE_URL, explorer_output_dir

SYSTEM_PROMPT = """You are the explorer agent in a test-automation pipeline. \
Your only job is to map a page's interactive elements so a downstream writer \
agent can generate reliable Playwright tests without ever looking at the \
live DOM itself. Be thorough and skeptical -- a wrong locator here becomes a \
flaky test later.

Rules:
- Primary locator for every element MUST be semantic (role, label, text, \
  placeholder, or testid). CSS/XPath is only allowed as a documented \
  fallback strategy, never as primary.
- If a semantic query for an element returns more than 1 match, that \
  locator is ambiguous -- note it and either find a more specific semantic \
  strategy or mark it as a testability_gap.
- Capture the accessibility tree first, before proposing any strategy --
  it is ground truth, not a strategy source itself.
- For each interactive element you find: propose 1-2 locator strategies via \
  vibium_find (which tells you the match count -- use it to judge \
  confidence), and record whether the accessible name differs from any \
  visible text you used.
- When you're done, write EXACTLY ONE JSON object to the given output path \
  using the Write tool, matching this shape:
{
  "page": "<page name>",
  "url": "<final url>",
  "viewport": "<width>x<height>",
  "crawled_at": "<iso8601 timestamp you compute from context>",
  "stats": {"total": N, "with_primary": N, "gaps": N},
  "elements": [
    {
      "name": "<short identifier, e.g. usernameInput>",
      "role": "<aria role>",
      "strategies": [
        {"type": "role|label|text|placeholder|testid|css|xpath",
         "selector": "<vibium find() kwargs as a string, e.g. role=button,text=Login>",
         "count": N, "confidence": 1-5, "note": null}
      ],
      "primary": {..same shape as one strategy..} or null,
      "or_chain": "<human-readable fallback chain>" or null,
      "accessibility_node": {"role": "...", "name": "..."},
      "testability_gap": true/false,
      "gap_note": "<reason>" or null
    }
  ]
}
Also write a short "context.md" alongside it: a prose summary of the page \
and a bulleted list of any testability gaps with severity (HIGH/MEDIUM/LOW).
"""


async def explore_page(page_name: str, path: str) -> None:
    out_dir = explorer_output_dir(page_name)
    url = f"{TARGET_BASE_URL}{path}"

    tool_names = [
        "mcp__vibium__vibium_navigate",
        "mcp__vibium__vibium_get_a11y_tree",
        "mcp__vibium__vibium_find",
        "mcp__vibium__vibium_click",
        "mcp__vibium__vibium_screenshot",
        "Write",
    ]
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        mcp_servers={"vibium": vibium_server},
        tools=tool_names,  # restricts availability -- allowed_tools alone only pre-approves
        allowed_tools=tool_names,
        strict_mcp_config=True,  # otherwise the CLI also loads MCP servers from user/project settings
        setting_sources=[],  # isolation mode -- otherwise the CLI also loads the user's ~/.claude/CLAUDE.md etc.
        permission_mode="acceptEdits",
        model=MODELS["explorer"],
    )

    map_path = out_dir / "element-map.json"
    context_path = out_dir / "context.md"
    prompt = (
        f"Explore the page at {url} (call it \"{page_name}\"). "
        f"Navigate there, capture the accessibility tree, identify every "
        f"interactive element, propose and validate locator strategies via "
        f"vibium_find, then write the element map to {map_path} and the "
        f"context summary to {context_path}, exactly as specified in your "
        f"system prompt."
    )

    print(f"[explorer] exploring {url} -> {out_dir}")
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(f"[explorer] {block.text}")
                    elif isinstance(block, ToolUseBlock):
                        print(f"[explorer] tool: {block.name}({json.dumps(block.input)[:120]})")
    finally:
        close_browser()

    if not map_path.exists():
        raise RuntimeError(
            f"Explorer finished without writing {map_path} -- check the "
            f"transcript above for what went wrong."
        )
    print(f"[explorer] done: {map_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True, help="short page name, e.g. login")
    parser.add_argument("--path", default="/", help="URL path under TARGET_BASE_URL")
    args = parser.parse_args()
    asyncio.run(explore_page(args.page, args.path))


if __name__ == "__main__":
    main()
