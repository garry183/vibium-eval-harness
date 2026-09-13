import pytest

pytest_plugins = [
    "tests.fixtures.login_fixtures",
]


def pytest_collection_modifyitems(config, items):
    """tests/specs hits a real browser against the live target site; tests/unit
    is pure Python. Auto-marking by path means `pytest -m "not live"` runs
    the fast deterministic suite without every spec file needing its own
    @pytest.mark.live decorator.
    """
    for item in items:
        if "tests/specs" in item.fspath.strpath.replace("\\", "/"):
            item.add_marker(pytest.mark.live)
