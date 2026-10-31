# Real-site pilot: addendum (а″) and (д) — warm-up, five attempts, survival on a fresh load per locator

Author's decision (2026-10-14). Committed **before** the code that implements it, before the paid pilot
run, and before any pilot record exists (`batch_runs_pilot/` does not exist). It amends addendum (а′)
(`pilot_addendum_scoring_a2.md`, commit `3534720`) and the survival reading of the analysis-plan addendum of
2026-10-14 (`pilot_analysis_plan.md`, commit `0f664c7`, point 3). Everything not named here is unchanged; the plan
(`pilot_plan.json`, `b79364225b5e…`) and the observation protocol are unchanged.

## (а″) Warm-up and five attempts (amends (а′))

**Why.** The offline feasibility test of (а′) (no model): on mobile.de, 49 of 50
evaluations passed within 3 attempts in one series; the evaluations that needed retries clustered at the first
evaluation after the browser started (cold start). A cold start is an artefact of the harness, not a property of the
site.

- **Warm-up.** After every start of the browser, one warm-up load of the same cell (the cell of the first evaluation)
  is made by the same loader. It is not evaluated and not recorded.
- **Attempts.** At most **5** fresh loads per evaluation (was: the first + 3 new). After 5 failed attempts: exit 3, no
  record, as before. Never a silently different result.
- **Feasibility requirement before the code is committed.** wikipedia.org, kaspersky.com, mobile.de × 50 evaluations
  × 2 series, each series starting with a cold browser: 100% within ≤ 5 attempts and 0 exit 3.
- **No-write test.** The observation walk and the Oracle evaluation do not write to the DOM: a mutation window around
  the walk and the evaluation alone counts 0 records on the 3 sites and on 2 testbed pages.

## (д) Survival: fresh load per locator, same mutation window (amends 0f664c7 point 3)

**Why.** An offline check (no model): the registered survival step loads the September page once per site and
resolves every locator in sequence on that live DOM. On wikipedia.org (September) a locator with an ancestor-state
condition (`body:not(.jsl10n-visible) …`) survives or not depending on its position in the sequence and on time
(8 differences among 1,032 synthetic locators on 33 sites: as-is order vs +5 s vs reversed order). The survival
comparison May → September is fair only if the September locator is evaluated at the same point as the May data:
immediately after the load, on a DOM that does not move.

- **Load.** Every locator is evaluated on a **new fresh load** of the September page: the same loader, the same shims
  (clock at the September record), the same network blocking. Without the XPath markers from the preparation.
- **Target.** Found on that load by role + accessible name as before (`rp_candidates.js`; role by the role table of
  `pilot_rule.md` §5, the same function as `rp_common.role_of`; the identical normalized name; exactly one
  candidate). If not exactly one candidate is found on that load, the attempt fails.
- **Window.** The mutation window of (а′) is opened **before** the target is searched. Inside it: the target search;
  the Oracle marker `data-oracle-id` set on the element found by role + name (the frozen `Oracle.EvaluateLocatorAsync`
  decides "matches the target" by this attribute); the Oracle evaluation (resolution only); then, synchronously, the
  records delivered so far + `takeRecords()` + shadow roots attached in the window.
- **The one excluded record.** Exactly one record is excluded: `type == "attributes"`,
  `attributeName == "data-oracle-id"`, `target ===` the element found. If there are 0 or more than 1 such records, the
  attempt fails (retry); nothing else is excluded. Every other record — including another attribute of the same
  element — counts as a mutation. The attempt counts only if the remaining count is 0.
- **Warm-up and attempts.** One warm-up load after every browser start (not evaluated); at most 5 attempts per locator.
- **Unstable DOM.** If no attempt counts after 5, the locator is **"survival undetermined (unstable DOM)"**: counted
  and reported separately from survived / broken / undefined (no unique September target). It is not an exit: survival
  is an offline analysis. The share of survived locators is taken over the locators whose survival was determined; the
  undetermined ones are reported per cell.
- **Tests required.** On 2 stable sites the window gives exactly 1 excluded record and 0 others; on wikipedia with a
  forced wait inside the window the check catches the mutation. The check that found the 8 differences, run again on
  the new code (as-is / +5 s before each locator / reversed order), gives 0 differences.
