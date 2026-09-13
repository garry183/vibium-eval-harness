"""Runs the explorer N times and archives each run as an immutable trace.

Plumbing for Unit 0 (error analysis) of COURSE.md -- deliberately NOT under
evals/, because the dataset layout is Unit 1 material and shouldn't be decided
by a collection script.

The explorer always writes to output/explorer/<page>/, so every run clobbers
the last one. This copies that directory out to traces/<run-id>/ after each
run, together with the captured stdout -- the "[explorer] tool: ..." lines are
the tool-call sequence, i.e. the trajectory data Unit 6 needs. Regenerating
those later means paying for 20 more runs, so they're kept from the start.

Failed runs are archived too. A crash is a data point for error analysis, not
a reason to stop the loop.

Usage:
    python -m tools.collect_traces                 # full plan (20 runs)
    python -m tools.collect_traces --dry-run       # print the plan, run nothing
    python -m tools.collect_traces --limit 1       # smoke test
    python -m tools.collect_traces --only login    # one page only
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from agents.shared.config import MODELS, ROOT, TARGET_BASE_URL

TRACES_DIR = ROOT / "traces"
EXPLORER_OUT = ROOT / "output" / "explorer"

# login gets the most repeats on purpose: repeated runs of one identical input
# are the only thing that shows run-to-run variance, and login is the cheapest
# page to repeat.
PLAN: list[tuple[str, str, int]] = [
    ("login", "/", 8),
    ("inventory", "/inventory.html", 6),
    ("cart", "/cart.html", 6),
]

MODEL = MODELS["explorer"]
ARTIFACTS = ("element-map.json", "context.md")


def _expand(plan: list[tuple[str, str, int]]) -> list[tuple[str, str]]:
    """[(page, path, n)] -> flat [(page, path)], interleaved so an early abort
    still leaves a spread across pages rather than 8 logins and nothing else."""
    rounds: list[tuple[str, str]] = []
    remaining = [[page, path, n] for page, path, n in plan]
    while any(r[2] > 0 for r in remaining):
        for r in remaining:
            if r[2] > 0:
                rounds.append((r[0], r[1]))
                r[2] -= 1
    return rounds


def _completed_ids() -> set[str]:
    if not TRACES_DIR.exists():
        return set()
    return {p.name for p in TRACES_DIR.iterdir() if (p / "meta.json").exists()}


def run_one(index: int, page: str, path: str) -> dict:
    run_id = f"{index:03d}-{page}"
    dest = TRACES_DIR / run_id
    dest.mkdir(parents=True, exist_ok=True)

    env = {
        **os.environ,
        "VIBE_CHECK_MODEL_EXPLORER": MODEL,  # pinned, so a later config edit can't
        "VIBIUM_HEADLESS": "true",           # silently change what these traces are
    }
    cmd = [sys.executable, "-m", "agents.explorer.explorer_agent", "--page", page, "--path", path]

    # The explorer has Write but not Read, and Write refuses to overwrite a file
    # it hasn't Read -- so a leftover artifact from the previous run silently
    # blocks this one from writing at all. Clear the target artifacts first.
    # (explorer_agent's own `if not map_path.exists()` guard does not catch this:
    # the stale file exists, so it reports success. See ARTIFACTS below for the
    # freshness check that does catch it.)
    src = EXPLORER_OUT / page
    for name in ARTIFACTS:
        (src / name).unlink(missing_ok=True)

    started = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    duration = round(time.time() - started, 1)

    (dest / "stdout.log").write_text(proc.stdout or "", encoding="utf-8")
    if proc.stderr:
        (dest / "stderr.log").write_text(proc.stderr, encoding="utf-8")

    # Freshness, not existence: an artifact older than this run's start is a
    # leftover, and copying it would silently relabel a previous run's output as
    # this one's. Presence is not proof of production.
    copied, stale = [], []
    for name in ARTIFACTS:
        f = src / name
        if not f.exists():
            continue
        if f.stat().st_mtime < started:
            stale.append(name)
            continue
        shutil.copy2(f, dest / name)
        copied.append(name)

    meta = {
        "run_id": run_id,
        "index": index,
        "page": page,
        "url": f"{TARGET_BASE_URL}{path}",
        "model": MODEL,
        "exit_code": proc.returncode,
        "duration_s": duration,
        "artifacts": copied,
        "stale_artifacts_ignored": stale,
        "produced_element_map": "element-map.json" in copied,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (dest / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, help="run only the first N of the plan")
    parser.add_argument("--only", help="restrict to one page name")
    args = parser.parse_args()

    schedule = _expand(PLAN)
    if args.only:
        schedule = [s for s in schedule if s[0] == args.only]
    if args.limit:
        schedule = schedule[: args.limit]

    done = _completed_ids()
    pending = [(i, p, path) for i, (p, path) in enumerate(schedule, 1) if f"{i:03d}-{p}" not in done]

    print(f"model={MODEL}  target={TARGET_BASE_URL}  traces={TRACES_DIR}")
    print(f"{len(schedule)} planned, {len(schedule) - len(pending)} already collected, {len(pending)} to run")
    for i, page, path in pending:
        print(f"  {i:03d}  {page:<10} {path}")
    if args.dry_run or not pending:
        return

    ok = 0
    for i, page, path in pending:
        print(f"\n--- run {i:03d} {page} ---", flush=True)
        meta = run_one(i, page, path)
        status = "ok" if meta["produced_element_map"] else f"NO MAP (exit {meta['exit_code']})"
        print(f"--- run {i:03d} {page}: {status} in {meta['duration_s']}s", flush=True)
        ok += bool(meta["produced_element_map"])

    print(f"\n{ok}/{len(pending)} runs produced an element-map. Traces in {TRACES_DIR}")
    print("Re-run this command to retry anything missing; completed runs are skipped.")


if __name__ == "__main__":
    main()
