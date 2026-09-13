"""Side-by-side view of what every run said about the same thing.

Plumbing for Unit 0: holding 8 element-maps in your head at once is the part
that's genuinely hard for a human. This lays them out so disagreements are
visible without having to remember anything.

It DISPLAYS, it does not JUDGE -- no defect is flagged, nothing is scored. Rows
that disagree are printed with a marker so your eye lands on them; whether a
disagreement is a defect is yours to decide.

Blind spot to keep in mind: this can only surface things the runs disagree
about. Anything all runs get wrong in the same way looks perfectly consistent
here. For that you have to open the page.

Usage:
    python -m tools.compare_runs                 # login runs (default)
    python -m tools.compare_runs --page cart
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict

from agents.shared.config import ROOT

DIFFERS = "  <-- differs"


def load(page: str) -> list[tuple[str, dict]]:
    out = []
    for f in sorted(glob.glob(str(ROOT / "traces" / f"*-{page}" / "element-map.json"))):
        run = os.path.basename(os.path.dirname(f))
        out.append((run, json.load(open(f, encoding="utf-8"))))
    return out


def _row(label: str, values: dict[str, object]) -> None:
    distinct = {json.dumps(v, sort_keys=True) for v in values.values()}
    mark = DIFFERS if len(distinct) > 1 else ""
    print(f"  {label:<26}{mark}")
    for run, v in values.items():
        print(f"      {run:<16} {v}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="login")
    args = ap.parse_args()

    runs = load(args.page)
    if not runs:
        raise SystemExit(f"no traces found for page '{args.page}'")
    print(f"=== {len(runs)} runs for page '{args.page}' ===\n")

    print("--- top-level fields ---")
    for field in ("url", "viewport", "crawled_at"):
        _row(field, {r: d.get(field) for r, d in runs})
    _row("stats", {r: d.get("stats") for r, d in runs})

    print("\n--- element names present ---")
    _row("element names", {r: sorted(e.get("name", "?") for e in d.get("elements") or []) for r, d in runs})

    by_name: dict[str, dict[str, dict]] = defaultdict(dict)
    for run, d in runs:
        for e in d.get("elements") or []:
            by_name[e.get("name", "?")][run] = e

    for name in sorted(by_name):
        present = by_name[name]
        print(f"\n--- element: {name}  (in {len(present)}/{len(runs)} runs) ---")
        _row("primary.type", {r: (e.get("primary") or {}).get("type") for r, e in present.items()})
        _row("primary.selector", {r: (e.get("primary") or {}).get("selector") for r, e in present.items()})
        _row("primary.count", {r: (e.get("primary") or {}).get("count") for r, e in present.items()})
        _row("primary.confidence", {r: (e.get("primary") or {}).get("confidence") for r, e in present.items()})
        _row("testability_gap", {r: e.get("testability_gap") for r, e in present.items()})
        _row("or_chain", {r: e.get("or_chain") for r, e in present.items()})
        _row("n strategies tried", {r: len(e.get("strategies") or []) for r, e in present.items()})
        _row("accessibility_node", {r: e.get("accessibility_node") for r, e in present.items()})


if __name__ == "__main__":
    main()
