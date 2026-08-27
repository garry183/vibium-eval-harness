# Fix log -- login

## tests/specs/test_login.py::test_login_form_elements_are_visible[chromium]
- **Category**: selector_rot
- **Root cause**: LoginPage.username_input used corrupted locator strings ("Username_DELIBERATELY_BROKEN" placeholder and "[data-test='username_ALSO_BROKEN']" CSS fallback) that match nothing in the DOM, per the aria snapshot in the traceback which shows the real textbox is accessible name "Username". element-map.json documents the correct primary locator as placeholder=Username with fallback [data-test='username'].
- **Fix applied**: Restored username_input in tests/pages/login_page.py to use get_by_placeholder("Username").or_(locator("[data-test='username']")), matching element-map.json's documented primary/or_chain for usernameInput.
- **Re-verified**: PASS

## tests/specs/test_login.py::test_successful_login_navigates_away_from_login_page[chromium]
- **Category**: n/a -- resolved as a side effect of an earlier fix in this run
- **Re-verified**: PASS

## tests/specs/test_login.py::test_invalid_login_stays_on_login_page[chromium]
- **Category**: n/a -- resolved as a side effect of an earlier fix in this run
- **Re-verified**: PASS

## Final full-suite result: GREEN