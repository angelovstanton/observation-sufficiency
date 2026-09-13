# Predicate & Corpus Provenance Manifest

**Purpose.** Self-documenting provenance for the frozen success predicate and the
locked 6,000-record corpus, so a mixed-predicate or oracle-leak accusation can be
rebutted from a single manifest without re-reading history. This file is
**additive** — it records hashes and facts already true; it touches no corpus
record and moves no canonical number.

_Last updated: 2026-07-23 (hash-provenance honesty fix; repoint post-split file:line citations)_

---

## 1. Frozen predicate

| Field | Value |
|---|---|
| File | `shared/oracle/Oracle.cs` |
| SHA-256 (current, HEAD) | `841231109312b5a1edaedeef18878ec0d8369a0a7c1bf4d87f684c331e31e20b` |
| SHA-256 (previously recorded) | `79aa9412020877e18a65ec1b46dc4827e812f072530e0f686a315f382e4ccf50` |
| Logic frozen (authoritative) | **2026-06-17T18:34:41Z** — re-freeze after an independent second-family code audit; predicate logic unchanged since |
| Predicate shape | 5-condition success predicate; 3-mode failure taxonomy (priority lacked > unreachable > grabbed) |

The file digest was **first recorded** in this manifest after the freeze; prior to
that the freeze was documented by convention only, not by a stored hash. The header
inside the file itself records the freeze (`Oracle.cs:7`, "PREDICATE RE-FROZEN
2026-06-17T18:34:41Z — post-external-audit re-validation").

### Hash provenance — why the digest moved after the logic freeze

`Oracle.cs` has been edited three times since the 2026-06-17 logic freeze, all
**non-logic**; a reader doing `git log shared/oracle/Oracle.cs` will find each accounted
for here. SHA-256 of the file at each commit:

| Commit | Change | `Oracle.cs` SHA-256 |
|---|---|---|
| `413384b` | logic freeze (2026-06-17T18:34:41Z) | `dbfae255…f34681` |
| `e269992` | split `record` type declarations (`ElementData`/`OracleRef`/`EvalResult`) into their own files — no logic | `dd3c0c00…217583` |
| `b442e6c` | add `///` XML-doc summaries — comments only | `79aa9412…ccf50` *(the previously recorded digest above)* |
| `f0c85ef` | dedup the BEM-base rule: `IsBemBaseOfVolatile` `private`→`internal` (+ `InternalsVisibleTo`) — visibility only | `841231…e20b` *(current)* |

The only commit to touch `Oracle.cs` after the digest was recorded is **`f0c85ef`**
(2026-07-22), and its sole change to this file is one access modifier
(`private`→`internal`) so `AttributeBundles.ApplyBundleNoVolatile` can call the single
authoritative BEM-base rule instead of duplicating it. **The predicate logic is
byte-for-byte unchanged.** Evidence: the BEM-parity `[Fact]` in `oracle.tests` runs
`Oracle.IsBemBaseOfVolatile` and the harness's `ApplyBundleNoVolatile` path over 22 real
testbed class names and asserts zero disagreement — passing as part of the **69/69**
`oracle.tests` suite.

**Re-pin command** (deliberate act — only after a documented, re-validated predicate
change: (1) a documented reason, (2) re-running the positive-control set (29
controls), (3) re-running the NONE-target replay, (4) a separate isolated commit
with "predicate change" in the message):

```
python -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('shared/oracle/Oracle.cs').read_bytes()).hexdigest())"
```

### Freeze-timestamp disambiguation

Two freezes occurred on the same day; do not conflate them:
- `2026-06-17T12:16:59Z` — an earlier freeze the same day, superseded a few hours later.
- **`2026-06-17T18:34:41Z`** — the authoritative re-freeze after the external audit
  (29/29 controls, D1–D5 fixes validated). All corpus classification is under this
  predicate.

---

## 2. Corpus reclassification (2026-07-20)

Eleven pages measured before the freeze were re-classified by **zero-LLM replay**
of their recorded locators — the model outputs are the originals; only the frozen
predicate was re-applied. The thirteen post-freeze pages were already consistent
and were not touched.

| Field | Value |
|---|---|
| Reclassified pages (11) | 01, 02, 04, 05, 08, 10, 11, 12, 14, 19, 21 |
| Reclassification date | 2026-07-20 |
| Method | zero-LLM `--replay` (predicate re-applied to archived locators) |
| Records touched | 206 |
| Net success-outcome change | **+51** (+61 gained − 10 lost) |
| Mechanisms | `VolatileClassRe` over-rejection fix (+61); `page_01` t_04 breadcrumb → `observation_lacked_stable_signal` (−10) |

Source of these facts: `experiments/computed_findings.md` §"Corpus provenance" (lines 11-29).

### Do not conflate with the audit-freeze re-replay

A **separate, earlier** replay event — the 2026-06-17 audit-freeze *validation*
re-replay (2,750 records over 11 pages, **+46 net**, D5 reclassification of 161
volatile→stable) — is not the corpus reclassification above (206 records, +51 net).
The two happen to touch 11 pages each, but they are not the same replay, and
their net counts are not interchangeable.

---

## 3. F4 (B_playwrightMCP / ARIA) oracle-leak audit — read-only provenance proof

**Open question:** the DOM encodings F0–F3 strip `data-oracle-*` before
serialization, but the F4 path (real Playwright ARIA snapshot) only *warns* on
detecting oracle text and writes no per-record leak flag — can a reviewer verify
from the artifacts that F4 never leaked an oracle anchor?

**Note on scope.** The raw ARIA-snapshot *text* is never persisted — the corpus
stores only tokens + locator + predicate booleans (`GroundingRecord.cs:12-40`), so
there is no stored F4 observation string to re-scan byte-for-byte. The proof below
rests on three things: a scan of the shipped records, the strip-by-construction
guarantee in the harness code, and the predicate logic itself being frozen with its
hash recorded (§1).

**Evidence (read-only, 2026-07-21):**

1. **No oracle string in any stored record.** `grep -rE "data-oracle|oracle-id"`
   over every `experiments/runs/*.jsonl` returns **0 hits** — no returned locator
   or field references an oracle anchor.
2. **F0–F3 strip by construction.** `StripOracleAnchors`
   (`shared/harness/AttributeBundles.cs:212`) drops every attribute whose key begins
   `data-oracle-`; it is called unconditionally in `BuildObservationAsync`
   (`shared/harness/Observation.cs:126`). DOM encodings physically cannot carry oracle anchors.
3. **Zero leak warnings ever emitted.** The only emitter of the warning is
   `GroundingRunner.cs:179` (`[WARN] F4 oracle leak detected`); `grep` over all of
   `experiments/runs/` finds **0** such lines.

**Conclusion:** zero oracle leakage in the locked corpus, established by the record
scan and warning scan above, the strip-by-construction guarantee, and the frozen
predicate logic (hash recorded in §1). The F4 leak oracle
(`shared/harness/Observation.cs:98`, a case-insensitive substring test for `"oracle"`
over the ARIA YAML) never tripped during the run.

### Forward recommendation (not implemented here)

For future runs, add `oracle_leak_detected` (bool, default `false`) as an
**additive** field on the record schema so future corpora carry first-party,
per-record leak evidence directly in the JSONL. The corpus stays locked and is
not retrofitted. A stronger first-party byte-scan (regenerate the 24 ARIA snapshots
offline via Playwright headless Chromium + testbed server — no LLM) is available on
request but was not run, per the read-only decision.
