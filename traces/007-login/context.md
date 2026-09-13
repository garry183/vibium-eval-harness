# Login page (saucedemo.com)

Minimal login form: username textbox, password textbox, one submit button. Two `heading` nodes ("Accepted usernames are:" etc.) exist for the credentials cheat-sheet but are static text, not interactive, so excluded from the element map. No links or images present on this page.

Both text inputs have no associated `<label>`/`aria-label` — their accessible name comes purely from the `placeholder` attribute, so `placeholder=` is the correct and only reliable semantic locator; `label=` queries return zero matches for both.

The login button's accessible name ("Login") comes from its `value`/`aria-label`, not from `textContent` (visible "LOGIN" is CSS-uppercased from "Login", and textContent is empty) — combining `role=button` with `text=Login` fails. Use `role=button` alone (safe today, since it's the only button) or `label=Login` as a semantic fallback.

## Testability gaps
- **MEDIUM** — Login button has no `data-testid`/`data-test` exposed to the testid locator (tried `testid=login-button`, `testid=username`, both 0 matches). Current primary locator (`role=button`) only works because there's exactly one button on the page; it will silently become ambiguous if any other button (e.g., an error-dialog dismiss button) is added. Recommend adding a stable `data-testid` to the login button.
- **LOW** — Neither username nor password input has a `label`/`aria-label`; locators depend entirely on `placeholder` text, which is more likely to be changed by copy edits than a dedicated label/testid would be.
