# Eval Harness — Course

A purpose-built evaluation harness for vibe-check's **explorer** agent, built as
a learning course. The harness is the deliverable; understanding it is the point.
Those are not the same goal, and this document exists because the second one is
the easy one to lose.

System under test: `agents/explorer/`. Everything else in the repo is out of
scope until Unit 7.

**Scope narrowed 2026-09-08 to the login page only.** Error analysis showed the
explorer has no fill/type tool, so `/inventory.html` and `/cart.html` are behind
an auth gate it cannot pass — 12 of the first 20 runs mapped the login form and
filed it under the wrong page name. Login is the only page where the explorer is
actually doing the job being measured. The 8 existing login traces are the working
set; the 12 blocked traces are kept as evidence for that finding, not analysed
further.

Tradeoff to remember: one page measures **consistency** (8 outputs, 1 input) and
says nothing about **generalisation**. Don't trust an absolute accuracy number
off a one-page dataset. Consistency is the more useful axis while learning the
machinery — Units 1-4 and 6 all work at n=1. Units 5 and 7 do not, which is what
the **Interlude** between Units 4 and 5 exists to fix.

---

## Why this document exists

Research on AI-assisted programming finds the failure mode is not laziness but
**metacognitive miscalibration**: learners rate their understanding as high
during assisted work, then underperform when working alone. Functional code gets
mistaken for mastery, and the gap is widest exactly when the assistance was most
effective.

The countermeasure is not less assistance. It is a different *role* for the
assistant: examiner, not author.

---

## Protocol — read before asking Claude for help

**Revised 2026-09-08.** The original protocol opened each unit with a written
prediction before any explanation. Two units in, it had produced zero data
points: predicting requires adjacent knowledge to extrapolate from, and for most
of this material there is none yet. The gate was producing blanks, and blanks
teach nothing. It is removed. The rule that actually matters — Claude examines,
Gaurav authors — is kept and unchanged.

### Gate 1 — Build

Gaurav writes the implementation. Claude reviews, finds bugs, and asks "why this
and not that" — and does **not** write it for him.

Claude MAY write: argparse blocks, file IO boilerplate, test scaffolding, type
stubs, and anything a unit explicitly labels "plumbing".

Claude MUST NOT write: scorers, metrics, dataset schema decisions, judge prompts,
aggregation logic. That is the material.

When Gaurav is genuinely stuck, Claude explains the *mechanism* with a concrete
case from the repo's own data, then hands back the decision. Every time Claude
supplies reasoning that should have been Gaurav's, it gets recorded in
`LEARNING.md` under that unit, so authorship stays honest.

Exception: **Unit 0 is a fully worked example.** Unit 1 is joint. Unit 2 onward,
Gaurav drives. Deliberate fading of guidance, not inconsistency.

### Gate 2 — Explain (closed-book)

At the end of each unit, Gaurav writes a plain-English explanation of the concept
in `LEARNING.md` **without looking at the code**. If he cannot, the unit is not
done — regardless of whether the tests pass.

This is now the only retention check, so it is not optional. It is also the one
that works: explaining after building is a retrieval act, and retrieval is what
makes memory durable.

### Session rules

- **Retrieval warm-up:** every session opens with 3 questions from prior units,
  answered from memory, before any new work. Verbal, not logged. Retrieval before
  new material beats the reverse order.
- **Delayed feedback:** Claude reviews at the end of a unit's build, not
  line-by-line during typing.
- **No unit is complete without its numeric exit criterion met.**

---

## Curriculum

Total ≈ 31 hours (27 + the 4h Interlude added 2026-09-08). Each unit: concept → predict → build → explain → exit check.

### Unit 0 — Error analysis  (~4h)  [worked example]

**Concept.** You cannot write a good check for a failure you have never seen.
Error analysis is the manual process of reading real traces, writing down every
defect in your own words (open coding), clustering those notes into failure modes
(axial coding), and counting them. Every automated eval downstream is scaffolding
on top of this pass. It is the step everyone skips.

**Build.**

- Run the explorer ~20 times across 3-4 pages; save every `element-map.json` and
  `context.md` with its run id.
- A dead-simple trace viewer — one HTML file, no framework — to read them.
- A CSV: one row per observed defect, in your own words.
- Cluster into named failure modes. Count each.

**Explain.** Why does a rubric written before error analysis usually contain dead
checks?

**Exit.** All 8 login traces reviewed. A written failure taxonomy with counts.

**DONE 2026-09-08 → `DEFECT-LOG.md`.** 29 observations, 11 clusters, counts on
all of them. Reviewed 3 by hand (001, 004 as the worked example; Gaurav
hand-verified the live DOM and traced 001's tool calls) and 5 machine-assisted
via `tools/compare_runs.py` plus a read of all 8 `context.md`. Gate 1 was not
satisfied for this unit — no predictions were written before the traces were
read, so there is no prediction-vs-reality measurement for Unit 0. Gate 3 still
open.

---

### Unit 1 — Dataset and the frozen environment  (~3h)  [joint]

**Concept.** A *sample* is an input paired with a **target** — a known-correct
answer you authored. `evals/*-golden.json` today holds rubrics, not samples,
which is why nothing in the repo can currently be scored for accuracy. Separately:
an eval that runs against the live internet is not reproducible. Freezing the
environment is eval design, not a workaround — distinct from the HAR-replay
anti-pattern, which was routing around a blocker instead of fixing it.

**Build.** `evals/dataset/` — a frozen snapshot of the login page, plus a
hand-authored list of the elements that should be found and the correct locator
for each. A loader that yields `(input, target)`.

Note the shape with one page: **1 sample, 1 target, 8 outputs to score against
it.** Many outputs per sample measures consistency; many samples measures
accuracy. You're buying the first for now.

**Explain.** What does "target" mean, and why can a rubric not serve as one?

**Decisions taken 2026-09-08** (Claude recommended, Gaurav accepted — see
`LEARNING.md`):

- *Envelope shape:* a `Sample` dataclass (`sample_id`, `url`, `target`). Attribute
  access fails loudly on a typo; a dict returns `None` silently. This object is
  passed through every unit to 7, so it is worth the strictness.
- *Frozen, not live:* the login page's HTML and assets are saved to
  `evals/dataset/login/snapshot/` and served over a local HTTP server (not
  `file://` — relative asset paths and CDP behave differently). `target.json` was
  hand-verified against the DOM on 2026-09-08 and rots silently the day SauceDemo
  edits their markup. Frozen means a failing run is always the explorer's fault.
  Cost: the eval stops tracking reality, so a live-vs-snapshot drift check and a
  written refresh procedure are part of this unit's build, not optional extras.

**Exit.** 1 sample with a target authored by hand, by you — from looking at the
page, never derived from an element-map. Plus: the loader yields it, and the
explorer can run against the frozen copy.

---

### Unit 2 — Deterministic scorers  (~3h)

**Concept.** The LLM judge is the tool of last resort, not the default. Every
check moved out of the judge has zero variance, zero cost, and zero calibration
debt. Pulling `schema_compliance` into jsonschema was the right instinct applied
once; this unit applies it exhaustively.

**Build.** Code-based scorers replacing the judged dimensions that never needed
judgment: semantic-primary rate, or_chain coverage, ambiguity (count > 1),
repeat-flag correctness.

**Explain.** For each of the 7 original dimensions, state whether it needs an LLM
and why. Defend the ones you keep.

**Exit.** ≥5 of 7 dimensions are code. A written justification per dimension.

---

### Unit 3 — The state-based scorer  (~3h)

**Concept.** Agents change a world, so correctness can be graded on world state
rather than on text. This is how tau-bench works: compare final state against an
annotated goal state, no judge involved. The explorer's real ground truth is not
a rubric score — it is whether each recorded locator resolves to exactly one
correct element on the page.

**Build.** Resolve every locator in an element-map against the frozen page with
Playwright. Assert `count == 1` and that the resolved element matches the labeled
target. Emit per-element accuracy.

**Explain.** Why is this number more trustworthy than any rubric score?

**Exit.** A real per-element accuracy figure for a real explorer run.

---

### Unit 4 — The harness proper  (~4h)

**Concept.** Dataset × Solver × Scorer bound into a repeatable Task, run k times,
aggregated with uncertainty. `pass^k` ("all k attempts succeeded") rather than
`pass@1`, because agent errors compound — a 90% pass@1 agent is 57% reliable at
k=8. A score without a variance estimate is not a measurement.

**Build.** A runner that loops the dataset, executes k independent trials, records
full traces, and aggregates. Metrics: mean ± stdev, pass^k, per-sample breakdown.

**Explain.** Why does pass@1 flatter an agent, and what does pass^k protect you
from?

**Exit.** pass^k and mean ± stdev printed for the whole dataset.

---

### Interlude — dataset expansion  (~4h)  [blocks Units 5 and 7]

**Why this exists.** Added 2026-09-08 after an audit found Units 5 and 7 were not
completable on a one-page dataset, and nobody noticed when scope was narrowed to
login. Unit 5 needs ~100 hand-labeled examples and a held-out split; login gives
3 elements × 8 runs = 24 judgments and no split. Unit 7 asks you to *correlate*
explore band against downstream pass rate; correlation at n=1 sample is not a
thing. Units 1–4 and 6 are fine at n=1 — they measure consistency. Units 5 and 7
measure accuracy and prediction, and those need samples.

**The blocker is already in your defect log.** Cluster J: 12 of 12 runs never
reached their target page, because the explorer has no fill/type tool and
everything interesting on SauceDemo is behind the login gate. That was ranked the
#1 failure in Unit 0. Fixing it is what unlocks more pages.

**Build.**

- Give the explorer a fill/type tool. This is the first change to the system under
  test — everything before this measured the explorer as-is.
- Re-run against inventory, cart, and checkout. Hand-author a `target.json` for
  each, same tiered format as login, same rule: from the live DOM, never from an
  element-map.
- 4 pages × ~3-8 elements × 8 runs lands around 100-150 labeled judgments. That is
  Unit 5's dataset.

**Note for Unit 7.** The 8 existing login traces become your *pre-change*
baseline. Adding a tool to the explorer is exactly the kind of change Unit 7's
significance-aware diff is built to evaluate, so keep them.

**Exit.** ≥4 samples with hand-authored targets. ≥100 labeled locator judgments
available. The explorer reaches every page it is asked to map.

---

### Unit 5 — The LLM judge, done right  (~4h)

**Concept.** Binary, not Likert: range scores cannot be reliably aligned to human
judgment, binary can. Validate with **TPR and TNR separately** — overall agreement
is a vanity metric, since a judge that always says "pass" scores 90% on a
90%-pass dataset. Judges need ~100 labeled examples and ongoing maintenance. And
hold out a split, or you are just overfitting the judge prompt to your labels.

**Build.** Reduce the surviving judged dimension(s) to binary. Label ~100 examples
by hand. Measure TPR/TNR on train, iterate the prompt, report on held-out.

**Explain.** Why is overall agreement misleading, and what does a high TPR with a
low TNR mean in practice?

**Exit.** TPR ≥ 0.9 and TNR ≥ 0.9 on the held-out split. Requires the Interlude:
~120 judgments split 80 train / 40 held-out. Do not attempt this on login alone —
24 judgments with no split will produce a number that means nothing.

---

### Unit 6 — Trajectory evaluation  (~3h)

**Concept.** This is what makes it an *agent* harness rather than an output
harness. A correct result reached in 20 steps with two bad tool calls is a failing
trajectory that final-answer scoring marks green. Current practice scores three
layers: final answer, trajectory, per-turn.

**Build.** Capture the explorer's tool-call sequence. Score wasted/redundant
calls, recovery after a failed call, steps-to-completion, token cost.

**Explain.** Give a concrete example from your own traces where output was fine
and trajectory was not.

**Exit.** Trajectory metrics on the dataset, plus ≥1 identified good-output /
bad-trajectory case.

---

### Unit 7 — Regression and criterion validity  (~3h)

**Concept.** Two questions a harness exists to answer. (a) Did my change move the
number *beyond noise*? `diff_runs.py` currently cannot tell a regression from
variance because it has no noise floor. (b) Does my gate predict the thing it was
built to protect? The `band >= B` rule claims the writer can trust the output.
That is falsifiable and has never been tested.

**Build.** Feed Unit 4's variance into a significance-aware run diff. Then run
explore → write → run across the dataset and correlate explore band against
writer-gate pass and pytest pass rate.

**Explain.** What would it mean if band did not correlate with downstream success?

**Exit.** A data-backed yes/no on whether the gate predicts anything. Requires the
Interlude — the correlation needs ≥4 samples, and even then treat the result as
directional, not conclusive. State the n next to the number, always.

---

## Capstone

Write up what you built and what you measured — publicly. Teaching it back is the
strongest retention check there is, and it doubles as the artifact that makes the
project worth having done.

---

## Progress

| Unit | Built | Explained | Exit met | Date |
|---|---|---|---|---|
| 0 — error analysis | ☑ | ☐ | ☑ | 2026-09-08 |
| 1 — dataset + frozen env | ☑ (loader+snapshot by Claude) | ☐ | ☑ | 2026-09-08 |
| 2 — deterministic scorers | ☐ | ☐ | ☐ | |
| 3 — state-based scorer | ☐ | ☐ | ☐ | |
| 4 — the harness proper | ☐ | ☐ | ☐ | |
| Interlude — dataset expansion | ☐ | n/a | ☐ | |
| 5 — LLM judge | ☐ | ☐ | ☐ | |
| 6 — trajectory eval | ☐ | ☐ | ☐ | |
| 7 — regression + validity | ☐ | ☐ | ☐ | |

The "Predicted" column was removed 2026-09-08 along with Gate 1. Units 0 and 1
both have empty prediction sections; the reason is recorded in `LEARNING.md`.

---

## References

- Hamel Husain, *Using LLM-as-a-Judge For Evaluation* — https://hamel.dev/blog/posts/llm-judge/index.html
- Hamel Husain & Shreya Shankar, *AI Evals FAQ* — https://hamel.dev/blog/posts/evals-faq/
- Inspect, UK AI Security Institute — https://inspect.aisi.org.uk/
- *tau-bench* — https://arxiv.org/abs/2406.12045
- *Beyond the Final Answer: Evaluating Reasoning Trajectories* — https://arxiv.org/pdf/2510.02837
