"""Unit 1 loader tests. Scaffolding -- the loader is dumb by design, so these
check the two things that would silently corrupt every downstream number: a
target read under the wrong schema, and a path composed wrongly."""

import json

import pytest

from evals.dataset.loader import Sample, load_sample, load_samples


def test_login_sample_loads():
    s = load_sample("login")
    assert s.sample_id == "login"
    assert s.path == "/"
    assert len(s.elements) == 3
    assert {e["name"] for e in s.elements} == {"usernameInput", "passwordInput", "loginButton"}


def test_url_composes_against_any_base():
    s = load_sample("login")
    assert s.url("https://www.saucedemo.com") == "https://www.saucedemo.com/"
    assert s.url("http://127.0.0.1:8899/") == "http://127.0.0.1:8899/"


def test_login_has_a_snapshot():
    assert load_sample("login").has_snapshot


def test_load_samples_yields_and_is_sorted():
    ids = [s.sample_id for s in load_samples()]
    assert ids == sorted(ids)
    assert "login" in ids


def test_sample_is_immutable():
    s = load_sample("login")
    with pytest.raises(Exception):
        s.sample_id = "other"


def test_missing_sample_raises():
    with pytest.raises(FileNotFoundError):
        load_sample("does-not-exist")


def _write_target(tmp_path, monkeypatch, payload):
    import evals.dataset.loader as loader

    d = tmp_path / "fake"
    d.mkdir()
    (d / "target.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(loader, "DATASET_DIR", tmp_path)


def test_wrong_schema_is_refused(tmp_path, monkeypatch):
    _write_target(tmp_path, monkeypatch, {"schema": "target-v2", "url": "https://x/", "elements": [{}]})
    with pytest.raises(ValueError, match="target-v1"):
        load_sample("fake")


def test_empty_target_is_refused(tmp_path, monkeypatch):
    _write_target(tmp_path, monkeypatch, {"schema": "target-v1", "url": "https://x/", "elements": []})
    with pytest.raises(ValueError, match="no elements"):
        load_sample("fake")


def test_path_recovered_from_target_url(tmp_path, monkeypatch):
    _write_target(tmp_path, monkeypatch,
                  {"schema": "target-v1", "url": "https://x/cart.html", "elements": [{"name": "a"}]})
    assert load_sample("fake").path == "/cart.html"
