# Real-site pilot — exploratory analysis

**EXPLORATORY — not pre-registered, computed after the registered results (f6a00d3).**

Not part of the registered analysis (`pilot_analysis.md`); no new model calls; the registered script is unchanged. Inputs: records `batch_runs_pilot/` (pins and checks of `revision1_pilot_analysis.py`), `pilot_survival.tsv` (sha256 `45a59643569a1d0a048782b31c381742b38650f33896d7882f3e8d4b86ec08de`), May / September probe candidates (RP_CACHE `probe/`, `survival_probe_1/`; combined sha256 `e1fa955fb1c82c0d…` / `37a19aaaa29aba26…`). Determined survival = survived + broken (no-reference drom.ru and undefined targets excluded).

## 1. Survival by May outcome

Share survived (%) among determined locators whose May record had the predicate true vs false. Wilson 95% CI per share; difference (true − false, pp) with the Newcombe hybrid-score 95% CI. All strata.

**P5**

| enc | cell | n P5=T | surv % (CI) | n P5=F | surv % (CI) | Δ pp [95% CI] |
|---|---|---|---|---|---|---|
| F1 | B_full | 198 | 94.4 [90.3, 96.9] | 62 | 27.4 [17.9, 39.6] | +67.0 [+54.2, +76.9] |
| F1 | B_noVolatile | 205 | 93.7 [89.5, 96.3] | 55 | 12.7 [6.3, 24.0] | +80.9 [+68.9, +87.9] |
| F1 | class_only | 204 | 93.6 [89.4, 96.2] | 56 | 10.7 [5.0, 21.5] | +82.9 [+71.4, +89.2] |
| F3 | B_full | 191 | 93.7 [89.3, 96.4] | 69 | 34.8 [24.6, 46.6] | +58.9 [+46.4, +69.4] |
| F3 | B_noVolatile | 208 | 93.8 [89.6, 96.3] | 52 | 13.5 [6.7, 25.3] | +80.3 [+67.8, +87.5] |
| F3 | class_only | 207 | 94.2 [90.1, 96.7] | 53 | 13.2 [6.5, 24.8] | +81.0 [+68.7, +88.1] |

**P_now**

| enc | cell | n P_now=T | surv % (CI) | n P_now=F | surv % (CI) | Δ pp [95% CI] |
|---|---|---|---|---|---|---|
| F1 | B_full | 216 | 94.4 [90.5, 96.8] | 44 | 0.0 [0.0, 8.0] | +94.4 [+85.5, +96.8] |
| F1 | B_noVolatile | 213 | 93.4 [89.3, 96.0] | 47 | 0.0 [0.0, 7.6] | +93.4 [+84.8, +96.0] |
| F1 | class_only | 211 | 93.4 [89.2, 96.0] | 49 | 0.0 [0.0, 7.3] | +93.4 [+85.0, +96.0] |
| F3 | B_full | 218 | 93.1 [89.0, 95.8] | 42 | 0.0 [0.0, 8.4] | +93.1 [+83.8, +95.8] |
| F3 | B_noVolatile | 216 | 93.5 [89.4, 96.1] | 44 | 0.0 [0.0, 8.0] | +93.5 [+84.5, +96.1] |
| F3 | class_only | 214 | 93.9 [89.9, 96.4] | 46 | 2.2 [0.4, 11.3] | +91.8 [+81.7, +94.8] |

Same, stratum "has stable signal" only (P5):

| enc | cell | n P5=T | surv % (CI) | n P5=F | surv % (CI) | Δ pp [95% CI] |
|---|---|---|---|---|---|---|
| F1 | B_full | 198 | 94.4 [90.3, 96.9] | 50 | 20.0 [11.2, 33.0] | +74.4 [+60.8, +83.5] |
| F1 | B_noVolatile | 205 | 93.7 [89.5, 96.3] | 43 | 0.0 [0.0, 8.2] | +93.7 [+84.4, +96.3] |
| F1 | class_only | 204 | 93.6 [89.4, 96.2] | 44 | 0.0 [0.0, 8.0] | +93.6 [+84.6, +96.2] |
| F3 | B_full | 191 | 93.7 [89.3, 96.4] | 57 | 26.3 [16.6, 39.0] | +67.4 [+54.0, +77.4] |
| F3 | B_noVolatile | 208 | 93.8 [89.6, 96.3] | 40 | 0.0 [0.0, 8.8] | +93.8 [+84.1, +96.3] |
| F3 | class_only | 207 | 94.2 [90.1, 96.7] | 41 | 2.4 [0.4, 12.6] | +91.8 [+80.8, +94.9] |

## 2. Why 353 locators broke

353 locators broke on the September pages; 271 of them were already wrong in May (P_now false).

Broken per cell: F1 B_full 56, F1 B_noVolatile 61, F1 class_only 63, F3 B_full 57, F3 B_noVolatile 58, F3 class_only 58.

Broken per site (top 10): 0176_discord.com 36, 0029_github.com 28, 0150_godaddy.com 23, 0142_afternic.com 21, 0382_datadoghq.com 21, 0399_doubleverify.com 21, 0146_kaspersky.com 16, 0379_plesk.com 16, 0160_criteo.com 15, 0206_telegram.org 14.

Locator kind = the signals the locator uses on the target element: id, data (data-*), aria (aria-* / role), attr (any other attribute: href, title, alt, placeholder, …), class, text; structural = none of these. Change = the first that holds, in this order: the locator was not P_now in May (it never resolved uniquely to the target); a used attribute present on the May target is absent on the September target; its value no longer satisfies the locator; the text condition fails; the locator has ancestors / position and the target's parent or index changed; another September candidate matches the target compound; otherwise unclassified. Attributes from the probe candidates (interactive elements only); ancestors are compared by XPath only.

Columns: wrong in May = wrong already in May (P_now false); attr missing = attribute missing in September; value changed = attribute value changed; text changed = text changed; parent / position = parent / position changed; not unique = no longer unique (another element matches); unclassified = unclassified (target still matches; non-candidate element).

| kind \ change | wrong in May | attr missing | value changed | text changed | parent / position | not unique | unclassified | total |
|---|---|---|---|---|---|---|---|---|
| attr | 140 | 0 | 15 | 0 | 0 | 4 | 3 | 162 |
| attr+class | 47 | 14 | 25 | 0 | 0 | 0 | 0 | 86 |
| class | 22 | 0 | 2 | 0 | 0 | 0 | 0 | 24 |
| aria | 15 | 0 | 2 | 0 | 0 | 0 | 0 | 17 |
| data+attr | 10 | 0 | 7 | 0 | 0 | 0 | 0 | 17 |
| class+text | 11 | 0 | 0 | 0 | 0 | 0 | 0 | 11 |
| id | 2 | 0 | 0 | 0 | 0 | 0 | 6 | 8 |
| aria+class | 5 | 0 | 2 | 0 | 0 | 0 | 0 | 7 |
| aria+text | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| aria+attr+text | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 5 |
| id+aria+attr+text | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 |
| aria+attr | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| id+attr | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 2 |
| attr+class+text | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| structural | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| **total** | 271 | 14 | 55 | 0 | 0 | 4 | 9 | 353 |

Broken locators that were correct in May (P_now true): attr missing 14, value changed 55, text changed 0, parent / position 0, not unique 4, unclassified 9.

Attributes behind "missing" / "value changed": {'class': 42, 'href': 17, 'title': 12, 'aria-controls': 2, 'id': 2}.

## 3. Leave-one-site-out — Δ P5 (B_noVolatile − B_full), stratum "has stable signal"

| enc | pairs | Δ all pp | LOSO min | LOSO max | sites driving Δ (shift when left out) | sites Δ>0 / =0 / <0 |
|---|---|---|---|---|---|---|
| F1 | 313 | +3.19 | +1.98 (without 0309_inmobi.com) | +3.63 (without 0109_triplinkintl.com) | 0309_inmobi.com (-1.21), 0418_unsplash.com (-0.56), 0131_intuit.com (-0.55) | 8 / 21 / 4 |
| F3 | 313 | +5.43 | +2.97 (without 0309_inmobi.com) | +6.21 (without 0357_mobile.de) | 0309_inmobi.com (-2.46), 0418_unsplash.com (-0.83), 0131_intuit.com (-0.48) | 11 / 17 / 5 |

Per-site paired P5 counts (sites with Δ ≠ 0):

| site | F1 B_full / NVC (Δ) | F3 B_full / NVC (Δ) |
|---|---|---|
| 0029_github.com | 8 / 9 (+1) | 9 / 9 (+0) |
| 0109_triplinkintl.com | 10 / 9 (-1) | 10 / 10 (+0) |
| 0131_intuit.com | 8 / 10 (+2) | 7 / 9 (+2) |
| 0142_afternic.com | 3 / 4 (+1) | 4 / 4 (+0) |
| 0146_kaspersky.com | 8 / 8 (+0) | 5 / 7 (+2) |
| 0150_godaddy.com | 5 / 6 (+1) | 5 / 6 (+1) |
| 0160_criteo.com | 8 / 8 (+0) | 8 / 7 (-1) |
| 0167_hichina.com | 6 / 5 (-1) | 6 / 6 (+0) |
| 0170_shopify.com | 9 / 9 (+0) | 8 / 9 (+1) |
| 0206_telegram.org | 7 / 7 (+0) | 8 / 7 (-1) |
| 0227_cisco.com | 10 / 9 (-1) | 10 / 10 (+0) |
| 0232_nist.gov | 9 / 9 (+0) | 8 / 7 (-1) |
| 0256_hubspot.com | 5 / 5 (+0) | 5 / 6 (+1) |
| 0309_inmobi.com | 5 / 9 (+4) | 1 / 9 (+8) |
| 0314_ok.ru | 8 / 10 (+2) | 8 / 10 (+2) |
| 0356_nasa.gov | 8 / 8 (+0) | 8 / 7 (-1) |
| 0357_mobile.de | 6 / 6 (+0) | 7 / 5 (-2) |
| 0365_checkpoint.com | 9 / 8 (-1) | 9 / 9 (+0) |
| 0379_plesk.com | 8 / 8 (+0) | 8 / 9 (+1) |
| 0382_datadoghq.com | 8 / 8 (+0) | 7 / 8 (+1) |
| 0385_stanford.edu | 8 / 9 (+1) | 8 / 9 (+1) |
| 0418_unsplash.com | 2 / 4 (+2) | 1 / 4 (+3) |

## 4. Survival paired — B_full vs B_noVolatile (same target, both determined)

b = survived only with B_noVolatile, c = survived only with B_full; McNemar uncorrected χ² and exact p; OR = b/c with the exact conditional CI.

| enc | pairs | B_full surv % | NVC surv % | Δ pp | b/c | OR [95% CI] | p χ² | p exact |
|---|---|---|---|---|---|---|---|---|
| F1 | 260 | 78.5 | 76.5 | -1.92 | 3/8 | 0.38 [0.06, 1.56] | 0.1317 | 0.2266 |
| F3 | 260 | 78.1 | 77.7 | -0.38 | 10/11 | 0.91 [0.35, 2.36] | 0.8273 | 1.0000 |

## 5. Input tokens per cell

observation_tokens = the observation measured with the fixed tokenizer (o200k_base), every record (326 per cell; a reused class_only record carries its byte-identical observation). Prompt tokens = API prompt tokens of called records only.

| enc | cell | n | mean obs tokens | median obs tokens | called | mean API prompt tokens |
|---|---|---|---|---|---|---|
| F1 | B_full | 326 | 38,738 | 33,339 | 326 | 38,830 |
| F1 | B_noVolatile | 326 | 35,713 | 32,194 | 326 | 35,805 |
| F1 | class_only | 326 | 35,717 | 32,194 | 86 | 46,147 |
| F3 | B_full | 326 | 30,446 | 26,651 | 326 | 30,538 |
| F3 | B_noVolatile | 326 | 27,529 | 25,661 | 326 | 27,621 |
| F3 | class_only | 326 | 27,532 | 25,661 | 86 | 37,114 |

Saving = 1 − mean(second) / mean(first) on the observation tokens; also the median of the per-target savings (same target, 1 − second / first).

| comparison | saving % | median per target % |
|---|---|---|
| F3 vs F1, B_full | 21.4 | 18.8 |
| F3 vs F1, B_noVolatile | 22.9 | 19.8 |
| F3 vs F1, class_only | 22.9 | 19.8 |
| B_noVolatile vs B_full, F1 | 7.8 | 1.1 |
| class_only vs B_full, F1 | 7.8 | 1.1 |
| B_noVolatile vs B_full, F3 | 9.6 | 1.4 |
| class_only vs B_full, F3 | 9.6 | 1.4 |

## 6. Survival among locators correct in May (P_now = true): P5 = true vs P5 = false

**EXPLORATORY — not pre-registered, computed after the registered results (f6a00d3).** Determined locators only. Δ = survived % (P5 true) − survived % (P5 false), Newcombe hybrid-score 95% CI; Fisher exact two-sided p. P5 = false with P_now = true means the locator resolved to the target but failed condition 3 / 4 (volatile or positional: "grabbed") or condition 5 (no-signal targets). The pooled rows count each target once per cell (up to 6 times), so they are not independent; their CI and p are descriptive.

| enc | cell | scope | n P5=T | surv % | n P5=F | surv % | Δ pp [95% CI] | Fisher p | P5=F: no-signal / grabbed |
|---|---|---|---|---|---|---|---|---|---|
| F1 | B_full | all strata | 198 | 94.4 | 18 | 94.4 | +0.0 [-6.1, +20.3] | 1.0000 | 7 / 11 |
| F1 | B_noVolatile | all strata | 205 | 93.7 | 8 | 87.5 | +6.2 [-4.9, +40.8] | 0.4250 | 8 / 0 |
| F1 | class_only | all strata | 204 | 93.6 | 7 | 85.7 | +7.9 [-4.5, +45.0] | 0.3860 | 7 / 0 |
| F3 | B_full | all strata | 191 | 93.7 | 27 | 88.9 | +4.8 [-3.6, +22.0] | 0.4071 | 9 / 18 |
| F3 | B_noVolatile | all strata | 208 | 93.8 | 8 | 87.5 | +6.2 [-4.8, +40.9] | 0.4203 | 8 / 0 |
| F3 | class_only | all strata | 207 | 94.2 | 7 | 85.7 | +8.5 [-3.9, +45.6] | 0.3593 | 7 / 0 |
| all | all cells | all strata | 1213 | 93.9 | 75 | 89.3 | +4.6 [-0.8, +13.6] | 0.1373 | 46 / 29 |
| all | all cells | has stable signal | 1213 | 93.9 | 29 | 86.2 | +7.7 [-0.7, +24.5] | 0.1034 | 0 / 29 |

## 7. COP (B_noVolatile × F3) vs naive (B_full × F1) — paired, stratum "has stable signal"

**EXPLORATORY — not pre-registered, computed after the registered results (f6a00d3).** **This comparison is not in the registered plan** (the plan compares bundles within one encoding); it changes bundle and encoding at once. Same target in both arms. Δ = COP − naive (pp); McNemar b = COP-only, c = naive-only, exact p; 95% CI = site-clustered percentile bootstrap (10,000, seed 42, 33 sites in Tranco order), as in the registered analysis.

| metric | n | naive % | COP % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p exact | p χ² |
|---|---|---|---|---|---|---|---|---|---|
| P5 | 313 | 77.6 | 81.5 | +3.83 | [+0.00, +7.79] | 23/11 | 2.09 [0.98, 4.75] | 0.0576 | 0.0396 |
| P_now | 313 | 81.8 | 81.5 | -0.32 | [-3.19, +2.24] | 11/12 | 0.92 [0.37, 2.27] | 1.0000 | 0.8348 |

Input tokens over the same pairs (observation = fixed tokenizer o200k_base; API prompt tokens, both arms called):

| tokens | naive mean | naive median | COP mean | COP median | saving % (means) | median per-target saving % |
|---|---|---|---|---|---|---|
| observation | 38,483 | 33,339 | 27,359 | 25,661 | 28.9 | 22.4 |
| API prompt | 38,575 | 33,430 | 27,451 | 25,753 | 28.8 | 22.3 |
