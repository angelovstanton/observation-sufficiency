# Real-site pilot: addendum (а‴) — page clock paused for scoring and survival

Author's decision (2026-10-14). Committed **before** the code that implements it, before the paid pilot
run, and before any pilot record exists (`batch_runs_pilot/` does not exist). It amends addenda (а′)
(`pilot_addendum_scoring_a2.md`), (а″) and (д) (`pilot_addendum_scoring_a3.md`). The observation path and the data
sent to the model are unchanged; the plan (`pilot_plan.json`, sha256 `b79364225b5e…`) is unchanged.

## Motive

Timers are not stopped on the observation path (§2 (б) unchanged). For scoring, the page clock is paused after the
load, and the pre-hash shows that the evaluated DOM is identical to the observed state. The aim is to score exactly
what the model saw, independently of machine speed. Reason: on mobile.de, walk + evaluation take about as long as the
DOM stays still (feasibility tables of 2026-10-14, both series).

The feasibility data (offline, no model): mobile.de, 2 × 50 evaluations from a cold
browser under (а′)+(а″): 52% and 74% within 5 attempts (24 and 13 refusals); median walk + evaluation 376 ms against a
first page mutation at a median 331 ms after the window opens. wikipedia.org and kaspersky.com: 100% within 5 attempts.

## Rule (а‴)

1. **Where.** The page clock is paused **only** on the loads that score a locator (Execute, Rescore, reuse) and on
   the survival loads. The observation path, the observation sent to the model, its hash, and `--verify-observations`
   are unchanged; timers keep running there (`pilot_rule.md` §2 (б) unchanged).
2. **How.** On those loads, right after the load and the markers (survival: right after the load), and before the
   mutation window opens and the first walk, the page clock is paused at its **current** time: the fixed time of the
   registered shim (`Date.now()`, the record's timestamp), with no forward jump. No timer, interval or animation frame
   runs after the pause, and none is triggered by it. Shown by a test (MutationObserver = 0 and a callback counter = 0
   after the pause; a 3 s timer does not fire).
3. **Shims.** The registered loader sets the fixed time (`Clock.SetFixedTime`) before navigation, which already
   installs Playwright's controllable clock; no `clock.install` is added and the load is unchanged. The `Date` and
   `Math.random` shims are unchanged; `Date.now()` stays the fixed time after the pause. If the load changed, the
   pre-hash would show it.
4. **Unchanged guards.** Pre-hash == pinned (full first walk) stays. The mutation window of (а′) / (д) stays as an
   additional guard (expected to always count 0). If it counts > 0: a new load, at most 5 attempts (а″), then exit 3
   (scoring) or "survival undetermined (unstable DOM)" (survival), as before. The warm-up of (а″) stays.

## Tests required before the code is committed

- Scoring path with the paused clock on all 198 cells: pre-hash == pinned 198/198.
- Feasibility: wikipedia.org, kaspersky.com, mobile.de × 50 × 2 cold series, one of them under parallel CPU load:
  100% on the first attempt and 0 exit 3.
- The delayed-evaluation test of (а′) point 7 (2 / 10 / 30 s): 5/5 identical results.
- Survival: the as-is / +5 s / reversed check → 0 differences (8 on 1 site before (д)).
- `--verify-observations` 198/198 and the 3-site E2E with restarts → 0 exit 3.
