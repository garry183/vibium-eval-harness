# Login page (saucedemo.com)

Standard SauceDemo login screen: a form with two text inputs (username, password) and one submit control, plus a static credentials panel (two headings + a list of usable usernames and the shared password) that is informational only -- not interactive, so it's excluded from the element map. No links, no images exposed to the a11y tree, no other buttons.

The accessibility tree is sparse: it reports the two textboxes with accessible names "Username"/"Password" and a button with no name, even though visually/functionally the "Login" text is present (it comes from the submit input's `value` attribute, not a text node). This mismatch is the main thing the writer agent needs to know about.

## Testability gaps

- **HIGH** — Login button has no accessible name via plain text/role query; a naive `text=Login` locator will fail. Must use `role=button,label=Login` instead. Anyone writing a test from intuition ("find button with text Login") will get a flaky/broken locator.
- **LOW** — `testid` strategy doesn't work anywhere on this page because SauceDemo uses `data-test` attributes, not `data-testid`. All testid-based locators silently fail; CSS attribute selectors (`[data-test='...']`) are a viable fallback but were not directly verifiable through `vibium_find` (no testid/css-attribute passthrough in the tool), so they're documented as unverified fallbacks only.
- **LOW** — `label=Username` / `label=Password` queries fail even though the a11y tree shows those as accessible names. The name comes from placeholder promotion, not an associated `<label>` element, and vibium's label strategy doesn't catch that. Use `placeholder=` instead, which is unambiguous (count 1 each) and 5/5 confidence.
- **LOW** — bare `role=textbox` is ambiguous (2 matches: username + password). Always qualify with placeholder.
