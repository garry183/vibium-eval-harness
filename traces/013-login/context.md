# Login page — https://www.saucedemo.com/

Single-purpose Swag Labs login screen: a form with a username textbox, a password textbox, and one submit button (rendered as `<input type=submit value="Login">`). Two static headings ("Accepted usernames are: ...", "Password for all users: secret_sauce") list valid test credentials but are not interactive. No links, checkboxes, or other controls on this page.

All three interactive elements resolved to unambiguous, high-confidence semantic locators:
- Username field → `placeholder=Username`
- Password field → `placeholder=Password`
- Login button → `label=Login` (accessible name), backed up by `role=button` since it's currently the only button on the page

## Testability gaps
- **LOW** — No `data-test`/`data-testid` attributes are exposed to the testid query strategy on any of the three elements. Not a blocker (placeholder/label locators are solid and stable), but if the app's DOM changes wording, tests relying on `label`/`placeholder` would break with no testid fallback to catch it.
- **LOW** — The login button's accessible name ("Login") comes from the `value` attribute of an `<input type=submit>`, not a text node. A naive `text=Login` locator returns zero matches — writer agent should use `label=Login`, not `text=`, for this control. Documented in element-map to prevent a flaky/incorrect locator downstream.
- **LOW** — `role=textbox` alone is ambiguous (matches both username and password, count=2). Must always pair with `placeholder=` to disambiguate; do not use bare role for these two fields.

No HIGH or MEDIUM severity gaps — this page is small and fully testable with semantic locators.
