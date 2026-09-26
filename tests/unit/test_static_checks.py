"""check_writer_files replaces what used to be LLM-judged prose instructions
("look for TODOs, hardcoded URLs...") with grep. These pin the exact
boundary cases -- a docstring mentioning a URL in prose must NOT false-positive,
but a URL assigned as a literal string must.
"""

from agents.grader.static_checks import check_writer_files


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return p


def test_clean_files_with_all_layers_present_produce_no_failures(tmp_path):
    spec = _write(tmp_path, "test_login.py", "def test_x(login_page):\n    assert True\n")
    failures = check_writer_files("login", {"page": [spec], "spec": [spec]})
    assert failures == []


def test_missing_layers_are_all_reported(tmp_path):
    spec = _write(tmp_path, "test_login.py", "def test_x(login_page):\n    assert True\n")
    layer_files = {"page": [spec], "module": [], "fixture": [], "spec": [spec], "catalogue": []}
    failures = check_writer_files("login", layer_files)
    assert len(failures) == 3
    assert all("missing layer" in f for f in failures)
    joined = " ".join(failures)
    assert "module" in joined and "fixture" in joined and "catalogue" in joined


def test_todo_marker_detected(tmp_path):
    p = _write(tmp_path, "login_page.py", "# TODO: fix this locator\nclass X: pass\n")
    failures = check_writer_files("login", {"page": [p]})
    assert any("TODO" in f for f in failures)


def test_time_sleep_detected(tmp_path):
    p = _write(tmp_path, "test_login.py", "import time\ndef test_x():\n    time.sleep(2)\n")
    failures = check_writer_files("login", {"spec": [p]})
    assert any("time.sleep" in f for f in failures)


def test_hardcoded_url_literal_detected(tmp_path):
    p = _write(tmp_path, "login_module.py", 'URL = "https://www.saucedemo.com/"\n')
    failures = check_writer_files("login", {"module": [p]})
    assert any("hardcoded URL" in f for f in failures)


def test_url_mentioned_in_docstring_prose_is_not_flagged(tmp_path):
    # Regression guard: the real login.testcases.md-adjacent docstring style
    # mentions a URL inline in a sentence, not as an assigned string literal.
    content = (
        '"""Spec: login page (https://www.saucedemo.com/).\n\n'
        'Credential values are Sauce Demo public test accounts."""\n'
        "def test_x():\n    assert True\n"
    )
    p = _write(tmp_path, "test_login.py", content)
    failures = check_writer_files("login", {"spec": [p]})
    assert failures == []


def test_fstring_interpolated_url_is_not_flagged(tmp_path):
    content = (
        "from agents.shared.config import TARGET_BASE_URL\n"
        'def test_x():\n    assert f"{TARGET_BASE_URL}/inventory.html" == "x"\n'
    )
    p = _write(tmp_path, "test_login.py", content)
    failures = check_writer_files("login", {"spec": [p]})
    assert failures == []


_PAGE_OBJECT = '''
class LoginPage:
    def __init__(self, page):
        self.page = page

    @property
    def username_input(self):
        return self.page.get_by_placeholder("Username").or_(self.page.locator("[data-test='username']"))

    @property
    def login_button(self):
        return self.page.locator("[data-test='login-button']")
'''


def test_css_only_page_object_property_detected(tmp_path):
    p = _write(tmp_path, "login_page.py", _PAGE_OBJECT)
    failures = check_writer_files("login", {"page": [p]})
    assert len(failures) == 1
    assert "'login_button'" in failures[0]


def test_css_fallback_chained_to_semantic_primary_is_not_flagged(tmp_path):
    content = _PAGE_OBJECT.replace(
        "self.page.locator(\"[data-test='login-button']\")",
        "self.page.get_by_role(\"button\", name=\"Login\").or_(self.page.locator(\"[data-test='login-button']\"))",
    )
    p = _write(tmp_path, "login_page.py", content)
    assert check_writer_files("login", {"page": [p]}) == []


def test_missing_layer_reported(tmp_path):
    p = _write(tmp_path, "test_login.py", "def test_x(): assert True\n")
    failures = check_writer_files("login", {"spec": [p], "fixture": []})
    assert any("missing layer: no fixture file" in f for f in failures)
