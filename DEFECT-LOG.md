# Defect Log — Unit 0 error analysis

**Scope:** the 8 `traces/*-login/` runs. Model: claude-sonnet-5. Collected 2026-09-07.

**Provenance:** 3 traces hand-reviewed (001, 004 by Claude as the worked example;
Gaurav hand-verified the live DOM and traced 001's tool calls). 5 traces
machine-assisted via `tools/compare_runs.py` on structured fields plus a read of
all 8 `context.md` files. Weight the taxonomy accordingly — the counts are solid,
the *completeness* of the category list is less certain than a full hand review
would give.

---

## Step 1 — Open coding

| # | Trace | What I noticed |
|---|---|---|
| 1 | 004 | `viewport` is the string `"unknown"` — passes the format check, tells me nothing |
| 2 | 004 | `crawled_at` is exactly midnight — made up; there is no clock in its toolkit |
| 3 | 004 | `stats.gaps` says 0, but `context.md` lists 3 gaps. The file disagrees with itself |
| 4 | 001 | `accessibility_node.name: null` for loginButton. Real accessible name is "Login" (verified in DOM) |
| 5 | 019 | `accessibility_node.name` is `""` — a third representation of "no name" alongside `null` and `"Login"` |
| 6 | 010 | Primary is `role=button,text=Login` with `count: 1`. `text=Login` matches **0** on this button — count looks fabricated |
| 7 | all 8 | `or_chain` written 8 different ways for the same element. Playwright syntax, prose, `->`, `OR`, `||`, parentheticals |
| 8 | 001,007,010,019 | `testability_gap: true`; 004,013,016,020 `false`. Same page, same element |
| 9 | 007,010 | Marked `gap: true` *despite* having found the accessible name — so it isn't caused by missing the name |
| 10 | 007 | Claims the accessible name comes from "its `value`/`aria-label`". **There is no `aria-label` on that button** |
| 11 | 016,020 | Assert the logo is "a CSS background image, not an `<img>`" — never probed for images. Training recall |
| 12 | 001,003,015,017,019,020 | CSS fallback strategies carry `count: null` — schema requires an integer |
| 13 | 001,019,020 | CSS fallbacks sourced from "known SauceDemo markup" — asserted, never executed |
| 14 | 020 | "Every `testid=...` query **timed out**" — but recorded as 0 matches |
| 15 | 010 | "`text=Login` query **timed out** with 0 matches" — timeout and zero-match conflated |
| 16 | 004 | "`label` query **timed out** / no match" — same conflation, in the element-map note |
| 17 | 019 | Rates the login-button name issue **HIGH**. 013 says "No HIGH or MEDIUM gaps" for the same page |
| 18 | 007,010 | Rate the testid finding **MEDIUM**; 001,004,013,016,019,020 rate it **LOW** |
| 19 | 013,019,020 | Report `role=textbox` ambiguity as a gap; 007,010,016 do not mention it |
| 20 | 001 | `n strategies tried` = 4; 004,007,010,016 = 2. Same element, 2x difference in effort |
| 21 | 004 | `vibium_get_a11y_tree` omits names that `vibium_find` confirms — the two tools disagree |
| 22 | 016 | Prose asserts "All 3 elements have a confident (5/5) primary" — true for 016, but 001 and 007 recorded 4 |
| 23 | 011 | Invented a `blocker` top-level key; 014 invented `blocker_note` + `non_interactive_context` |
| 24 | 011,015 | (out of scope, kept as evidence) Never reached the target page — no fill/type tool exists |
| 25 | 015 | (out of scope) Mapped the login form and filed it under `"page": "cart"` |
| 26 | all | `confidence` varies 3/4/5 for identical measured evidence (`count=1`, same selector) |
| 27 | 011 | **Correct behaviour:** refused to fabricate a map from memory, documented the blocker instead |
| 28 | 007 | Claims visible text is "LOGIN", CSS-uppercased from `value="Login"`. Screenshot shows **"Login"**, mixed case. No uppercasing. Fabricated |
| 29 | all 8 | **Correct behaviour:** every run correctly determined `text=Login` cannot match this control |
| 30 | root cause | `vibium_tools.py:98` — `find_all` **raises TimeoutError** on no-match, never returns empty. The `count: 0` branch is dead code, so every zero-match probe reaches the agent as an exception and gets written down as `count: 0`. This is cluster B's cause |
| 31 | root cause | Each no-match probe blocks for **30s**. At 4-6 failed probes per run that is 2-3 min of pure waiting — most of the 250-690s run durations |

---

## Step 2 — Clusters

| Cluster | Rows |
|---|---|
| **A. Unverified assertions from training recall** | 10, 11, 13, 28 |
| **B. Tool failure recorded as factual negative** | 14, 15, 16, 30 |
| **C. Schema violations** | 12, 23 |
| **D. Self-contradiction within one run** | 3, 22 |
| **E. Disagreement about observable page facts** | 4, 5, 6, 21 |
| **F. Undefined terms → inconsistent judgment** | 8, 9, 17, 18, 19 |
| **G. Meaningless or fabricated field values** | 1, 2 |
| **H. Undefined output format** | 7, 26 |
| **I. Variable effort on identical work** | 20 |
| **L. Wasted wall-clock from tool design** | 31 |
| **J. Wrong page mapped** (out of scope, kept as evidence) | 24, 25 |
| **K. Correct behaviour to preserve** | 27, 29 |

---

## Step 3 — Counts

Over the 8 login traces unless noted. Mechanical counts from
`tools/compare_runs.py` and the scratchpad `count_modes.py`.

| Cluster | Metric | Count |
|---|---|---|
| G | `crawled_at` fabricated (exactly midnight) | **18 of 20** (7 of 8 login) |
| G | `viewport` = `"unknown"` | 3 of 8 login (7 of 20) |
| H | distinct `or_chain` formats | **47 across 20 traces**, no two alike |
| H | `confidence` values for identical evidence | 3 distinct (3, 4, 5) for `count=1` |
| F | `testability_gap` split on loginButton | **4 true / 4 false** |
| F | severity for the testid finding | MEDIUM ×2, LOW ×6 |
| F | severity for the button-name finding | HIGH ×1, MEDIUM ×2, LOW ×5 |
| E | `accessibility_node.name` for loginButton | `"Login"` ×6, `null` ×1, `""` ×1 |
| C | traces failing `validate_explorer_output` | 7 of 20 (all from `count: null`) |
| B | timeouts recorded as zero-match | 3 traces state it explicitly in prose |
| I | `n strategies tried` on loginButton | range 2–5 |
| J | runs that never reached their target page | **12 of 12** inventory + cart |

---

## Verdict — what the counts say

**Ranked by count × consequence:**

1. **J — wrong page mapped (12/12).** Root cause: the explorer has no fill/type
   tool, so anything behind auth is unreachable. Biggest failure in the set, and
   invisible to the current rubric, which has no "did you get there" dimension.
   `EXP-002-*` and `EXP-003-*` in `explore-golden.json` can never pass.
2. **G — fabricated field values (18/20).** `crawled_at` is fabricated *by
   design*: the system prompt asks for "a timestamp you compute from context"
   and there is no clock. Fix the prompt, not the model.
3. **B — timeout recorded as zero-match.** Low count but high consequence: a tool
   failure is being converted into a factual claim about the page. "The query
   timed out" and "the element does not exist" are not the same statement, and
   the difference propagates into every downstream locator decision.
4. **H — undefined output format (47 formats).** `or_chain` and `confidence` have
   no spec, so every run invents one. Not model error — spec absence.
5. **F — undefined terms (4/4 split).** `testability_gap` and the LOW/MEDIUM/HIGH
   scale are nowhere defined. Runs 007 and 010 found the accessible name and
   still flagged a gap, so this is genuine definitional ambiguity, not missing
   evidence.
6. **C — schema violations (7/20).** All `count: null` on unexecuted CSS
   strategies. Would fail the gate; nothing noticed because the grader never ran.
7. **E — disputed page facts.** 2 of 8 disagree with the other 6 about the
   button's accessible name. Settled against the live DOM: the name is "Login".
8. **A — unverified assertions.** CSS fallbacks and DOM-structure claims sourced
   from training recall rather than observation. Directly contradicts the system
   prompt's "a11y tree is ground truth" instruction.
9. **I — variable effort.** 2 to 5 strategies tried on the same element.

**K is not a defect list — it's the regression risk.** Two behaviours worth
protecting: refusing to fabricate when blocked (011), and correctly ruling out
`text=` on an `<input type=submit>` (8/8). Any scorer built next must score these
as *good*, or it's untested in the passing direction.

Note K shrank from 3 to 2 on review: 007's "CSS-uppercased LOGIN" reasoning was
credited as good and turned out to be fabricated. Cluster A gained a row and the
one genuinely-good-judgment example was lost. Worth remembering that the *praise*
in an error analysis needs verifying as hard as the criticism.

---

## Implications for the rubric

The current 7 LLM-judged dimensions grade **locator quality**. The counts say the
top three failure modes are *unreachable pages*, *fabricated fields*, and *tool
errors laundered into facts* — none of which any dimension covers.

Checks the data argues for, none of which need an LLM:

- Did the run reach the URL it was asked to map?
- Does every strategy with a `selector` have an integer `count`?
- Was every strategy type probed before one was declared unavailable?
- Did any tool call time out, and is that recorded as an error rather than a zero?
- Is every `count` reproducible by re-running the locator against the page?

That last one is Unit 3 and subsumes most of the rest.

---

## Traces reviewed

- [x] 001-login (hand)
- [x] 004-login (hand)
- [x] 007-login (prose hand-read + structured diff)
- [x] 010-login (prose hand-read + structured diff)
- [x] 013-login (prose hand-read + structured diff)
- [x] 016-login (prose hand-read + structured diff)
- [x] 019-login (prose hand-read + structured diff)
- [x] 020-login (prose hand-read + structured diff)
