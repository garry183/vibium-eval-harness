"""Freezes a live page to disk so the eval stops depending on the internet.

Unit 1 plumbing. The point is reproducibility: `evals/dataset/login/target.json`
was hand-verified against SauceDemo's DOM on 2026-09-08 and rots silently the
day they edit their markup. Against a frozen copy, a failing run is always the
explorer's fault -- which is the only condition under which the number means
anything.

What it saves: the raw HTTP response bodies, verbatim, at their original paths.
Not `page.content()` -- that is the post-JavaScript DOM, and replaying it would
be a different document from the one the explorer originally saw. Byte-faithful
resources served from a local root reproduce the real load, JS included.

Known limit: cross-origin assets are skipped and reported. If the page needs
one to render correctly, the snapshot is not faithful and the script says so
rather than quietly producing a broken copy.

Usage:
    python -m tools.snapshot_page                        # login page
    python -m tools.snapshot_page --sample login --path /
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from agents.shared.config import ROOT, TARGET_BASE_URL

DATASET = ROOT / "evals" / "dataset"


def _local_path(root: Path, url: str) -> Path:
    """Map a URL to a file under root, mirroring the server's path layout."""
    p = urlparse(url).path
    if not p or p.endswith("/"):
        p = p + "index.html"
    return root / p.lstrip("/")


def snapshot(sample: str, path: str, base_url: str) -> None:
    url = base_url.rstrip("/") + path
    out = DATASET / sample / "snapshot"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    origin = urlparse(url).scheme + "://" + urlparse(url).netloc
    saved: list[dict] = []
    skipped: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()

        def on_response(resp):
            if not resp.url.startswith(origin):
                skipped.append(resp.url)
                return
            try:
                body = resp.body()
            except Exception as e:  # redirects and 204s have no body
                skipped.append(f"{resp.url} ({type(e).__name__})")
                return
            dest = _local_path(out, resp.url)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            saved.append({
                "url": resp.url,
                "file": str(dest.relative_to(out)).replace("\\", "/"),
                "status": resp.status,
                "content_type": (resp.header_value("content-type") or "").split(";")[0],
                "bytes": len(body),
            })

        page.on("response", on_response)
        page.goto(url, wait_until="networkidle")
        title = page.title()
        browser.close()

    (out / "MANIFEST.json").write_text(json.dumps({
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_url": url,
        "title": title,
        "resources": sorted(saved, key=lambda r: r["file"]),
        "skipped_cross_origin": sorted(set(skipped)),
    }, indent=2), encoding="utf-8")

    print(f"[snapshot] {url} -> {out}")
    for r in saved:
        print(f"  {r['status']}  {r['bytes']:>8}  {r['content_type']:<24} {r['file']}")
    if skipped:
        print(f"\n[snapshot] WARNING: {len(set(skipped))} cross-origin/bodyless resources not saved:")
        for s in sorted(set(skipped)):
            print(f"  {s}")
        print("  If the page needs any of these to render, this snapshot is NOT faithful.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="login")
    ap.add_argument("--path", default="/")
    ap.add_argument("--base-url", default=TARGET_BASE_URL)
    a = ap.parse_args()
    snapshot(a.sample, a.path, a.base_url)


if __name__ == "__main__":
    main()
