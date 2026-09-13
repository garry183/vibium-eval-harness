"""Persists one JSON record per grading run under evals/runs/, so scores can
be diffed across runs instead of only ever being compared against nothing.
A single grading run tells you today's score; without a history, you can't
tell a prompt regression from normal LLM variance. See diff_runs.py.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from agents.shared.config import EVALS_DIR

RUNS_DIR = EVALS_DIR / "runs"


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"


def record_run(mode: str, result: dict) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sha = _git_sha()
    record = {"run_id": f"{ts}-{sha}", "git_sha": sha, "timestamp": ts, **result}
    out_dir = RUNS_DIR / mode
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result['target']}-{ts}-{sha}.json"
    path.write_text(json.dumps(record, indent=2))
    return path


def load_runs(mode: str, target: str) -> list[dict]:
    d = RUNS_DIR / mode
    if not d.exists():
        return []
    runs = [json.loads(f.read_text()) for f in d.glob(f"{target}-*.json")]
    return sorted(runs, key=lambda r: r["timestamp"])
