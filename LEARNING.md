# Learning Log

Lab notebook for the course in `COURSE.md`. Written by Gaurav, not by Claude.

**Restructured 2026-09-08.** Predictions were dropped (see COURSE.md, Protocol).
Two sections per unit now: what got built, and a closed-book explanation. The
explanation is the only retention check left, so it is not optional — write it
with the code closed. If you can't, the unit isn't done.

Where Claude supplied reasoning that should have been yours, it is labelled as
such. Don't let it blur later.

---

## Unit 0 — Error analysis

### What I built

`DEFECT-LOG.md`. The process was open coding (write down every defect in your own
words, no categories yet) then axial coding (cluster the notes into named failure
modes) then counting. 29 observations from the 8 login traces, 11 clusters.

Provenance, because it changes how much the taxonomy is worth: traces 001 and 004
were reviewed by hand — Gaurav verified the live DOM himself and traced 001's tool
calls. The other 5 were machine-assisted via `tools/compare_runs.py` on structured
fields, plus a full read of all 8 `context.md` files. So the **counts** are solid;
the **completeness of the category list** is less certain than a full hand review
would give.

Scope was narrowed to login mid-unit. The first 20 runs covered login, inventory
and cart; 12 of them never reached their page, so only the 8 login traces are
measuring anything. The other 12 are kept as evidence for that finding.

### Failure taxonomy

| Cluster | Failure mode | Count | Example |
|---|---|---|---|
| J | Never reached the target page | **12 of 12** inventory+cart | 015 mapped the login form, filed it as `"page": "cart"` |
| G | `crawled_at` fabricated (exactly midnight) | **18 of 20** | 004 |
| G | `viewport` = the string `"unknown"` | 7 of 20 | 004 |
| H | Distinct `or_chain` formats | **47 across 20**, no two alike | all |
| H | `confidence` for identical evidence (`count=1`) | 3 distinct values (3, 4, 5) | all |
| F | `testability_gap` on loginButton | **4 true / 4 false** | 001/007/010/019 vs 004/013/016/020 |
| F | Severity for the button-name finding | HIGH ×1, MEDIUM ×2, LOW ×5 | 019 vs 013 |
| E | `accessibility_node.name` for loginButton | `"Login"` ×6, `null` ×1, `""` ×1 | 001, 019 |
| C | Traces failing `validate_explorer_output` | 7 of 20, all `count: null` | 001, 019, 020 |
| B | Timeout recorded as a zero-match | 3 traces say so in prose | 010, 020 |
| A | Assertions from training recall, never probed | 4 observations | 016/020 "the logo is a CSS background image" |
| I | Strategies tried on the same element | range 2–5 | 001 (4) vs 004 (2) |
| K | **Correct behaviour to protect** | 2 | 011 refused to fabricate when blocked; 8/8 ruled out `text=` on `<input type=submit>` |

### What actually happened — the three that matter

**1. The biggest failure was invisible to the rubric.** 12 of 12 runs never
reached inventory or cart, because the explorer has no fill/type tool and both
pages are behind the login gate. Every one of those runs mapped the login form
instead and filed it under the wrong page name. None of the 7 rubric dimensions
asks "did you get to the page you were asked to map", so the grader would have
scored these runs on locator quality and never mentioned that they described the
wrong page. `EXP-002-*` and `EXP-003-*` in `explore-golden.json` can never pass.

**2. A tool bug was being laundered into claims about the page.**
`vibium_tools.py:98` — `find_all` raises `TimeoutError` on no-match and never
returns empty, so the `count: 0` branch is dead code. Every zero-match probe
reaches the agent as an exception, and the agent writes it down as `count: 0`.
"The query timed out" and "the element does not exist" are different statements,
and the difference propagates into every downstream locator decision. Same bug
costs 30s per failed probe, which at 4–6 probes a run is most of the 250–690s
run times.

**3. Two of the top failure modes are spec absence, not model error.**
`crawled_at` is fabricated by design: the system prompt asks for "a timestamp you
compute from context" and there is no clock in the toolkit. 47 `or_chain` formats
across 20 traces because no format was ever specified. `testability_gap` splits
4/4 on the same element because the term is defined nowhere. Fix the prompt and
the spec, not the model.

### What surprised me

The praise needed verifying as hard as the criticism. Cluster K started at 3
entries. On review, 007's reasoning that the button's visible text was
"CSS-uppercased LOGIN from `value=\"Login\"`" turned out to be fabricated — the
screenshot shows mixed-case "Login" and there is no uppercasing. So cluster A
gained a row and the one genuinely-good-judgment example was lost. K is down to 2.

Second surprise: the runs largely agreed with each other while being wrong
together. `tools/compare_runs.py` can only surface disagreement, so anything all
8 runs got wrong in the same way looks perfectly consistent. That is the blind
spot that makes a hand-authored target (Unit 1) necessary rather than optional —
you cannot find a shared error by comparing the outputs to each other.

### Gate 1 note

No predictions were written before the traces were read, so there is no
prediction-vs-reality measurement for this unit. Gate 1 was subsequently removed
from the course (2026-09-08) for producing only blanks.

### Closed-book explanation

> Why does a rubric written before error analysis usually contain dead checks?

**Waived 2026-09-11 on Gaurav's instruction.** Not written, and deliberately not
ghostwritten by Claude — a Claude-authored answer here would measure nothing and
would read later as if it were Gaurav's. Unit 0 is therefore closed on its
artifact (`DEFECT-LOG.md`, exit criterion met) with the retention check
outstanding, not satisfied.

Still open, if it's ever picked back up. The material is all in the taxonomy
above: the 7 rubric dimensions all grade locator quality, while the top three
real failures were unreachable pages, fabricated fields, and tool errors recorded
as page facts.

---

## Unit 1 — Dataset and the frozen environment

### What I built

`evals/dataset/login/target.json` — hand-authored from the live SauceDemo DOM,
3 elements, every locator sorted into correct_primary / acceptable_fallback /
wrong with a reason for each "wrong". Two open questions resolved by direct
probing: `role=textbox` is count=2 in vibium (it matches password inputs, unlike
Playwright), and `.input_error` is present in the clean state despite its name.

**Snapshot and loader — built by Claude, not by Gaurav.** Requested explicitly
after the mechanism was explained. Recorded here so authorship stays honest;
these are the files to be able to explain closed-book before Unit 1 is signed off.

| File | What it does |
|---|---|
| `tools/snapshot_page.py` | Saves the raw HTTP response bodies at their original paths. Not `page.content()` — that is the post-JS DOM and would replay a different document. |
| `tools/serve_snapshot.py` | Serves the snapshot over `127.0.0.1` on an OS-assigned port. Not `file://`: relative paths, CORS and CDP all behave differently there. |
| `tools/check_drift.py` | Compares target vs snapshot vs live on the attributes that change what a locator resolves to. This is the price of freezing. |
| `evals/dataset/loader.py` | `Sample` dataclass + `load_samples()` generator. |
| `tests/unit/test_dataset_loader.py` | 9 tests; the ones that matter refuse a wrong `schema` and an empty `elements`. |

What the capture found: SauceDemo's login page is a 1.3 KB `index.html` plus a
527 KB JS bundle — the form is rendered by JavaScript, so a naive HTML-only
snapshot would have frozen an empty page. Google Fonts and a Backtrace telemetry
endpoint are cross-origin and were not saved; fonts are cosmetic and telemetry
fails silently, so neither affects the DOM. The script warns about them rather
than pretending the snapshot is complete.

Drift check result 2026-09-08: all 3 elements match on both the snapshot and the
live site. The frozen copy is a faithful stand-in as of today.

Vibium probe 2026-09-09 (Playwright agreeing is not enough — vibium is the engine
the explorer drives, and the two already disagree): against the frozen URL,
`placeholder=Username` -> count=1 and `role=textbox` -> count=2, exactly what
`target.json` records. The engine-specific quirk survives the replay, which a
broken snapshot would not have preserved.

**Decisions taken** — Claude recommended, Gaurav accepted:

1. *Envelope shape:* a `Sample` dataclass (`sample_id`, `url`, `target`).
   Attribute access fails loudly on a typo; a dict returns `None` silently.
2. *Frozen, not live:* snapshot the page to `evals/dataset/login/snapshot/`,
   serve over local HTTP. A failing run is then always the explorer's fault, never
   SauceDemo's. Cost: the eval stops tracking reality, so a drift check and a
   refresh procedure are part of the build.

### Record of the gap — where Claude did the thinking

**Not a real prediction. Written by Claude at Gaurav's instruction, after the
mechanism had already been explained.** Recorded here as an honest account of the
gap, not as a measurement. Gate 1 is NOT satisfied for this unit.

What was actually answered from memory, before any explanation:

| Q | Gaurav's answer | Verdict |
|---|---|---|
| What does the explorer need to start? | "URL" | correct |
| What does the scorer need to judge a locator? | "no idea" | blank |
| Write the envelope as a Python shape | "no idea" | blank |
| Why yield, not return a list? | "no idea" | blank |
| What has to be on disk to freeze the page? | "no idea" | blank |
| Two ways it could be wrong | "no idea" | blank |

**The gap, stated plainly:** at the start of Unit 1 the input side of scoring was
clear (the explorer takes a URL) and the *output* side was not — there was no
mental model of what a scorer consumes. That is the thing to re-test in Unit 3,
where the same question comes back as "what do I compare a locator against?".

Unit 0's prediction section is also empty. Two units in, prediction-vs-reality
has produced zero data points. Mitigation agreed for Unit 2 onward: predictions
become multiple-choice — Claude poses the question with three plausible answers,
Gaurav picks one and says why, before any explanation. A wrong pick is a data
point; a blank is not.

### What Claude supplied

Recorded so the reasoning is not mistaken for Gaurav's own later:

- The scorer's input is the target entry. Run 010 recorded loginButton's primary
  as `role=button,text=Login`. Nothing in the run says whether that is right. You
  find out by opening `target.json`, looking up `loginButton`, and finding that
  locator in the `wrong` list. That lookup *is* the scoring operation.
- One envelope = what the explorer needs (URL) + what the scorer needs (the
  target). That is the `(input, target)` pair the course asks for.
- `yield` over `return [...]`: a list builds all samples before the caller sees
  the first one, and changing the signature later means changing every caller.
  Irrelevant at 1 sample, not at 50.
- Both design decisions (dataclass, frozen) were Claude's recommendations,
  accepted without argument rather than chosen. Worth re-testing in Unit 3: if
  the reasons for each are not reproducible from memory then, they were never
  learned.

### Closed-book explanation

> What does "target" mean, and why can a rubric not serve as one?

**Waived 2026-09-11 on Gaurav's instruction**, same reasoning as Unit 0 — see
that section. Unit 1 is closed on its artifacts (`target.json`, the snapshot
tooling, the loader; exit criterion met, drift-checked and vibium-verified) with
the retention check outstanding.

Consequence to remember: the snapshot tooling and loader were written by Claude
(see the authorship table above) and have now never been explained back by
Gaurav. Treat them as borrowed, not owned. Unit 3 asks "what do I compare a
locator against?", which is this same question again — that is the next natural
place to find out whether any of it stuck.

---

## Unit 2 — Deterministic scorers

### What I built

`agents/grader/explore_scorers.py` — five code scorers, one per converted
dimension, plus `tests/unit/test_explore_scorers.py` (28 cases, each dimension
tested clean *and* dirty). `grading_tools.py` now splits `CODE_DIMENSIONS` from
`JUDGED_DIMENSIONS`; the grader's structured-output schema accepts only the two
judged scores and rejects the rest, so the LLM cannot answer a question that is
no longer its to answer. `grader_agent.py` computes the five, merges them with
the LLM's two, and records `scored_by` and `scorer_notes` in the grading file so
any number can be traced to its answerer.

The rubric was **converted, not deleted** — still 7 dimensions, still 0–5 each,
still out of 35, so `EXPLORE_GRADE_BANDS` and the band ≥ B gate are unchanged.
Only the answerer moved. Same move as `schema_compliance`, which is the
precedent this unit generalises.

**Authorship: the scorer code, the tests and the justification table below were
written by Claude, on request, after Gaurav produced the code/judge sort and had
it corrected.** Gaurav's own contribution to this unit is the sort itself (3 of
7 correct on first pass — see the corrections in the table) and the two
decisions on `count`. Recorded here so it is not mistaken later for his own
work, same as the Unit 1 snapshot tooling.

Two decisions Gaurav made that shaped the code:

- `count: null` means the explorer asserted a locator it never ran — the
  explorer should run it or omit it. The scorer treats null as unverified and
  gates on it when confidence ≥ 3.
- `count: 0` should be a real value, and the tool must be fixed to return it.
  Until then, `_unmeasured_reason()` refuses to read a zero as a measurement.
  Both fixes are owed in `vibium_tools.py:98`; neither was made in this unit.

Result on the existing login trace: **19/25 from code**, with three critical
failures — all three `data-test` fallbacks carry confidence 3 on a count that
was never executed. `strategy_validation` 2/5, `multi_strategy_coverage` 2/5
(two of three `or_chain`s name a fallback that was never run). The old rubric
scored this trace band B. The deterministic half does not agree.

### Dimension-by-dimension justification

Test applied: *give two competent engineers the same element-map — could they
disagree on the answer?* If no, it is code.

| Dimension | Needs an LLM? | Why |
|---|---|---|
| semantic_primary_rate | **No** | `primary.type` is a literal string from a fixed enum. Counting how many fall in the semantic set is arithmetic. |
| coverage_completeness | **No** | Was judgment only while nothing existed to compare against. Unit 1's `target.json` made it set membership. Matching is on selectors the answer key recognises, not on element names — the explorer invents those. |
| strategy_validation | **No** | Internal coherence only: is the primary among the listed strategies, does its count support the claim, is confidence consistent with whether the locator was executed. Live re-resolution against the frozen page is Unit 3's, deliberately not borrowed here. |
| dynamic_content_flagging | **No** | "Matches more than one and nothing acknowledges it" is two fields and a comparison. |
| context_narrative_quality | **Yes** | Whether prose adds something the JSON does not is an opinion about writing. No field carries it and no code check approximates it. **Kept.** |
| multi_strategy_coverage | **No** | Presence of an `or_chain` plus a second strategy with a measured count. Format is deliberately *not* scored: Unit 0 found 47 formats across 20 traces, which is a missing spec, not a model defect — enforcing an unwritten rule is preference wearing a lab coat. |
| interaction_contract_quality | **Yes, under protest** | Whether an element triggers navigation is a hard fact about the page, but `ElementRecord` has no field for it, so a code scorer has nothing to read. The fix is a schema field, not a better scorer. Logged, not made. **Kept by default, not by merit.** |

**5 of 7 in code.** Exit met. Both survivors are defended above; only one is
defended on merit.

### Closed-book explanation

> For each dimension, does it need an LLM, and why?

_Not yet written. Owed by Gaurav, closed-book. Claude authored the build and the
justification table for this unit, which makes the retention check more
important here, not less — a table you did not write is not a thing you know._

---

## Unit 3 — The state-based scorer

### What I built

### Closed-book explanation

> Why is this number more trustworthy than any rubric score?

---

## Unit 4 — The harness proper

### What I built

### Closed-book explanation

> Why does pass@1 flatter an agent, and what does pass^k protect you from?

---

## Interlude — Dataset expansion

### What I built

### Notes

---

## Unit 5 — The LLM judge, done right

### What I built

### Closed-book explanation

> Why is overall agreement misleading, and what does a high TPR with a low TNR
> mean in practice?

---

## Unit 6 — Trajectory evaluation

### What I built

### Closed-book explanation

> A concrete case from my own traces where output was fine and trajectory was not:

---

## Unit 7 — Regression and criterion validity

### What I built

### Closed-book explanation

> What would it mean if band did not correlate with downstream success?
