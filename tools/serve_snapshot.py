"""Serves a frozen snapshot over local HTTP.

Unit 1 plumbing. Why a server and not `file://`: relative asset paths, CORS,
and CDP all behave differently on the file scheme, so a `file://` replay is not
the same document the explorer saw over HTTP. Serving the snapshot root over
127.0.0.1 keeps the load path identical -- same relative URLs, same origin
semantics -- with only the host swapped.

Port 0 means the OS picks a free port, so parallel eval runs never collide.

Use as a context manager, which is how the harness will consume it:

    from tools.serve_snapshot import serve_snapshot
    with serve_snapshot("login") as base_url:
        ...  # base_url is e.g. http://127.0.0.1:53411

Or standalone, to poke at the frozen page by hand:

    python -m tools.serve_snapshot --sample login
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator

from agents.shared.config import ROOT

DATASET = ROOT / "evals" / "dataset"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D102 - stdout is the trace stream
        pass


def snapshot_dir(sample: str) -> Path:
    d = DATASET / sample / "snapshot"
    if not (d / "index.html").exists():
        raise SystemExit(
            f"no snapshot for sample '{sample}' at {d}\n"
            f"capture one first:  python -m tools.snapshot_page --sample {sample}"
        )
    return d


@contextlib.contextmanager
def serve_snapshot(sample: str, port: int = 0) -> Iterator[str]:
    root = snapshot_dir(sample)
    handler = functools.partial(_QuietHandler, directory=str(root))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", default="login")
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()
    with serve_snapshot(a.sample, a.port) as base_url:
        print(f"[serve] {a.sample} snapshot at {base_url}  (ctrl-c to stop)")
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            print("\n[serve] stopped")


if __name__ == "__main__":
    main()
