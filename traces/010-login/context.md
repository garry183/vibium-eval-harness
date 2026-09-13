# Login Page (saucedemo.com)

Simple, static login form: one `<form>` containing a Username textbox, a Password textbox, and a Login submit button. No JS-driven widgets, no dynamic loading states pre-submit. Below the form are two static heading blocks listing accepted usernames and the shared password ("Accepted usernames are:" / "Password for all users:") -- informational only, not interactive, not included in the element map.

Both text inputs are identified by `placeholder` (Username / Password) since there are no associated `<label>` elements -- `label=` queries fail for both, and bare `role=textbox` is ambiguous (2 matches). Placeholder is the correct primary locator here, not a compromise.

The Login button is rendered from `<input type="submit" value="Login">`. Its visible "text" as reported by the tool is empty (submit-button labels come from the `value` attribute, not text content), but its accessible name resolves to "Login" -- confirmed via `label=Login` and role tree. `role=button` alone is currently unambiguous (only one button on the page) but pair it with the accessible name for durability.

## Testability Gaps

- **MEDIUM** -- `data-test` attributes exist on the real inputs/button (`data-test="username"`, `data-test="password"`, `data-test="login-button"`, per known SauceDemo markup) but are **not** discoverable via the `testid` locator strategy in this toolchain, which only matches `data-testid`. Any downstream test written against `getByTestId()` will fail. Use role/placeholder locators instead, or explicitly configure the test framework's testid attribute to `data-test` if `data-testid`-based locators are required.
- **LOW** -- Login button's accessible name ("Login") comes from an `<input value>` attribute rather than element text content. Playwright's `getByText('Login')` will NOT match it (confirmed: `text=Login` query timed out with 0 matches). Writers must use `getByRole('button', { name: 'Login' })`, not a text locator.
