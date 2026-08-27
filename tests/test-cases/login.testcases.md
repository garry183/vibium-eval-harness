# Login Page -- Test Case Catalogue

Source: `tests/specs/test_login.py` (generated from element-map.json + context.md, no critical_failures present -- 1 documented gap addressed via workaround, see below).

## Covered

- **test_login_form_elements_are_visible** -- verifies the username input, password input, and login button are all visible on page load.
- **test_credentials_hint_panel_displays_expected_headings** -- verifies both static headings ("Accepted usernames are:" and "Password for all users:") are visible and have the exact expected text.
- **test_successful_login_navigates_away_from_login_page** -- fills valid credentials (`standard_user` / `secret_sauce`) and submits, asserting the browser navigates to `/inventory.html`.
- **test_invalid_login_stays_on_login_page** -- fills invalid credentials and submits, asserting the browser URL remains on the login page (`/`).

## Gaps / Skips

- **Login button locator (HIGH gap, addressed):** `loginButton` has `testability_gap: true` -- no accessible name, `role=button` only works by accident (sole button on page), `text=Login` and testid both fail. Per the element map's `gap_note`, used the documented CSS fallback `[data-test='login-button']` as primary in the Page Object. If a second unlabeled button is ever added, this remains safe since it's an explicit attribute selector, not a positional `role=button` guess.
- **No error-message assertion test (skipped):** element-map.json maps only 5 elements on this page, none of which is a login-error/alert container. Testing the *content* of an invalid-login error message would require inventing a locator not present in the map, which is disallowed. Only the safe side-effect (URL not changing) is asserted instead.
- **Heading disambiguation caution (not a skip, flagged):** `accepted_usernames_heading`'s primary locator (`role=heading,text=Accepted usernames are:`) was noted in the element map as "not independently re-validated for count=1 in isolation." Used as documented primary; if it turns out ambiguous at runtime, re-crawl is needed to confirm.
