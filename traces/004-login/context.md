# Login page — saucedemo.com

Standard SauceDemo login screen: a single form with username textbox, password textbox, and a submit button. No links, checkboxes, or other interactive controls in the DOM — the "Accepted usernames are:" / "Password for all users:" blocks are static `heading` elements (credentials cheat sheet), not interactive, so they're excluded from the element map.

Both text inputs get their accessible name from their `placeholder` attribute (no `<label>`/`aria-label`), so `label=` locators against them fail even though the accessibility tree reports a name — use `placeholder=` as primary.

The login control is `<input type="submit" value="Login">`, not a `<button>` with text content. `text=Login` will fail; `label=Login` (accessible name from the `value` attribute) works and is unambiguous since it's the only button on the page.

## Testability gaps

None blocking — all 3 interactive elements have a confident (5/5), unambiguous semantic locator.

- LOW: `role=button` alone is unambiguous today only because there's exactly one button on the page. Not a gap now, but don't rely on it long-term — prefer `role=button,label=Login`.
- LOW: No `data-testid`/`data-test` attributes are exposed to the `testid` locator strategy used by this tool (tried `login-button`, `username`, `password`, `login-credentials` — all failed). SauceDemo does have `data-test` attributes in the raw DOM, but this tool's `testid` finder didn't match them, so testid is not a viable strategy here despite the app supporting test ids in principle.
- LOW: `vibium_get_a11y_tree` omitted the `name` field for the button and heading nodes in the raw dump, while targeted `vibium_find` calls confirmed real accessible names ("Login", "Accepted usernames are:", "Password for all users:"). Treat the raw tree dump as a starting map, not a complete source of accessible names — verify names via `find()`.
