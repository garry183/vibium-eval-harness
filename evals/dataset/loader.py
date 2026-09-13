"""Hands out one (input, target) pair per sample. Nothing else.

Unit 1. This is the piece that makes the repo scoreable: until now `evals/`
held rubrics -- instructions for judging style -- and a rubric cannot tell you
that `text=Login` matches zero elements. A *target* can, because it is a
hand-authored answer key.

The loader is deliberately dumb. It does not run the explorer, it does not
score, it does not validate locators. It opens the answer key and yields it.
Everything that judges lives downstream, so that a bug in scoring can never be
confused with a bug in loading.

Shape choices, and why:

  * A `Sample` dataclass, not a dict. `s.targt` raises AttributeError;
    `s["targt"]` raises KeyError but `s.get("targt")` returns None and the bug
    surfaces three units later as a mysterious zero. This object is threaded
    through every unit to 7 -- worth the strictness.

  * `path`, not a full URL. The explorer builds its URL as
    `TARGET_BASE_URL + path` (agents/explorer/explorer_agent.py:69), and the
    whole point of Unit 1's freeze is that the base swaps between the live site
    and a local snapshot server. Storing a baked-in URL would hard-code the very
    thing that has to vary. `sample.url(base)` composes it.

  * A generator, not a list. At one sample this is irrelevant. At fifty it
    matters, and changing the signature later means changing every caller --
    so it costs nothing to be right now.

Usage:
    from evals.dataset.loader import load_samples, load_sample

    for sample in load_samples():
        with sample.frozen() as url:
            ...  # run the explorer against url, score against sample.target
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

from agents.shared.config import ROOT

DATASET_DIR = ROOT / "evals" / "dataset"
TARGET_SCHEMA = "target-v1"


@dataclass(frozen=True)
class Sample:
    """One eval sample: an input the explorer can run, and the answer key for it."""

    sample_id: str
    path: str
    target: dict
    dir: Path

    @property
    def elements(self) -> list[dict]:
        return self.target["elements"]

    @property
    def has_snapshot(self) -> bool:
        return (self.dir / "snapshot" / "index.html").exists()

    def url(self, base_url: str) -> str:
        return base_url.rstrip("/") + self.path

    @contextlib.contextmanager
    def frozen(self) -> Iterator[str]:
        """Serve this sample's snapshot and yield the URL to explore."""
        from tools.serve_snapshot import serve_snapshot

        with serve_snapshot(self.sample_id) as base:
            yield self.url(base)


def _path_for(target: dict) -> str:
    """Recover the path from the target's recorded source URL."""
    from urllib.parse import urlparse

    return urlparse(target["url"]).path or "/"


def load_sample(sample_id: str) -> Sample:
    d = DATASET_DIR / sample_id
    f = d / "target.json"
    if not f.exists():
        raise FileNotFoundError(f"no target for sample '{sample_id}' at {f}")
    target = json.loads(f.read_text(encoding="utf-8"))

    # Fail loudly on a schema the scorers were not written against. A target is
    # the one file in the harness that must never be silently misread -- a
    # wrong answer key produces confident, wrong numbers.
    if target.get("schema") != TARGET_SCHEMA:
        raise ValueError(f"{f}: expected schema {TARGET_SCHEMA!r}, got {target.get('schema')!r}")
    if not target.get("elements"):
        raise ValueError(f"{f}: target has no elements")

    return Sample(sample_id=sample_id, path=_path_for(target), target=target, dir=d)


def load_samples() -> Iterator[Sample]:
    """Yield every sample in evals/dataset/, sorted by id for stable run order."""
    for d in sorted(p for p in DATASET_DIR.iterdir() if p.is_dir() and (p / "target.json").exists()):
        yield load_sample(d.name)
