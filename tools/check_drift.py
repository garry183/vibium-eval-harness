"""Answers one question: is the frozen snapshot still the page it claims to be?

Unit 1 plumbing, and the cost of freezing. A snapshot buys reproducibility by
giving up contact with reality -- so something has to keep checking whether the
live site has moved out from under the target. This is that something.

It compares the three parties that must agree:

    target.json   what Gaurav hand-verified on 2026-09-08
    snapshot      what the eval actually runs against
    live          what SauceDemo serves today

target-vs-snapshot drifting means the snapshot is wrong and the eval has been
measuring the explorer against the wrong page. target-vs-live drifting means the
site changed: the eval is still valid, but it is now measuring performance on a
page that no longer exists, and the refresh procedure below applies.

Elements are anchored by the `id` in the target's recorded `html`, not by any
locator under test -- grading a locator with the locator would be circular.

Refresh procedure, when live has drifted and you want to move to the new page:
    1. python -m tools.snapshot_page --sample <s>      (re-capture)
    2. re-verify target.json BY HAND against the new DOM -- do not patch it from
       a diff, and never from an element-map
    3. bump verified_on, and note in target.json what changed and why
    4. the pre-refresh traces are no longer comparable; label them

Usage:
    python -m tools.check_drift                    # login, snapshot + live
    python -m tools.check_drift --skip-live        # offline: snapshot only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from agents.shared.config import ROOT, TARGET_BASE_URL
from tools.serve_snapshot import serve_snapshot

DATASET = ROOT / "evals" / "dataset"

# Attributes that change what a locator resolves to. Everything else (styling
# classes reordered, whitespace) is noise and would make this cry wolf.
SIGNIFICANT = ("id", "name", "type", "placeholder", "value", "data-test", "aria-label", "role")


def _anchor(html: str) -> str | None:
    m = re.search(r'\bid="([^"]+)"', html)
    return f"#{m.group(1)}" if m else None


def _attrs(page, selector: str) -> dict | None:
    loc = page.locator(selector)
    if loc.count() != 1:
        return None
    return {a: loc.get_attribute(a) for a in SIGNIFICANT}


def _expected(html: str) -> dict:
    return {a: (m.group(1) if (m := re.search(rf'\b{a}="([^"]*)"', html)) else None) for a in SIGNIFICANT}


def compare(page, elements: list[dict], label: str) -> int:
    drifted = 0
    for el in elements:
        name, html = el["name"], el["html"]
        sel = _anchor(html)
        if not sel:
            print(f"  {name:<16} SKIP   no id in target html; cannot anchor")
            continue
        actual = _attrs(page, sel)
        if actual is None:
            print(f"  {name:<16} DRIFT  {sel} did not resolve to exactly 1 element on {label}")
            drifted += 1
            continue
        exp = _expected(html)
        diffs = {a: (exp[a], actual[a]) for a in SIGNIFICANT if exp[a] != actual[a]}
        if diffs:
            drifted += 1
            print(f"  {name:<16} DRIFT  on {label}")
            for a, (e, g) in diffs.items():
                print(f"      {a:<12} target={e!r}  {label}={g!r}")
        else:
            print(f"  {name:<16} ok     on {label}")
    return drifted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="login")
    ap.add_argument("--skip-live", action="store_true", help="offline; check the snapshot only")
    a = ap.parse_args()

    target = json.loads((DATASET / a.sample / "target.json").read_text(encoding="utf-8"))
    elements = target["elements"]
    print(f"=== drift check: {a.sample}  (target verified {target['verified_on']}) ===\n")

    total = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        with serve_snapshot(a.sample) as base:
            page = browser.new_page()
            page.goto(base + "/", wait_until="networkidle")
            print("--- target vs snapshot  (a DRIFT here means the eval is invalid) ---")
            total += compare(page, elements, "snapshot")
            page.close()

        if not a.skip_live:
            page = browser.new_page()
            page.goto(TARGET_BASE_URL + "/", wait_until="networkidle")
            print("\n--- target vs live  (a DRIFT here means the site moved on) ---")
            total += compare(page, elements, "live")
            page.close()

        browser.close()

    print(f"\n{'DRIFT DETECTED' if total else 'no drift'} ({total} element/party mismatches)")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
