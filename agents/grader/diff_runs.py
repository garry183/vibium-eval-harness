"""Compares the two most recent recorded grading runs for a (mode, target)
pair and reports score/gate/critical-failure flips. This is the regression
half of the eval harness -- a lone grading run can't tell you whether a
change made things better or worse, only what today's score is.

Usage: python -m agents.grader.diff_runs --mode explore --target login
"""

from __future__ import annotations

import argparse

from agents.grader.run_log import load_runs


def diff(mode: str, target: str) -> str:
    runs = load_runs(mode, target)
    if len(runs) < 2:
        return f"[{mode}/{target}] fewer than 2 recorded runs -- nothing to diff yet."

    prev, latest = runs[-2], runs[-1]
    lines = [f"[{mode}/{target}] {prev['run_id']} -> {latest['run_id']}"]

    if mode == "explore":
        if prev["band"] != latest["band"]:
            lines.append(f"  band: {prev['band']} -> {latest['band']} (score {prev['score']} -> {latest['score']})")
        else:
            lines.append(f"  band unchanged: {latest['band']} (score {prev['score']} -> {latest['score']})")
    else:
        if prev["pass_rate"] != latest["pass_rate"]:
            lines.append(f"  pass_rate: {prev['pass_rate']} -> {latest['pass_rate']}")
        else:
            lines.append(f"  pass_rate unchanged: {latest['pass_rate']}")

    if prev["gate_passed"] != latest["gate_passed"]:
        lines.append(f"  GATE FLIP: {prev['gate_passed']} -> {latest['gate_passed']}")

    prev_crit = set(prev.get("critical_failures", []))
    latest_crit = set(latest.get("critical_failures", []))
    new_crit = latest_crit - prev_crit
    fixed_crit = prev_crit - latest_crit
    if new_crit:
        lines.append(f"  NEW critical failures: {sorted(new_crit)}")
    if fixed_crit:
        lines.append(f"  resolved critical failures: {sorted(fixed_crit)}")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["explore", "writer"], required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    print(diff(args.mode, args.target))


if __name__ == "__main__":
    main()
