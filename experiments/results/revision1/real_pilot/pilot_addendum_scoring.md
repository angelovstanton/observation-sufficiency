# Real-site pilot: addendum — scoring checkpoint, release liability, departure A1

Author's decision (2026-10-14). Committed **before** the code that implements it, before the paid pilot
run, and before any pilot record exists (`batch_runs_pilot/` does not exist). Prompted by an independent pre-run review
(not shipped). The rule (`pilot_rule.md`), the analysis plan
(`pilot_analysis_plan.md`), the sites, the targets, the plan (`pilot_plan.json`, sha256 `b79364225b5e…`) and the
observation protocol (addendum `1a16fa1`) are unchanged.

## (а) Scoring checkpoint

- **Rule.** Every evaluation of a locator — in the paid run after the model's answer (Execute), when a done record
  is re-scored on restart (Rescore), and when a reused class_only record is checked against its source (reuse) — is
  made on a **new, fresh offline load** of the cell by the canonical loader, the same one that builds the
  observation (`RealPilotOffline.ObserveCellAsync`: network blocked, shims of `pilot_rule.md` §2 (б), every target
  marker set by XPath, the cell's observation as the first walk of that load). It is never made on the page the
  observation was taken from, nor on a page kept open from an earlier evaluation.
- **Checkpoint.** On that load, before the evaluation, the observation sha256 must equal the pinned one
  (`observations_manifest.tsv`). The Oracle evaluation (`Oracle.EvaluateLocatorAsync`, resolution only) follows
  immediately. After it, the observation sha256 is computed again on the same load and must again equal the pinned
  one.
- **On a mismatch** (before or after): up to 3 new loads. If the third new load also mismatches, the run stops
  (exit 3) and no record is written. The model's answer stays in the journal and is replayed on the next start
  without a new (paid) request.
- **Reason.** The locator is scored against the same DOM state the model saw. On pages with timers (the review's
  wikipedia.org case: a 1 s timer adds a class to `<body>`), scoring after the model's latency, or on an aged page,
  can make the same locator succeed or fail depending on time.
- **Not changed.** Page timers are not stopped or frozen; the registered protocol (`pilot_rule.md` §2 (б): `Date` and
  `Math.random` fixed, timers keep running) is unchanged. The checkpoint only fixes *when* the evaluation happens.

## (б) Release liability

- When a request with unknown outcome (pending or error without a response) is released by the operator, the upper
  bound of its reservation (its reserved input tokens, plus the maximum output tokens, at list price) is added to
  the spent amount as a **budget liability** and counts towards the hard cap (USD 114.34), for the rest of the run.
- The new attempt for the same event makes its own reservation; the cap check before it includes the liability.
- The budget is therefore: Σ API-reported usage of all responses + Σ liability of released requests.
- The release itself is unchanged: only with `--plan pilot --execute`, the confirmation and `BAR_BATCH_RELEASE`; it
  records the release and stops before any request.

## (в) Procedural departure A1

- The final `targets.json` (326 targets on 33 sites, including 10 new targets on kaspersky.com) was committed in
  `83cdb27` together with the observation dumps, not before them, as `pilot_analysis_plan.md` ("committed before the
  observation dump") requires.
- The selection algorithm was fixed before (commit `ea2034c` and `pilot_rule.md`). Independent recomputation gives
  326/326 identical targets (both pre-run reviews).
- This departure is declared in the pilot report. It is not corrected retroactively.

## (г) Reservation framing tokens

- The runner reserves **64** chat-format framing tokens per request; the registered stop rule names 16.
- The larger reservation is more conservative and does not change the request. Worst case of the full plan with 64:
  50,435,050 + 1,476 × 64 input tokens and 1,476 × 256 output tokens = **USD 104.08 < 114.34** (hard cap).
- Declared in the pilot report as a departure.
