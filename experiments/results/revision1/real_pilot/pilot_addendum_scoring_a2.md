# Real-site pilot: addendum (а′) — scoring checkpoint by mutation window

Author's decision (2026-10-14). Committed **before** the code that implements it, before the paid pilot
run, and before any pilot record exists. It replaces the post-evaluation check of point (а) of
`pilot_addendum_scoring.md` (commit `29b291c`); everything else in that addendum ((а) fresh load per evaluation,
pre-hash, retry and exit 3; (б); (в); (г)) is unchanged. The plan (`pilot_plan.json`, `b79364225b5e…`) and the
observation protocol are unchanged.

## Why (a departure, found before any model call)

Under (а) the observation sha256 was computed a second time after the Oracle evaluation and had to equal the pinned
one. Offline, with no model: on wikipedia.org, kaspersky.com and mobile.de the first walk
always equals the pin (54/54 loads), but the DOM then changes on every load, about 0.27 s (wikipedia), 0.47 s
(kaspersky) and 0.5 s (mobile.de) after the first walk ends. A second full walk takes 0.1–0.25 s, so the post-hash
races the page's timers; on mobile.de it failed on 4 of 4 loads and the run would refuse (exit 3) repeatedly. The
evaluation itself fits in the window; a second full walk is the wrong instrument to show it.

## Requirements

1. The `MutationObserver` is installed after the markers are set (they are mutations themselves) and before the first walk. It observes `subtree`, `attributes`, `childList` and `characterData` on `document` and on every open shadow root the walk finds. A shadow root attached inside the window also counts as a change.
2. The final check is synchronous (`observer.takeRecords()`; the asynchronous callback is not awaited). Zero records from the start of the walk to the end of the Oracle evaluation means the DOM is unchanged. Mutations by the Oracle itself, if any, are excluded explicitly and documented; if the Oracle does not write to the DOM, a test shows it.
3. Pre-hash == pinned stays (full walk). The post-hash is replaced by the check in point 2. Up to 3 fresh loads, then exit 3 without a record, as before.
4. The pilot record carries `mutation_count` in the window, `attempts`, and ms from the load to the end of the evaluation.
5. Declared limitation: a `MutationObserver` does not see property changes (`input.value`, `:checked`, `:hover`/`:focus`). The registered tasks are Click/Fill on a statically loaded page with no interaction before the evaluation, so the risk is negligible. None of the 326 targets may depend on such state; this is checked.
6. Feasibility test before the code is committed: 50 fresh loads under the protocol on each of wikipedia.org, kaspersky.com and mobile.de. It reports the share that succeeds on the first attempt, the share that succeeds within 3 attempts, and the walk + evaluation time relative to the first mutation. If a site does not reach 100% within 3 attempts, the code is not committed and those sites are decided separately.
7. The ancestor-state locator case (wikipedia.org t_03) gives the same result 3/3 with evaluation delays of 2 s, 10 s and 30 s. It never yields a wrong evaluation: either the correct result or exit 3, never a silently different result.

## Rule (а′)

- **Load.** As in (а): a new fresh offline load of the cell by the canonical loader (network blocked, shims, every
  target marker set by XPath).
- **Window opens.** After the markers are set and before the first walk, a `MutationObserver` is installed on
  `document` and on every open shadow root present at that moment, with `subtree`, `attributes`, `childList` and
  `characterData`. `Element.prototype.attachShadow` is wrapped to count shadow roots attached afterwards. The observer
  and the wrapper do not change the DOM.
- **Pre-hash.** The first walk is the cell's observation; its sha256 must equal the pinned one.
- **Evaluation.** The Oracle evaluation (resolution only) follows immediately on the same load.
- **Window closes.** Synchronously, in one page call: records delivered to the observer's callback so far plus
  `observer.takeRecords()`, plus the count of shadow roots attached in the window. The attempt counts only if this is
  **0**. The Oracle does not write to the DOM (shown by a test); no mutation is excluded.
- **On a mismatch** (pre-hash, or a mutation in the window): up to 3 new fresh loads; if none counts, the run stops
  (exit 3) and no record is written; the model's answer stays in the journal and is replayed without payment.
- **Recorded (pilot records only).** `scoring_attempts` (loads used), `scoring_mutations` (window count of each attempt,
  in order; the last is 0) and `scoring_ms` (ms from the start of the accepted load to the end of its evaluation). They
  are written at Execute and for a reused record; a restart's re-scoring compares the score fields only.

## Declared limitation

A `MutationObserver` does not see changes of DOM properties that are not attributes (`input.value`, checkedness,
`:hover` / `:focus`). The registered tasks are Click (323) and Fill (3) on a statically loaded page with no
interaction before the evaluation. Of the 326 targets: 272 link, 33 button, 10 menuitem, 8 tab, 1 searchbox,
1 textbox, 1 combobox; none is a checkbox, radio or option. The observation walk reads attributes and text only
(`Observation.cs`). A locator using `:checked` or a `[value=…]` / `[checked]` / `[selected]` selector is a volatile (state) signal for the
frozen Oracle (`Oracle.LocatorUsesVolatileSignal`, `Oracle.cs:351`), so it fails condition 3 of P5.
