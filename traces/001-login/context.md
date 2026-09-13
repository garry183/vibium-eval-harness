# Login page (saucedemo.com)

Minimal form: username textbox, password textbox, one submit button. No nav, no links, no hamburger menu on this screen (that appears post-login). Two `heading` (level 4) nodes exist in the tree but are static instructional text ("Accepted usernames are:" / "Password for all users:"), not interactive -- excluded from the element map.

Both inputs are cleanly locatable by placeholder text with zero ambiguity. `role=textbox` alone is ambiguous (matches both fields) so it's documented but not used as primary.

## Testability gaps

- **MEDIUM -- Login button has no exposed accessible name.** It's an `<input type="submit" value="Login">`. The value should compute to an accessible name per the HTML-AAM spec, but the a11y tree returned `{"role": "button"}` with no name, and `text=Login` matched zero elements (Playwright's text engine doesn't read the `value` attribute). Only reliable semantic locator is bare `role=button`, which is unambiguous *today* solely because it's the only button on the page -- brittle if the page ever adds a second button (e.g. a "forgot password" or SSO button). Recommend the writer agent prefer the CSS fallback `[data-test="login-button"]` for resilience, or assert on visible/rendered value text rather than accessible name.
- **LOW -- `data-test` attributes aren't picked up by vibium's `testid` query.** SauceDemo uses `data-test="username"` / `data-test="password"` / `data-test="login-button"`, but vibium's testid finder appears to target `data-testid` (or similar), so all three testid probes returned zero matches. These are still valid, stable CSS fallbacks -- just not reachable through the semantic testid strategy. Not blocking since placeholder/role primaries work, but worth knowing before assuming testid coverage exists.
