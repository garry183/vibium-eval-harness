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

# Model choice per agent role. A judge must be at least as capable as what it
# judges -- a cheaper-tier grader scoring Sonnet output is a capability
# inversion, not a cost optimization (self-grading-bias research says
# same-family judges are fine; a *weaker* judge is the actual risk). Override
# any of these via env if needed.
MODELS = {
    "explorer": os.environ.get("VIBE_CHECK_MODEL_EXPLORER", "claude-sonnet-5"),
    "writer": os.environ.get("VIBE_CHECK_MODEL_WRITER", "claude-sonnet-5"),
    "runner": os.environ.get("VIBE_CHECK_MODEL_RUNNER", "claude-sonnet-5"),
    "grader": os.environ.get("VIBE_CHECK_MODEL_GRADER", "claude-sonnet-5"),
}

EXPLORE_GRADE_GATE = "B"  # writer refuses to run below this band

# Out of 35 (7 LLM-judged dimensions x 5), not 40 -- schema_compliance was
# removed from the LLM rubric and is now a deterministic jsonschema check
# (see agents/shared/schemas.py) run as a hard gate instead of a judged score.
# Bands keep the same percentage cutoffs as the original 0-40 scale.
EXPLORE_GRADE_BANDS = {
    "A": (32, 35),
    "B": (26, 31),
    "C": (18, 25),
    "D": (11, 17),
    "F": (0, 10),
}


def band_for_score(score: int) -> str:
    return next((b for b, (lo, hi) in EXPLORE_GRADE_BANDS.items() if lo <= score <= hi), "F")


def band_meets_gate(band: str) -> bool:
    order = list(EXPLORE_GRADE_BANDS)
    return band in order and order.index(band) <= order.index(EXPLORE_GRADE_GATE)


def explorer_output_dir(page: str) -> Path:
    d = OUTPUT_DIR / page
    d.mkdir(parents=True, exist_ok=True)
    return d
