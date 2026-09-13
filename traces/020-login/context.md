# Login page (saucedemo.com)

Standard login form: username textbox, password textbox, one submit button (rendered as `<input type=submit value="Login">`). Below the form is static informational text (two heading-role blocks listing accepted usernames and the shared password) -- not interactive, excluded from the element map. No links or images with accessible roles were found (logo is a CSS background image, not an `<img>`).

Only 3 interactive elements total, all have confident, unambiguous semantic locators. This is a clean, low-risk page for automation.

## Testability gaps

- **LOW** -- `testid` strategy (vibium's `data-testid` lookup) does not match this site's actual test attribute, `data-test` (e.g. `data-test="username"`, `data-test="login-button"`). Every `testid=...` query timed out. Not blocking since `placeholder`/`label` locators are reliable primaries, but downstream writer agent should NOT assume `data-testid` fallbacks work here -- use `[data-test="..."]` CSS as the documented fallback instead.
- **LOW** -- `text=Login` and `role=button,text=Login` both fail to match the login button because it's an `<input>` element (value attribute, not textContent). Writer agent must use `label=Login` (or `role=button` alone, given only one button exists) instead of `text=`.
- **LOW** -- `label=Username` / `label=Password` (role+label combo) fail even though `placeholder=Username` / `placeholder=Password` succeed -- accessible name comes from the `placeholder` attribute, not `aria-label`, so the `label` strategy is the wrong tool for these two fields specifically. Use `placeholder=` as primary.
