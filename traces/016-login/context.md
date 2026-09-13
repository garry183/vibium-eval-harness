# Login page (saucedemo.com)

Standard Sauce Labs demo login screen: a form with two text inputs (Username,
Password) and a submit button (`<input type=submit value="Login">`). Below
the form are two non-interactive `<h4>` headings listing accepted usernames
and the shared password -- informational only, not part of the interaction
map. No links or `<img>` elements are exposed to the accessibility tree (the
Swag Labs logo is a CSS background image, not a real `<img>`).

All 3 interactive elements have a confident (5/5), unambiguous semantic
primary locator. No blocking testability gaps.

## Testability notes (none block automation, all LOW)

- **LOW** — Username/Password inputs have no `<label>` element or
  `aria-label`; their accessible name is derived purely from the
  `placeholder` attribute. `placeholder=` locators work reliably (count=1),
  but a `label=` locator will *not* find them despite the a11y tree showing
  a name. Writer agents should use `placeholder=`, not `label=`, for these
  two fields.
- **LOW** — The Login button is `<input type="submit" value="Login">`, not a
  `<button>Login</button>`. A generic `text=Login` locator returns 0 matches
  because it checks `textContent`, not the `value` attribute. Use
  `role=button,label=Login` (or Playwright's `getByRole('button', { name:
  'Login' })`) instead.
- **LOW** — No `data-test`/`data-testid` attributes were resolvable via the
  `testid` locator strategy, even though Sauce Demo is known to ship
  `data-test` attributes in its DOM. The vibium `testid` locator appears to
  require `data-testid` specifically; `data-test` is not picked up. If
  stronger locators are needed, this is a documented CSS fallback only:
  `[data-test="username"]`, `[data-test="password"]`,
  `[data-test="login-button"]` -- not verified as primary since it's
  non-semantic.
