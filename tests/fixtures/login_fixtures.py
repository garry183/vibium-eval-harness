import pytest

from tests.pages.login_page import LoginPage
from tests.modules.login_module import goto_login


@pytest.fixture
def login_page(page):
    """Navigates to the login page and returns its Page Object.

    The login page has no auth precondition -- it IS the auth entry point.
    """
    page_obj = LoginPage(page)
    goto_login(page_obj)
    return page_obj
