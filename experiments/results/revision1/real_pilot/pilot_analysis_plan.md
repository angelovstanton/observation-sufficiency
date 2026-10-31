# Real-site pilot: analysis plan (pre-registered)

Status: committed together with `pilot_rule.md`, **before** any processing of the sites and before
any model call. Nothing outside this plan is computed for the pilot claim: no other metrics,
thresholds or exclusions.

## Cells and model

- Primary cells: {B_full, B_noVolatile} × {F1, F3}. B_noVolatile is the NVC path with the
  Oracle-determined lists (`pilot_rule.md` §6).
- Sensitivity cells: class-only (`B_full_minus_volClass`) × {F1, F3}.
- Model: gpt-4.1 (the corpus deployment, `BAR_MODEL_DEPLOYMENT_1`), temperature 0, max output
  tokens 256 (`shared/harness/LlmClient.cs`).
- Prompt: the corpus prompt, unchanged (`GroundingRunner.SystemPrompt` + `BuildUserPrompt`), with
  the template task of `pilot_rule.md` §5.
- One generation per (target × cell).
- Sites and targets: as selected by `pilot_rule.md` (`targets.json`, committed before the
  observation dump). The cost cap, if needed, applies by Tranco rank (`pilot_rule.md` §2).

## Scoring

- The locator is evaluated, resolution only, on the May page loaded with the pilot adapter
  (offline, shims on, markers set by XPath), by the frozen Oracle (`Oracle.EvaluateLocatorAsync`).
  The inputs are the page's Oracle-determined lists (§6 of the rule) and the target's
  `signal_attrs` (§7 of the rule).
- **P5**: the frozen five-condition predicate (`success`).
- **P_now**: conditions 1 + 2 (unique match AND matches the oracle element).

## Primary analysis

For each encoding (F1, F3), each metric (P5, P_now) and each stratum ("has stable signal", "no
stable signal") **separately**, the pairs are B_full vs B_noVolatile on the same target:

- Success rates of both cells and their difference Δ = P(B_noVolatile) − P(B_full).
- McNemar on the pairs: `mcnemar()` from `p1/analysis/revision1_diagnostics.py`, the corpus
  routine. It reports discordant counts b (B_noVolatile-only) and c (B_full-only), the
  uncorrected χ², the exact binomial p and the OR with its exact CI, as that routine reports them.
- A 95% CI for Δ by a **site-clustered percentile bootstrap**: `page_bootstrap` / `pct_ci` from
  `revision1_diagnostics.py`, 10,000 replicates, seed 42, clusters = sites in Tranco rank order.
  Replicates in which the stratum is empty are undefined; they are excluded and their number is
  reported.

## Interpretation (fixed now)

- What is reported is the **direction** of Δ and whether it matches the corpus:
  - stratum "has stable signal": the corpus pattern is P5 ↑ and P_now ≈ 0;
  - stratum "no stable signal": the corpus pattern is P_now ↓.
- No claim is made that the effect size transfers from the corpus to real sites.

## Secondary: survival

- The generated locator is executed (resolution only) on the **September** DOM (CC-MAIN-2026-39
  record of the same domain), loaded with the same adapter: offline, shims on, clock at the
  September record's timestamp.
- The target in September is the element with the **same role and the same accessible name**,
  computed by the same functions (`rp_candidates.js`, the role table of the rule's §5), if that
  element is unique.
- If no unique such element exists, survival is **undefined** for that target. It is excluded
  from this measure and counted.
- The measure is the share of locators that resolve to exactly that element (unique match),
  reported per cell.

## Sensitivity

The same primary analysis, with B_full vs class-only (`B_full_minus_volClass`) in place of
B_full vs B_noVolatile (`pilot_rule.md` §6).

## Not done

No other metrics, thresholds or exclusions. No manual removal of sites or targets. No re-runs to
replace failed calls beyond the harness's existing behaviour. Any departure is reported as a
departure.

## Addendum (2026-10-12): scope, class_only reuse, hard cap

Author's decision. Written and committed after the preparation (eligibility, targets, observation dump, cost
estimate; `prep_report.md`) and **before any model call**. The rule (`pilot_rule.md`), the sites and the targets
(`targets.json`, commit `ea2034c`) are unchanged.

- **Sites.** Every eligible site, with no rank cut. This replaces the cost-cap clause of `pilot_rule.md` §2
  for this run.
  - Eligibility is as recorded in `eligibility.md`.
  - Criterion 2(б) (determinism) is applied to all dumps of a site, not only the two step-1 dumps.
  - On that basis wikipedia.org is excluded: its page sets a `<body>` class from a 1 s `setTimeout`.
  - Result: 31 sites and 306 targets. The targets of excluded sites stay in `targets.json` and are not called.
- **Primary cells.** B_full and B_noVolatile × F1 and F3, one call per target and cell.
- **Sensitivity cells, reuse rule.** class_only × F1 and F3 is called only for a site and encoding whose
  class_only observation differs from its B_noVolatile observation (sha256 in `observations_manifest.tsv`).
  - When the two observations are byte-identical, the prompt is identical too. The B_noVolatile result is then
    reused as the class_only result, with no call, as in the corpus NVC sensitivity.
  - Per this rule, class_only is called on 9 sites for F1 and 9 for F3, and reused elsewhere.
- **Hard cap.** USD 109.12, at the gpt-4.1 list price ($2.00 / 1M input, $8.00 / 1M output).
  - The cap is the pre-run upper bound plus 10%.
  - The upper bound is USD 99.20. It covers 1,396 calls and 48,146,912 input tokens (o200k_base,
    `CountTokens(SystemPrompt) + CountTokens(BuildUserPrompt(obs, task))`). Each call adds 16 chat-format
    tokens and 256 output tokens.
  - The figures are in `cost_estimate.json`.
  - The runner tracks the cumulative list-price cost from the API-reported prompt and completion tokens. It
    stops before any call whose upper bound (its input tokens + 16, plus 256 output tokens) would take the
    total above the cap.
  - Calls not made because of the cap are reported as such. They are not replaced.

## Addendum (2026-10-12): "no stable signal" stratum, descriptive only

Author's decision, committed before any model call. The rule and the target list are unchanged.

- After wikipedia.org was excluded, the stratum "no stable signal" holds 13 targets. That is too few for
  inference, so the stratum is reported **descriptively only**: counts and shares of P5 and P_now per cell
  (B_full, B_noVolatile, class_only × F1, F3).
- For this stratum there is **no McNemar and no CI**: no bootstrap, no OR, no p-value. Its direction relative to
  the corpus pattern is not tested and is not used for any conclusion.
- Conclusions about B_full vs B_noVolatile (and the class-only sensitivity) are drawn **only for the stratum
  "has stable signal"**, with the primary analysis above (paired McNemar and site-clustered bootstrap CI for Δ).

## Addendum (2026-10-13): final figures after the observation re-dump

Author's decision, committed before any model call. The earlier lines are kept as written; the figures below
replace the counts and the cap of the addendum of 2026-10-12 (scope, class_only reuse, hard cap). The rules are
unchanged. Source: `redump_report.md` (observation protocol of the `pilot_rule.md` addendum `1a16fa1`; criterion
(г) re-measured under that protocol per the addendum `60e2aaf`, with no site passing).

- **Sites.** 33 eligible sites. wikipedia.org and kaspersky.com enter: both pass 2(б) under the new protocol. No
  site leaves. publicnode.com, tradingview.com and zendesk.com stay excluded under (г).
- **Targets.** 326: 313 "has stable signal" and 13 "no stable signal". The "no stable signal" stratum stays
  descriptive only (addendum of 2026-10-12).
- **Calls.** 1,476: B_full and B_noVolatile × F1, F3, 326 each. class_only is called on 86 targets per encoding (9 sites for F1,
  9 for F3). 480 class_only results are reused from B_noVolatile under the reuse rule.
- **Input tokens.** 50,435,050 (o200k_base, `CountTokens(SystemPrompt) + CountTokens(BuildUserPrompt(obs, task))`).
- **Upper bound.** USD 103.94. Each call adds 16 chat-format tokens and 256 output tokens, at the gpt-4.1 list
  price ($2.00 / 1M input, $8.00 / 1M output).
- **Hard cap.** USD 114.34: the upper bound plus 10%, rounded up to the cent, under the rule of addendum
  `9f0bb2b`. The stop rule is unchanged.
- The figures are in `cost_estimate.json`, `pilot_plan.json` (`budget`, `counts`) and `redump_report.md`.

## Addendum (2026-10-14): interpretation rules, before the paid run

Author's decision, committed before the paid pilot run and before any pilot record exists (`batch_runs_pilot/` does
not exist). The rules and the figures above are unchanged. This registers three readings that the analysis code
(commit `34edebc`) fixes. The wording is quoted verbatim from the docstrings of `p1/analysis/revision1_pilot_analysis.py`
and `real_pilot/rp_survival.py`.

1. **Corpus pattern, stratum "has stable signal"** (section "Interpretation"). Verbatim from
   `revision1_pilot_analysis.py`: "Operational reading, fixed here before any outcome: P5 matches if Δ > 0;
   P_now matches "≈ 0" if the 95% bootstrap CI of Δ contains 0."
   - "P5 ↑" therefore means Δ > 0, and "P_now ≈ 0" means that the 95% CI of Δ contains 0.
   - The CI of Δ is reported for P5 as well.
2. **Same accessible name** (section "Secondary: survival"). Verbatim from `rp_survival.py`: "the September target is
   the candidate with the same role (pilot_rule.md §5 role table, rp_common.role_of) and the same accessible name
   (rp_candidates.js name, the identical normalized string), if exactly one candidate has both. Otherwise survival is
   undefined for that target: "absent" (no such candidate) or "ambiguous" (more than one)."
   - "Same name" therefore means the identical normalized string.
3. **Survival loading** (section "Secondary: survival"). Verbatim from `rp_survival.py`: "the adapter
   (REAL_PILOT=survival) loads the September page once per site (shims, September clock), marks every September
   target by its XPath and resolves the record's locator (Oracle.EvaluateLocatorAsync, resolution only). survived =
   unique match AND that element."
   - The September page is therefore loaded once per site, and all locators are evaluated on that load.

**Fact known before the paid run.** The September targets are pinned in `real_pilot/survival_targets.json`
(sha256 `6bdd67be22b43caa126305ab50784ff2136c46bce05e507bae8bd5dac70874db`, commit `34edebc`). They were produced by
`rp_survival.py prep`, and two independent probes agree on every target. Of 326 targets:

| result | targets |
|---|---|
| unique September target | 265 |
| absent | 51 |
| ambiguous | 10 |

For the 61 absent or ambiguous targets, survival is undefined; they are excluded from the measure and counted.
