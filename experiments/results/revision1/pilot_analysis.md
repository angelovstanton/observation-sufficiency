# Revision 1 — real-site pilot analysis

Zero LLM, zero network. Follows `real_pilot/pilot_analysis_plan.md` and its addenda (committed before any model call); this script was committed before any pilot record was read. Nothing outside the plan is computed for the pilot claim.

**Direction, not size.** What is reported is the direction of Δ and whether it matches the corpus pattern; no claim is made that the effect size transfers from the corpus to real sites. Conclusions about B_full vs B_noVolatile (and the class-only sensitivity) are drawn only for the stratum "has stable signal"; the stratum "no stable signal" is descriptive only.

Conventions: Δ = second − first (pp); 95% CI = site-clustered percentile bootstrap (10,000 replicates, seed 42, clusters = 33 sites in Tranco order; empty-stratum replicates excluded and counted); b = second-only, c = first-only; OR = b/c with exact conditional CI; p χ² = McNemar uncorrected; p exact = binomial. P5 = five-condition predicate; P_now = unique match ∧ matches oracle. Corpus pattern (has stable signal): P5 ↑ — read as Δ > 0; P_now ≈ 0 — read as 95% CI of Δ contains 0.

## Run

Records 1,956 / 1,956 expected (1,476 called, 480 reused class_only); missing 0 (not replaced; a pair needs both arms). Called records: prompt tokens 50,451,286, completion tokens 25,204, list price USD 101.104204 (cap 114.34).

Cost with release liability (addendum (е) point 4): called records USD 101.104204 + liability of 2 released key line(s) USD 0.137856 (Bound = reservation × 2 + 256 × 8 µUSD) = **USD 101.242060**.

| encoding | cell | present | expected |
|---|---|---|---|
| F1 | B_full | 326 | 326 |
| F1 | B_noVolatile | 326 | 326 |
| F1 | class_only | 326 | 326 |
| F3 | B_full | 326 | 326 |
| F3 | B_noVolatile | 326 | 326 |
| F3 | class_only | 326 | 326 |

Journal: 2,960 lines, sha256 `b55c0f0e6ed79cfce81d19c06128a6b7b213682ef139413a8fe9b600c1f1050a`; types {'error': 2, 'pending': 1479, 'rejected_429': 1, 'released': 2, 'response': 1476}; released keys 2.

## Primary — B_full vs B_noVolatile, stratum "has stable signal"

| comparison (second − first) | enc | pred | n | first % | second % | Δ pp | 95% CI (pp) | empty repl. | b/c | OR [95% CI] | p χ² | p exact | direction | matches corpus |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B_noVolatile vs B_full | F1 | P5 | 313 | 77.6 | 80.8 | +3.19 | [+0.00, +7.12] | 0 | 14/4 | 3.50 [1.10, 14.60] | 0.0184 | 0.0309 | + | True (↑ (Δ > 0)) |
| B_noVolatile vs B_full | F1 | P_now | 313 | 81.8 | 80.8 | -0.96 | [-2.58, +0.63] | 0 | 2/5 | 0.40 [0.04, 2.44] | 0.2568 | 0.4531 | − | True (≈ 0 (95% CI of Δ contains 0)) |
| B_noVolatile vs B_full | F3 | P5 | 313 | 76.0 | 81.5 | +5.43 | [+0.31, +12.01] | 0 | 25/8 | 3.12 [1.37, 8.02] | 0.0031 | 0.0046 | + | True (↑ (Δ > 0)) |
| B_noVolatile vs B_full | F3 | P_now | 313 | 82.1 | 81.5 | -0.64 | [-3.39, +1.90] | 0 | 7/9 | 0.78 [0.25, 2.35] | 0.6171 | 0.8036 | − | True (≈ 0 (95% CI of Δ contains 0)) |

## Sensitivity — B_full vs class_only, stratum "has stable signal"

| comparison (second − first) | enc | pred | n | first % | second % | Δ pp | 95% CI (pp) | empty repl. | b/c | OR [95% CI] | p χ² | p exact | direction | matches corpus |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| class_only vs B_full | F1 | P5 | 313 | 77.6 | 80.2 | +2.56 | [-0.93, +6.64] | 0 | 14/6 | 2.33 [0.84, 7.41] | 0.0736 | 0.1153 | + | True (↑ (Δ > 0)) |
| class_only vs B_full | F1 | P_now | 313 | 81.8 | 80.2 | -1.60 | [-3.44, +0.31] | 0 | 2/7 | 0.29 [0.03, 1.50] | 0.0956 | 0.1797 | − | True (≈ 0 (95% CI of Δ contains 0)) |
| class_only vs B_full | F3 | P5 | 313 | 76.0 | 81.2 | +5.11 | [+0.32, +11.58] | 0 | 24/8 | 3.00 [1.30, 7.72] | 0.0047 | 0.0070 | + | True (↑ (Δ > 0)) |
| class_only vs B_full | F3 | P_now | 313 | 82.1 | 81.2 | -0.96 | [-3.16, +1.28] | 0 | 6/9 | 0.67 [0.20, 2.10] | 0.4386 | 0.6072 | − | True (≈ 0 (95% CI of Δ contains 0)) |

## Stratum "no stable signal" — descriptive only (no McNemar, no CI, no direction test)

| enc | cell | n | P5 | P5 % | P_now | P_now % |
|---|---|---|---|---|---|---|
| F1 | B_full | 13 | 0 | 0.0 | 8 | 61.5 |
| F1 | B_noVolatile | 13 | 0 | 0.0 | 8 | 61.5 |
| F1 | class_only | 13 | 0 | 0.0 | 7 | 53.8 |
| F3 | B_full | 13 | 0 | 0.0 | 10 | 76.9 |
| F3 | B_noVolatile | 13 | 0 | 0.0 | 9 | 69.2 |
| F3 | class_only | 13 | 0 | 0.0 | 8 | 61.5 |

Stratum "has stable signal", per cell (shares, for reference):

| enc | cell | n | P5 | P5 % | P_now | P_now % |
|---|---|---|---|---|---|---|
| F1 | B_full | 313 | 243 | 77.6 | 256 | 81.8 |
| F1 | B_noVolatile | 313 | 253 | 80.8 | 253 | 80.8 |
| F1 | class_only | 313 | 251 | 80.2 | 251 | 80.2 |
| F3 | B_full | 313 | 238 | 76.0 | 257 | 82.1 |
| F3 | B_noVolatile | 313 | 255 | 81.5 | 255 | 81.5 |
| F3 | class_only | 313 | 254 | 81.2 | 254 | 81.2 |

## Secondary — survival (September, CC-MAIN-2026-39)

Targets without a unique September element (same role and name), survival undefined and excluded: {'absent': 51, 'ambiguous': 10} (`real_pilot/survival_targets.json`).

Share = survived / determined. Each attempt first checks the B_full × F1 pre-hash against the site's September reference (addenda (е), (е′); `real_pilot/survival_reference.json`, sha256 `d115fe48f201bea1e2291563d511efc0ca8ef6c16e0ae37c1965c364af79b1b3`). Undetermined = unstable September DOM after 5 fresh loads (addendum (д)); no reference = the site has no stable reference (addendum (е′)); both reported separately. Sites without a stable reference: ['0337_drom.ru'].

| enc | cell | records | defined | undefined | undetermined | no reference | determined | survived | broken | share % |
|---|---|---|---|---|---|---|---|---|---|---|
| F1 | B_full | 326 | 265 | 61 | 0 | 5 | 260 | 204 | 56 | 78.5 |
| F1 | B_noVolatile | 326 | 265 | 61 | 0 | 5 | 260 | 199 | 61 | 76.5 |
| F1 | class_only | 326 | 265 | 61 | 0 | 5 | 260 | 197 | 63 | 75.8 |
| F3 | B_full | 326 | 265 | 61 | 0 | 5 | 260 | 203 | 57 | 78.1 |
| F3 | B_noVolatile | 326 | 265 | 61 | 0 | 5 | 260 | 202 | 58 | 77.7 |
| F3 | class_only | 326 | 265 | 61 | 0 | 5 | 260 | 202 | 58 | 77.7 |

## Per site (descriptive): successes per cell

| site | enc | B_full n / P5 / P_now | B_noVolatile n / P5 / P_now | class_only n / P5 / P_now |
|---|---|---|---|---|
| 0029_github.com | F1 | 10 / 8 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0029_github.com | F3 | 10 / 9 / 10 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0031_wikipedia.org | F1 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0031_wikipedia.org | F3 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0049_wordpress.org | F1 | 10 / 8 / 8 | 10 / 8 / 8 | 10 / 8 / 8 |
| 0049_wordpress.org | F3 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0109_triplinkintl.com | F1 | 10 / 10 / 10 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0109_triplinkintl.com | F3 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0129_dropbox.com | F1 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 8 / 8 |
| 0129_dropbox.com | F3 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0131_intuit.com | F1 | 10 / 8 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0131_intuit.com | F3 | 10 / 7 / 10 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0142_afternic.com | F1 | 10 / 3 / 6 | 10 / 4 / 7 | 10 / 4 / 6 |
| 0142_afternic.com | F3 | 10 / 4 / 7 | 10 / 4 / 7 | 10 / 4 / 6 |
| 0146_kaspersky.com | F1 | 10 / 8 / 9 | 10 / 8 / 8 | 10 / 8 / 8 |
| 0146_kaspersky.com | F3 | 10 / 5 / 8 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0150_godaddy.com | F1 | 10 / 5 / 6 | 10 / 6 / 6 | 10 / 6 / 6 |
| 0150_godaddy.com | F3 | 10 / 5 / 7 | 10 / 6 / 6 | 10 / 6 / 6 |
| 0160_criteo.com | F1 | 10 / 8 / 8 | 10 / 8 / 8 | 10 / 7 / 7 |
| 0160_criteo.com | F3 | 10 / 8 / 8 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0162_webex.com | F1 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0162_webex.com | F3 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0167_hichina.com | F1 | 6 / 6 / 6 | 6 / 5 / 5 | 6 / 5 / 5 |
| 0167_hichina.com | F3 | 6 / 6 / 6 | 6 / 6 / 6 | 6 / 6 / 6 |
| 0170_shopify.com | F1 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0170_shopify.com | F3 | 10 / 8 / 8 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0176_discord.com | F1 | 10 / 4 / 4 | 10 / 4 / 4 | 10 / 4 / 4 |
| 0176_discord.com | F3 | 10 / 4 / 4 | 10 / 4 / 4 | 10 / 4 / 4 |
| 0206_telegram.org | F1 | 10 / 7 / 7 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0206_telegram.org | F3 | 10 / 8 / 8 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0227_cisco.com | F1 | 10 / 10 / 10 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0227_cisco.com | F3 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0232_nist.gov | F1 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0232_nist.gov | F3 | 10 / 8 / 8 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0256_hubspot.com | F1 | 10 / 5 / 6 | 10 / 5 / 6 | 10 / 5 / 6 |
| 0256_hubspot.com | F3 | 10 / 5 / 6 | 10 / 6 / 7 | 10 / 6 / 7 |
| 0266_spectrum.com | F1 | 10 / 7 / 7 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0266_spectrum.com | F3 | 10 / 7 / 7 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0278_dnsmadeeasy.com | F1 | 10 / 3 / 3 | 10 / 3 / 3 | 10 / 3 / 3 |
| 0278_dnsmadeeasy.com | F3 | 10 / 3 / 3 | 10 / 3 / 3 | 10 / 3 / 3 |
| 0309_inmobi.com | F1 | 10 / 5 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0309_inmobi.com | F3 | 10 / 1 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0314_ok.ru | F1 | 10 / 8 / 9 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0314_ok.ru | F3 | 10 / 8 / 9 | 10 / 10 / 10 | 10 / 8 / 8 |
| 0324_appsflyer.com | F1 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0324_appsflyer.com | F3 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0337_drom.ru | F1 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0337_drom.ru | F3 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0356_nasa.gov | F1 | 10 / 8 / 8 | 10 / 8 / 8 | 10 / 8 / 8 |
| 0356_nasa.gov | F3 | 10 / 8 / 8 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0357_mobile.de | F1 | 10 / 6 / 9 | 10 / 6 / 9 | 10 / 7 / 10 |
| 0357_mobile.de | F3 | 10 / 7 / 10 | 10 / 5 / 8 | 10 / 7 / 10 |
| 0365_checkpoint.com | F1 | 10 / 9 / 9 | 10 / 8 / 8 | 10 / 8 / 8 |
| 0365_checkpoint.com | F3 | 10 / 9 / 9 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0379_plesk.com | F1 | 10 / 8 / 8 | 10 / 8 / 8 | 10 / 8 / 8 |
| 0379_plesk.com | F3 | 10 / 8 / 8 | 10 / 9 / 9 | 10 / 9 / 9 |
| 0381_issuu.com | F1 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0381_issuu.com | F3 | 10 / 10 / 10 | 10 / 10 / 10 | 10 / 10 / 10 |
| 0382_datadoghq.com | F1 | 10 / 8 / 9 | 10 / 8 / 8 | 10 / 8 / 8 |
| 0382_datadoghq.com | F3 | 10 / 7 / 8 | 10 / 8 / 9 | 10 / 8 / 9 |
| 0385_stanford.edu | F1 | 10 / 8 / 8 | 10 / 9 / 9 | 10 / 8 / 8 |
| 0385_stanford.edu | F3 | 10 / 8 / 8 | 10 / 9 / 9 | 10 / 8 / 8 |
| 0399_doubleverify.com | F1 | 10 / 6 / 6 | 10 / 6 / 6 | 10 / 6 / 6 |
| 0399_doubleverify.com | F3 | 10 / 7 / 7 | 10 / 7 / 7 | 10 / 7 / 7 |
| 0418_unsplash.com | F1 | 10 / 2 / 5 | 10 / 4 / 5 | 10 / 4 / 5 |
| 0418_unsplash.com | F3 | 10 / 1 / 4 | 10 / 4 / 5 | 10 / 4 / 5 |
