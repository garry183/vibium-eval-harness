"""Covers the exact scenario scope_guard's module docstring documents as the
reason it exists: a runner given "touch only what this failure implicates"
still bundled an unrelated property fix in testing. These tests are the
mechanical backstop for that -- they should fail loudly if traceback-matching
regresses to over- or under-scoping.
"""

from agents.runner.scope_guard import (
    allowed_properties,
    changed_properties,
    properties_named_in_traceback,
    test_name_from_nodeid as name_from_nodeid,  # avoid pytest collecting the imported fn as a test
)

PAGE_OBJECT_SOURCE = '''
class LoginPage:
    def __init__(self, page):
        self.page = page

    @property
    def username_input(self):
        return self.page.get_by_placeholder("Username")

    @property
    def password_input(self):
        return self.page.get_by_placeholder("Password")

    @property
    def login_button(self):
        return self.page.get_by_role("button", name="Login")
'''

MODULE_SOURCE = '''
def login(page_obj, username, password):
    page_obj.username_input.fill(username)
    page_obj.password_input.fill(password)
    page_obj.login_button.click()
'''

SPEC_SOURCE = '''
def test_successful_login(login_page):
    login(login_page, "standard_user", "secret_sauce")
'''


def test_traceback_evidence_scopes_to_only_the_named_property():
    # Locator timeout on username_input: the traceback names that property's
    # line, never reaches password_input's. Evidence must not over-scope to
    # every property login() touches.
    traceback = (
        'page_obj.username_input.fill(username)\n'
        'playwright._impl._errors.TimeoutError: Timeout waiting for locator'
    )
    known = {"username_input", "password_input", "login_button"}
    assert properties_named_in_traceback(traceback, known) == {"username_input"}


def test_allowed_properties_prefers_traceback_evidence_over_call_graph():
    traceback = 'page_obj.username_input.fill(username)\nTimeoutError'
    result = allowed_properties(
        test_name="test_successful_login",
        traceback_text=traceback,
        page_object_source=PAGE_OBJECT_SOURCE,
        spec_source=SPEC_SOURCE,
        module_source=MODULE_SOURCE,
    )
    # Call-graph reachability would allow all three (login() touches all
    # three properties) -- evidence must narrow it to just the one implicated.
    assert result == {"username_input"}


def test_allowed_properties_falls_back_to_call_graph_without_evidence():
    # A pure assertion mismatch: no locator call in the failing frame, so
    # there's nothing to match against in the traceback text.
    traceback = "AssertionError: assert False"
    result = allowed_properties(
        test_name="test_successful_login",
        traceback_text=traceback,
        page_object_source=PAGE_OBJECT_SOURCE,
        spec_source=SPEC_SOURCE,
        module_source=MODULE_SOURCE,
    )
    assert result == {"username_input", "password_input", "login_button"}


def test_allowed_properties_returns_none_when_test_unresolvable():
    result = allowed_properties(
        test_name="test_does_not_exist",
        traceback_text="AssertionError",
        page_object_source=PAGE_OBJECT_SOURCE,
        spec_source=SPEC_SOURCE,
        module_source=MODULE_SOURCE,
    )
    assert result is None


def test_changed_properties_detects_only_the_edited_property():
    before = PAGE_OBJECT_SOURCE
    after = PAGE_OBJECT_SOURCE.replace(
        'get_by_placeholder("Username")', 'get_by_placeholder("Username").or_(page.locator("[data-test=\'username\']"))'
    )
    assert changed_properties(before, after) == {"username_input"}


def test_changed_properties_empty_when_nothing_changed():
    assert changed_properties(PAGE_OBJECT_SOURCE, PAGE_OBJECT_SOURCE) == set()


def test_name_from_nodeid_strips_module_and_parametrize_id():
    assert name_from_nodeid("tests/specs/test_login.py::test_foo[chromium]") == "test_foo"


def test_name_from_nodeid_no_parametrize():
    assert name_from_nodeid("tests/specs/test_login.py::test_foo") == "test_foo"
