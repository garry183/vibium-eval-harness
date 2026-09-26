"""Page Object for the Sauce Demo login page.

Locators only -- no actions, no assertions.
Sourced from element-map.json (page: login).
"""

from playwright.sync_api import Page


class LoginPage:
    def __init__(self, page: Page):
        self.page = page

    @property
    def username_input(self):
        # primary: placeholder=Username (confidence 5, count 1 per
        # element-map.json), with the documented or_chain fallback
        # [data-test='username'] so a single-strategy drift degrades
        # gracefully instead of hard-timing-out (mirrors login_button).
        return self.page.get_by_placeholder("Username").or_(
            self.page.locator("[data-test='username']")
        )

    @property
    def password_input(self):
        # primary: placeholder=Password (confidence 5), chained with the
        # element-map's documented or_chain fallback [data-test='password'].
        return self.page.get_by_placeholder("Password").or_(
            self.page.locator("[data-test='password']")
        )

    @property
    def login_button(self):
        # <input type=submit value="Login"> -- accessible name comes from the
        # value attribute, so role+name resolves uniquely (evals/dataset/login/
        # target.json correct_primary). text=Login finds nothing because there
        # is no text node; that made an earlier crawl wrongly call this a gap.
        return self.page.get_by_role("button", name="Login").or_(
            self.page.locator("[data-test='login-button']")
        )

    @property
    def accepted_usernames_heading(self):
        # primary: role=heading,text=Accepted usernames are:
        # NOTE (from element-map): not independently re-validated for
        # count=1 in isolation -- flagged as a caution, not a gap.
        return self.page.get_by_role("heading", name="Accepted usernames are:")

    @property
    def password_for_all_users_heading(self):
        # primary: role=heading,text=Password (confidence 5, count 1)
        return self.page.get_by_role("heading", name="Password")
