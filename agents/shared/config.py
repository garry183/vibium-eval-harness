"""Central config for all agents. No agent reads os.environ directly."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Windows consoles default to a legacy codepage (cp1252) that can't encode
# characters Claude's output routinely contains (em-dashes, "≠", etc.) --
# without this, printing a live message stream crashes mid-run. Every agent
# imports this module first, so reconfiguring here covers all of them.
for _stream in (sys.stdout, sys.stderr):
    if _stream.encoding and _stream.encoding.lower() != "utf-8":
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]

TARGET_BASE_URL = os.environ.get("TARGET_BASE_URL", "https://www.saucedemo.com")
VIBIUM_HEADLESS = os.environ.get("VIBIUM_HEADLESS", "false").lower() == "true"

OUTPUT_DIR = ROOT / "output" / "explorer"
EVALS_DIR = ROOT / "evals"
TESTS_DIR = ROOT / "tests"

# Model choice per agent role. Explorer/writer/runner need real reasoning over
# ambiguous live-page state; grader is closer to deterministic rubric-checking,
# so it defaults to a cheaper tier. Override any of these via env if needed.
MODELS = {
    "explorer": os.environ.get("VIBE_CHECK_MODEL_EXPLORER", "claude-sonnet-5"),
    "writer": os.environ.get("VIBE_CHECK_MODEL_WRITER", "claude-sonnet-5"),
    "runner": os.environ.get("VIBE_CHECK_MODEL_RUNNER", "claude-sonnet-5"),
    "grader": os.environ.get("VIBE_CHECK_MODEL_GRADER", "claude-haiku-4-5-20251001"),
}

EXPLORE_GRADE_GATE = "B"  # writer refuses to run below this band
EXPLORE_GRADE_BANDS = {
    "A": (37, 40),
    "B": (30, 36),
    "C": (21, 29),
    "D": (12, 20),
    "F": (0, 11),
}


def explorer_output_dir(page: str) -> Path:
    d = OUTPUT_DIR / page
    d.mkdir(parents=True, exist_ok=True)
    return d
