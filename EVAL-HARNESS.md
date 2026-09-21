# Eval harness — status and plan

Start here for anything eval-related. This file is the map; it holds no
material of its own.

| Document | What it is |
|---|---|
| `COURSE.md` | The plan. 8 units + an interlude, each with a concept, a build, and a numeric exit criterion. |
| `LEARNING.md` | The lab notebook. What got built, who wrote it, and the closed-book explanations. |
| `DEFECT-LOG.md` | Unit 0's output. 29 observations from 8 real explorer runs, clustered and counted. Everything downstream is scaffolding on this. |

**System under test:** `agents/explorer/`. Nothing else in the repo is in scope
until Unit 7.

---

## Why this exists

`evals/explore-golden.json` holds a rubric: seven LLM-judged dimensions that
grade whether a locator *looks* well chosen. A rubric cannot tell you that
`text=Login` matches zero elements on the page, because it never looks at the
page. Until Unit 1, nothing in this repo could be scored for **accuracy** — only
for style, by a judge that was never itself validated.

The harness fixes that in a specific order: hand-authored answer keys first,
then delete every judged check that a code check can do, then ground truth from
the page itself, then rebuild the judge properly on whatever survives.

---

## Where we are

| Unit | State | Artifact |
|---|---|---|
| 0 — Error analysis | **Closed** 2026-09-11 | `DEFECT-LOG.md` |
| 1 — Dataset + frozen environment | **Closed** 2026-09-11 | `evals/dataset/`, `tools/snapshot_page.py`, `tools/serve_snapshot.py`, `tools/check_drift.py` |
| 2 — Deterministic scorers | **build done** 2026-09-15, explanation owed | `agents/grader/explore_scorers.py`, `tests/unit/test_explore_scorers.py` |
| 3 — State-based scorer | not started | |
| 4 — The harness proper | not started | |
| Interlude — Dataset expansion | not started, **blocks 5 and 7** | |
| 5 — LLM judge, done right | not started | |
| 6 — Trajectory evaluation | not started | |
| 7 — Regression + criterion validity | not started | |

Both units are closed on their **artifacts** — each numeric exit criterion is
met. Both closed-book explanations were **waived on 2026-09-11** rather than
written, so neither unit has a retention check behind it; the waiver and its
consequence are recorded in `LEARNING.md`. The snapshot tooling and loader are
Claude's code that has never been explained back — borrowed, not owned.

---

## What Unit 0 found

8 login traces, 29 observations, 11 clusters. Ranked by count × consequence:

1. **12 of 12** runs never reached inventory or cart. The explorer has no
   fill/type tool, so everything behind the login gate is unreachable — and 12
   runs mapped the login form and filed it under the wrong page name. The
   current rubric has no "did you get there" dimension, so this was invisible.
2. **18 of 20** fabricated `crawled_at` (exactly midnight). The system prompt
   asks for "a timestamp you compute from context" and there is no clock in the
   toolkit. Fix the prompt, not the model.
3. **Tool timeouts recorded as factual zero-matches.** `vibium_tools.py:98` —
   `find_all` raises `TimeoutError` on no-match and never returns empty, so the
   `count: 0` branch is dead code. Every zero-match probe reaches the agent as
   an exception and gets written down as an observation about the page. "The
   query timed out" and "the element does not exist" are different statements.
   Each such probe also blocks for 30s, which is most of the 250–690s run times.
4. **47 distinct `or_chain` formats across 20 traces**, no two alike. Not model
   error — there is no spec, so every run invents one.
5. **`testability_gap` split 4 true / 4 false** on the same element on the same
   page. The term is nowhere defined.
6. 7 of 20 traces fail schema validation, all from `count: null` on CSS
   strategies that were asserted rather than executed.

Two behaviours worth protecting as regressions: one run correctly refused to
fabricate a map when blocked, and all 8 correctly ruled out `text=` on an
`<input type=submit>`. Any scorer built next must score these as *good*, or it
is untested in the passing direction.

---

## What Unit 1 built

**The answer key.** `evals/dataset/login/target.json` — hand-authored by Gaurav
from the live DOM, never derived from an element-map. Three elements, each
locator sorted into `correct_primary` / `acceptable_fallback` / `wrong`, with a
reason recorded for every "wrong". Two facts settled by direct probing:
`role=textbox` resolves to **2** in vibium because it matches
`input[type=password]` (Playwright's `getByRole` does not) — so a locator graded
correct here is not automatically correct in the generated Playwright suite. And
`class="input_error"` is present in the clean page state despite its name.

**The frozen environment.** SauceDemo's login page is a 1.3 KB `index.html` plus
a 527 KB JS bundle — the form does not exist in the served HTML, JavaScript
builds it. A naive HTML-only snapshot would have frozen a blank page and scored
every future run at zero for a reason having nothing to do with the explorer.
The capture saves raw HTTP response bodies at their original paths instead, so
the replay is the real load. Google Fonts and a Backtrace telemetry endpoint are
cross-origin and not saved; the script warns rather than claiming completeness.

**The cost of freezing, paid explicitly.** A snapshot buys reproducibility by
giving up contact with reality, so `tools/check_drift.py` compares all three
parties — target, snapshot, live — on the attributes that change what a locator
resolves to. Last run 2026-09-08: no drift.

### Running it

```bash
python -m tools.snapshot_page --sample login   # re-capture the frozen page
python -m tools.serve_snapshot --sample login  # serve it at :8899 to poke by hand
python -m tools.check_drift --sample login     # target vs snapshot vs live
python -m pytest tests/unit/test_dataset_loader.py
```

```python
from evals.dataset.loader import load_samples

for sample in load_samples():
    with sample.frozen() as url:      # serves the snapshot, yields a local URL
        ...                           # run the explorer, score against sample.target
```

`Sample` is a frozen dataclass (`sample_id`, `path`, `target`, `dir`). It stores
a *path*, not a URL, because the base swaps between the live site and the local
snapshot server — that swap is the entire point of the unit.

### Authorship

`target.json` is Gaurav's, hand-verified. The snapshot tooling and the loader
were written by Claude at his request after the mechanism was explained; this is
recorded in `LEARNING.md` so it is not mistaken later for his own work. Both
still need a closed-book explanation before Unit 1 is signed off.

### Verified end to end

Vibium — the engine the explorer actually drives, not just Playwright — was run
against the frozen URL on 2026-09-09:

| Probe | Frozen page | `target.json` says |
|---|---|---|
| `placeholder=Username` | count=1 | `correct_primary` |
| `role=textbox` | count=2 | `wrong` — "count=2, vibium matches both inputs" |

The `role=textbox` = 2 result is the behaviour that distinguishes vibium from
Playwright, and it reproduces on the local copy. A broken replay would not have
preserved an engine-specific quirk, so this is the strongest available evidence
that the snapshot is faithful at the layer the eval measures.

Note for anyone re-running probes by hand: only probe locators expected to
*match*. A no-match blocks for 30s (`vibium_tools.py:98`, cluster B in
`DEFECT-LOG.md`), and four of them in one script was enough for the OS to kill
the process for memory pressure on the first attempt.

---

## What Unit 2 built

Five of the seven judged dimensions are now code. The rubric was converted, not
deleted — 7 dimensions, 0-5 each, out of 35, bands and the band >= B gate
unchanged. Only the answerer moved.

| Dimension | Answered by |
|---|---|
| `semantic_primary_rate` | code |
| `coverage_completeness` | code — set membership against Unit 1's `target.json` |
| `strategy_validation` | code — internal coherence only; live re-resolution is Unit 3 |
| `dynamic_content_flagging` | code |
| `multi_strategy_coverage` | code — presence, not format (no `or_chain` spec exists yet) |
| `context_narrative_quality` | LLM — an opinion about writing |
| `interaction_contract_quality` | LLM **under protest** — `ElementRecord` has no field for it |

The grader's structured-output schema now accepts only the two judged scores, so
the LLM cannot answer a question that isn't its to answer. Grading files carry
`scored_by` and `scorer_notes`, so every number is traceable to its answerer.

**Unit 0 cluster B is now enforced, not just documented.** `count: 0` is never
read as a measurement — `vibium_tools.py:98` raises on no-match and never
returns empty, so every zero in every element-map was inferred from an exception.
`count: null` is treated as an assertion that was never executed.

Scored against the existing login trace: **19/25 from code**, three critical
failures — all three `data-test` fallbacks carry confidence 3 on a count that was
never run. `multi_strategy_coverage` 2/5, because two of three `or_chain`s name a
fallback nobody executed. That trace was band B under the old rubric.

**Owed:** the closed-book explanation (Gaurav), and two explorer fixes this unit
only detects rather than repairs — make `find_all` return 0 on no-match, and stop
the explorer writing `count: null`.

### Running it

```bash
python -m pytest tests/unit/test_explore_scorers.py
```

---

## What's planned

**Unit 2 — Deterministic scorers.** Every check moved out of the LLM judge has
zero variance, zero cost, and zero calibration debt. Replace the judged
dimensions that never needed judgment. *Exit:* at least 5 of 7 dimensions are
code, with a written defence of each survivor.

**Unit 3 — The state-based scorer.** Agents change a world, so grade the world,
not the prose. Resolve every locator in an element-map against the frozen page
and assert `count == 1` on the labelled target. This is the number that actually
means something, and it subsumes most of the rubric. *Exit:* a real per-element
accuracy figure.

**Unit 4 — The harness proper.** Dataset × solver × scorer, run k times,
aggregated with uncertainty. `pass^k`, not `pass@1` — a 90% pass@1 agent is 57%
reliable at k=8. *Exit:* pass^k and mean ± stdev for the dataset.

**Interlude — Dataset expansion.** *Added after an audit found Units 5 and 7 were
not completable on a one-page dataset.* Unit 5 needs ~100 labelled examples and a
held-out split; login gives 24 judgments and no split. Unit 7 asks for a
*correlation*, which does not exist at n=1. Fix: give the explorer a fill/type
tool — the #1 defect from Unit 0 — then add inventory, cart and checkout targets.
The 8 existing login traces become the pre-change baseline Unit 7 needs.
*Exit:* at least 4 samples, at least 100 labelled judgments, every page reachable.

**Unit 5 — The LLM judge, done right.** Binary, not Likert. Validate with TPR and
TNR *separately* — overall agreement is a vanity metric, since a judge that always
says "pass" scores 90% on a 90%-pass dataset. *Exit:* TPR and TNR both at least
0.9 on held-out.

**Unit 6 — Trajectory evaluation.** A correct answer reached in 20 steps with two
bad tool calls is a failing trajectory that final-answer scoring marks green.
*Exit:* trajectory metrics plus at least one good-output / bad-trajectory case
from the real traces.

**Unit 7 — Regression and criterion validity.** Two questions the harness exists
to answer: did my change move the number *beyond noise* (`diff_runs.py` currently
cannot tell a regression from variance — it has no noise floor), and does the
`band >= B` gate predict the thing it claims to protect? That claim is falsifiable
and has never been tested. *Exit:* a data-backed yes/no.

**Capstone.** Write it up publicly.

---

## Known limitations

- **One sample.** 8 outputs against 1 input measures *consistency*, not
  *generalisation*. Do not quote an absolute accuracy number off this dataset.
  The Interlude is what changes that.
- **Frozen is not current.** The eval measures the explorer against the page as
  of 2026-09-08. `check_drift.py` is the tripwire; the refresh procedure is in
  its docstring, and it requires re-verifying `target.json` by hand — never
  patching it from a diff, and never from an element-map.
- **Engine mismatch.** Locators are graded against vibium's matching semantics.
  The generated Playwright suite resolves some of them differently.
- **Two units, zero predictions.** Gate 1 (predict before seeing) was removed on
  2026-09-08 after producing only blanks. Prediction-vs-reality, the course's
  original measurement, has no data points; the closed-book explanations are now
  the only retention check, which is why they are not optional.
