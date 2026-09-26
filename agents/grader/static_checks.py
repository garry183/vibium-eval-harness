"""Deterministic writer-output checks that don't need an LLM's judgment --
TODO markers, forbidden time.sleep() calls, hardcoded URL literals, and
missing layers are grep-shaped questions, not "does this satisfy the
expectation" judgment calls. These run before the writer-grader LLM call and
their findings are merged into critical_failures unconditionally, so a
regression here fails the gate even if the LLM happens to miss it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_TODO_RE = re.compile(r"\b(TODO|FIXME)\b")
_SLEEP_RE = re.compile(r"\btime\.sleep\s*\(")
_HARDCODED_URL_RE = re.compile(r"""["'](https?://[^"']+)["']""")


def css_only_properties(source: str) -> list[str]:
    """Page Object properties whose locator is raw CSS/XPath with no get_by_*
    anywhere in the chain. A CSS fallback chained via .or_() is fine; CSS as
    the only strategy is a non-semantic primary. The LLM grader once passed
    exactly this on the strength of a gap_note, so it's checked here instead.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    offenders = []
    for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
        for fn in cls.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            if not any(isinstance(d, ast.Name) and d.id == "property" for d in fn.decorator_list):
                continue
            calls = {
                n.func.attr for n in ast.walk(fn)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            }
            if "locator" in calls and not any(c.startswith("get_by_") for c in calls):
                offenders.append(fn.name)
    return offenders


def check_writer_files(suite: str, layer_files: dict[str, list[Path]]) -> list[str]:
    """layer_files: {layer_name: [Path, ...]} e.g. {"page": [...], "spec": [...]}.
    Returns critical-failure strings; empty list means clean.
    """
    failures: list[str] = []

    for layer, paths in layer_files.items():
        if not paths:
            failures.append(f"missing layer: no {layer} file found for suite '{suite}'")

    for paths in layer_files.values():
        for path in paths:
            content = path.read_text()
            rel = path.as_posix()
            if _TODO_RE.search(content):
                failures.append(f"{rel}: contains TODO/FIXME marker")
            if _SLEEP_RE.search(content):
                failures.append(f"{rel}: contains time.sleep() -- forbidden, use explicit waits")
            url_match = _HARDCODED_URL_RE.search(content)
            if url_match:
                failures.append(
                    f"{rel}: hardcoded URL literal '{url_match.group(1)}' -- "
                    f"import TARGET_BASE_URL from agents.shared.config instead"
                )

    for path in layer_files.get("page", []):
        for name in css_only_properties(path.read_text()):
            failures.append(
                f"{path.as_posix()}: property '{name}' uses only a CSS/XPath locator -- "
                f"primary must be semantic (get_by_*), CSS only as an .or_() fallback"
            )

    return failures
