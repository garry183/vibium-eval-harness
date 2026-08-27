"""
Spec: login page (https://www.saucedemo.com/).

Credential values (standard_user / secret_sauce, invalid_user / wrong_password)
are NOT present in element-map.json or context.md -- they are Sauce Demo's
well-known public test accounts, used here as test data only (no locator
invention involved). If these ever stop working, source real values from the
accepted_usernames_heading / password_for_all_users_heading panel instead.

No error-message assertion test is included: the element map has no locator
for a login-error banner (only 5 elements were mapped, none is an error
container), and inventing one would violate the no-new-locators rule. See
tests/test-cases/login.testcases.md for the corresponding skip note.
"""

from playwright.sync_api import expect

from agents.shared.config import TARGET_BASE_URL
from tests.modules.login_module import login


def test_login_form_elements_are_visible(login_page):
    """Username input, password input, and login button are all present and visible."""
    expect(login_page.username_input).to_be_visible()
    expect(login_page.password_input).to_be_visible()
    expect(login_page.login_button).to_be_visible()


def test_credentials_hint_panel_displays_expected_headings(login_page):
    """The static credentials-hint panel shows both headings with correct text."""
    expect(login_page.accepted_usernames_heading).to_be_visible()
    expect(login_page.accepted_usernames_heading).to_have_text("Accepted usernames are:")
    expect(login_page.password_for_all_users_heading).to_be_visible()
    expect(login_page.password_for_all_users_heading).to_have_text("Password for all users:")


def test_successful_login_navigates_away_from_login_page(login_page):
    """Valid credentials submit successfully and leave the login page."""
    login(login_page, "standard_user", "secret_sauce")
    expect(login_page.page).to_have_url(f"{TARGET_BASE_URL}/inventory.html")


def test_invalid_login_stays_on_login_page(login_page):
    """Invalid credentials do not navigate away from the login page.

    (Error-message content is not asserted -- no locator for it exists in
    the element map. See catalogue for the documented skip.)
    """
    login(login_page, "invalid_user", "wrong_password")
    expect(login_page.page).to_have_url(TARGET_BASE_URL + "/")
