"""Action flows for the login page. Orchestrates LoginPage locators.

No assertions here -- assertions live only in tests/specs/test_login.py.
"""

from agents.shared.config import TARGET_BASE_URL
from tests.pages.login_page import LoginPage


def goto_login(page_obj: LoginPage):
    page_obj.page.goto(TARGET_BASE_URL)


def login(page_obj: LoginPage, username: str, password: str):
    page_obj.username_input.fill(username)
    page_obj.password_input.fill(password)
    page_obj.login_button.click()
