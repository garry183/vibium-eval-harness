"""Writer agent: turns explorer output into a 4-layer pytest+playwright-python
test suite. Never gets browser or MCP tools -- if it needs to know something
about the live page that isn't in element-map.json or context.md, that's an
explorer gap, not something to guess around.
"""

import argparse
import asyncio
import json

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, ToolUseBlock, query

from agents.shared.config import MODELS, OUTPUT_DIR, TESTS_DIR

SYSTEM_PROMPT = """You are the writer agent. You generate a pytest + \
playwright-python test suite for ONE page, using ONLY the element-map.json \
and context.md you're given -- you have no browser access and must not \
invent locators that aren't in the element map.

Refuse and explain instead of writing anything if the element map has any \
critical_failures unaddressed, or is missing elements needed for the \
requested test cases.

Rules (violating any of these is a failed output, not a style nit):
- No hardcoded base URLs. Import TARGET_BASE_URL from agents.shared.config.
- No time.sleep(). Use Playwright's built-in auto-waiting and explicit \
  `expect(locator).to_be_visible()` / `wait_for` calls only.
- Locators must come from element-map.json's `primary` field, translated to \
  Playwright syntax (role -> get_by_role, label -> get_by_label, text -> \
  get_by_text, placeholder -> get_by_placeholder, testid -> get_by_test_id). \
  Never introduce a CSS/XPath locator that isn't already the documented \
  fallback (or_chain) for that element.
- Write exactly 5 files (4 layers plus a catalogue), for page name "{page}":
  1. tests/pages/{page}_page.py -- a Page Object class. ONLY locator \
     properties (e.g. `@property def username_input(self): return \
     self.page.get_by_placeholder("Username")`). No actions, no assertions.
  2. tests/modules/{page}_module.py -- plain functions that orchestrate \
     Page Object locators into user flows (e.g. `def login(page_obj, user, \
     pw)`). No assertions here either -- this is action-only.
  3. tests/fixtures/{page}_fixtures.py -- pytest fixtures (`@pytest.fixture`) \
     that build on pytest-playwright's built-in `page` fixture, instantiate \
     the Page Object, and perform any precondition setup (e.g. navigating to \
     the page, or logging in if this page requires auth) via the module's \
     functions. Read tests/conftest.py first (if it exists) and add an \
     import line for this fixtures file if one isn't already there -- \
     create conftest.py if it doesn't exist yet. Never overwrite another \
     page's existing import lines.
  4. tests/specs/test_{page}.py -- actual pytest test functions using the \
     fixtures, one test per logical section/behavior, with real assertions \
     (`expect(...)`). This is the only file allowed to contain assertions.
  5. tests/test-cases/{page}.testcases.md -- a human-readable catalogue \
     generated FROM the actual spec file you just wrote (not from a plan): \
     one bullet per test function, its name, and what it verifies.

Do not add tests for elements that have testability_gap: true unless the \
gap_note describes a workaround you're using -- otherwise skip them and \
note the skip in the testcases.md catalogue.
"""


def _check_gate(page: str) -> dict:
    grading_path = OUTPUT_DIR / page / "explore-grading.json"
    if not grading_path.exists():
        raise SystemExit(
            f"Refusing to write tests for '{page}': {grading_path} not found. "
            f"Run the explorer and grader (explore mode) first."
        )
    grading = json.loads(grading_path.read_text())
    if not grading.get("gate_passed"):
        raise SystemExit(
            f"Refusing to write tests for '{page}': explore-grading gate "
            f"failed (band={grading.get('band')}, "
            f"critical_failures={grading.get('critical_failures')}). "
            f"Re-run the explorer, don't patch around a bad crawl."
        )
    return grading


async def write_tests(page: str) -> None:
    _check_gate(page)
    element_map = (OUTPUT_DIR / page / "element-map.json").read_text()
    context_md = (OUTPUT_DIR / page / "context.md").read_text()

    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT.format(page=page),
        tools=["Read", "Write", "Glob"],  # hard restriction -- no Bash/Edit/browser/MCP tools available at all
        allowed_tools=["Read", "Write", "Glob"],
        strict_mcp_config=True,  # otherwise the CLI also loads MCP servers from user/project settings
        setting_sources=[],  # isolation mode -- otherwise the CLI also loads the user's ~/.claude/CLAUDE.md etc.
        cwd=str(TESTS_DIR.parent),
        model=MODELS["writer"],
    )
    prompt = (
        f"Page name: {page}\n\n"
        f"element-map.json:\n{element_map}\n\n"
        f"context.md:\n{context_md}\n\n"
        f"Write the 4 layers plus the test-case catalogue as specified in "
        f"your system prompt, rooted at {TESTS_DIR}."
    )

    print(f"[writer] generating tests for '{page}'")
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(f"[writer] {block.text}")
                elif isinstance(block, ToolUseBlock):
                    print(f"[writer] tool: {block.name}({json.dumps(block.input)[:120]})")

    spec_path = TESTS_DIR / "specs" / f"test_{page}.py"
    if not spec_path.exists():
        raise RuntimeError(f"Writer finished without producing {spec_path}")
    print(f"[writer] done: {spec_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", required=True)
    args = parser.parse_args()
    asyncio.run(write_tests(args.page))


if __name__ == "__main__":
    main()
