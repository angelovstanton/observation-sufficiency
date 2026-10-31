# Revision 1 — batch analysis

Zero LLM, zero network. Follows `batch_analysis_plan.md` (committed before any outcome was read); anything else is under **Exploratory**. Plan `batch_plan.json` sha256 `567c370855a29bf641a8d809a73fb433f217207b087fc62cb2c61ec70402353f`; `journal.jsonl` sha256 `e7984c9f4388d23b42006a12c04ad7cae2e7073500b62c1e4bb720b07dac93f9`.

Conventions: Δ = second − first, in percentage points; 95% CI = page-clustered percentile bootstrap (10,000 draws, seed 42); b = second-only successes, c = first-only; OR = b/c with exact conditional 95% CI; p χ² = McNemar uncorrected, p exact = binomial on b/(b+c). P5 = five-condition predicate (primary); P_now = unique match ∧ matches oracle (secondary). Strata from `shared/testbed/pages/*.truth.json` (no_attribute_signal = NONE + text-only targets; P5 is 0 there by construction). gpt-4.1 / gpt-4.1-nano at temperature 0; o4-mini at the service default.

Holm (plan § Multiplicity): one set per (family, predicate, stratum), on p χ² and on p exact. Rows whose two arms are both original corpus records show raw p only (`raw only`). Undefined p (no discordant pairs) → n/a, not in the set. Subset rows of F2 (minus_aria remaining / flipped targets) are their own sets of size 1. Both F4 o4-mini rows (all events, without re-issued) are in the F4 set. Set sizes: F1|P5|has_attribute_signal = 9, F1|P5|overall = 9, F1|P_now|has_attribute_signal = 9, F1|P_now|no_attribute_signal = 9, F1|P_now|overall = 9, F2|P5|has_attribute_signal = 3, F2|P5|overall = 3, F2|P_now|has_attribute_signal = 3, F2|P_now|no_attribute_signal = 3, F2|P_now|overall = 3, F2-sub|P5|has_attribute_signal = 1, F2-sub|P5|overall = 1, F2-sub|P_now|has_attribute_signal = 1, F2-sub|P_now|no_attribute_signal = 1, F2-sub|P_now|overall = 1, F2-sub45|P5|has_attribute_signal = 1, F2-sub45|P5|overall = 1, F2-sub45|P_now|has_attribute_signal = 1, F2-sub45|P_now|overall = 1, F3|P5|has_attribute_signal = 6, F3|P5|overall = 6, F3|P_now|has_attribute_signal = 6, F3|P_now|no_attribute_signal = 6, F3|P_now|overall = 6, F4|P5|has_attribute_signal = 2, F4|P5|overall = 2, F4|P_now|has_attribute_signal = 2, F4|P_now|no_attribute_signal = 2, F4|P_now|overall = 2.

## Data

4,500 batch records (blocks 1: 660, 2: 720, 3: 2,880, 4: 240); every plan key ends in a journaled response; journal 9,054 lines (error 4, pending 4525, rejected_429 20, released 5, response 4500). Observation sha256 of every record equals the audited manifest. Block-1 reused cells are rebuilt from the corpus records they reuse (B_full_minus_state = B_noState×F1 on 24 pages; minus_volClass pages 02/04/12/19 and minus_volId pages 03/07 = B_full×F1).

Re-issued after client timeout / provider error (journal `released`, equal to `released_keys.md`: True): 5 — by block 1: 1, 2: 0, 3: 2, 4: 2. Keys: `gpt-4.1|B_full_minus_volClass|F1|page_06|t_03|0`; `gpt-4.1|B_noVolatile|F1|page_09|t_01|1`; `gpt-4.1|B_noVolatile|F1|page_22|t_10|1`; `o4-mini|B_full|F1|page_01|t_10|0`; `o4-mini|B_full|F1|page_02|t_09|0`.

## Controls

| control | recomputed | expected | ok |
|---|---|---|---|
| corpus: gpt-4.1 COP − B_full×F1 Δ P5 (pp) | 10.0 | 10.0 | OK |
| corpus: nano B_noVolatile×F1 successes | 163 | 163 | OK |
| corpus: nano B_noVolatile×F2 successes | 70 | 70 | OK |
| corpus: o4-mini COP successes | 181 | 181 | OK |
| journal: released keys == released_keys.md | True | True | OK |
| batch: condition 5 true, B_full_minus_aria×F1 (240 targets) | 147 | 147 | OK |
| batch: condition 5 true, B_full_minus_volClass×F1 (240 targets) | 192 | 192 | OK |
| batch: condition 5 true, B_full_minus_volId×F1 (240 targets) | 192 | 192 | OK |
| batch: condition 5 true, B_full_minus_state×F1 (240 targets) | 192 | 192 | OK |
| batch: minus_aria condition-5 flips == targets whose only attribute signal is aria-label | True | True | OK |
| batch: minus_aria condition-5 flips (count) | 45 | 45 | OK |
| batch: reps 2/3 have rep-1 condition 5 and observation tokens on every event | True | True | OK |
| batch: o4-mini B_full×F1 condition 5 / tokens == gpt-4.1 B_full×F1 | True | True | OK |
| batch: F2L condition 5 == F2 and F2L − F2 tokens == 151 on every event | True | True | OK |

## F1 — Repetitions (block 3; rep 1 = original corpus run)

### (a) Stability

| model | cell | pred | n / rep | rep 1 % [95% CI] | rep 2 % | rep 3 % | range pp | identical across 3 reps, % [95% CI] | Fleiss κ [95% CI] |
|---|---|---|---|---|---|---|---|---|---|
| gpt-4.1 | B_full×F1 | P5 | 240 | 57.9 [48.3, 67.1] | 60.0 [50.8, 68.8] | 59.2 [50.0, 68.3] | 2.08 | 226/240 = 94.2 [90.8, 97.1] | 0.920 [0.872, 0.960] |
| gpt-4.1 | B_full×F1 | P_now | 240 | 90.4 [85.8, 94.6] | 90.8 [86.2, 95.0] | 92.1 [87.9, 95.8] | 1.67 | 233/240 = 97.1 [94.6, 99.2] | 0.880 [0.759, 0.967] |
| gpt-4.1 | B_noVolatile×F1 | P5 | 240 | 67.5 [57.9, 75.4] | 68.8 [60.0, 76.2] | 68.3 [60.4, 75.4] | 1.25 | 233/240 = 97.1 [94.6, 99.2] | 0.955 [0.919, 0.987] |
| gpt-4.1 | B_noVolatile×F1 | P_now | 240 | 83.8 [77.1, 89.2] | 85.8 [80.4, 90.8] | 84.2 [79.2, 89.2] | 2.08 | 227/240 = 94.6 [91.2, 97.5] | 0.862 [0.769, 0.932] |
| gpt-4.1 | B_noVolatile×F2 | P5 | 240 | 55.4 [47.9, 62.9] | 56.7 [50.0, 62.9] | 56.2 [49.6, 62.5] | 1.25 | 223/240 = 92.9 [89.6, 95.8] | 0.904 [0.858, 0.944] |
| gpt-4.1 | B_noVolatile×F2 | P_now | 240 | 69.6 [62.1, 76.7] | 71.2 [65.8, 77.1] | 71.2 [65.4, 77.1] | 1.67 | 215/240 = 89.6 [85.4, 93.3] | 0.832 [0.765, 0.892] |
| gpt-4.1 | B_noVolatile×F3 | P5 | 240 | 67.9 [59.2, 75.4] | 68.3 [59.6, 75.8] | 68.3 [59.6, 75.8] | 0.42 | 237/240 = 98.8 [97.1, 100.0] | 0.981 [0.959, 1.000] |
| gpt-4.1 | B_noVolatile×F3 | P_now | 240 | 85.8 [80.8, 90.0] | 84.6 [80.0, 88.8] | 84.6 [80.0, 88.8] | 1.25 | 233/240 = 97.1 [94.6, 99.2] | 0.924 [0.857, 0.975] |
| gpt-4.1-nano | B_noVolatile×F1 | P5 | 240 | 67.9 [62.9, 72.5] | 67.9 [62.9, 72.5] | 68.3 [63.7, 72.9] | 0.42 | 236/240 = 98.3 [96.2, 100.0] | 0.974 [0.941, 1.000] |
| gpt-4.1-nano | B_noVolatile×F1 | P_now | 240 | 73.8 [68.8, 78.3] | 73.8 [68.8, 78.3] | 74.6 [70.0, 79.2] | 0.83 | 237/240 = 98.8 [96.7, 100.0] | 0.978 [0.942, 1.000] |
| gpt-4.1-nano | B_noVolatile×F2 | P5 | 240 | 29.2 [23.8, 34.6] | 27.5 [22.1, 32.9] | 26.7 [21.7, 31.7] | 2.50 | 227/240 = 94.6 [92.1, 96.7] | 0.910 [0.866, 0.948] |
| gpt-4.1-nano | B_noVolatile×F2 | P_now | 240 | 37.1 [31.2, 42.9] | 35.0 [28.7, 41.2] | 34.6 [29.2, 40.4] | 2.50 | 221/240 = 92.1 [88.3, 95.4] | 0.885 [0.823, 0.936] |

Rate and agreement CIs: page-cluster bootstrap. κ CI: page-cluster bootstrap on per-page sums; replicates with undefined κ dropped: none.

### (b) Headline replication — B_noVolatile×F1 vs B_full×F1, gpt-4.1

| comparison (second − first) | stratum | pred | n | first % | second % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p χ² | p exact | p χ² Holm | p exact Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 1 | overall | P5 | 240 | 57.9 | 67.5 | +9.58 | [+3.33, +16.67] | 26/3 | 8.67 [2.66, 44.74] | 1.95e-05 | 1.52e-05 | raw only | raw only |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 1 | overall | P_now | 240 | 90.4 | 83.8 | -6.67 | [-11.67, -2.08] | 6/22 | 0.27 [0.09, 0.69] | 0.0025 | 0.0037 | raw only | raw only |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 1 | has_attribute_signal | P5 | 192 | 72.4 | 84.4 | +11.98 | [+4.19, +21.39] | 26/3 | 8.67 [2.66, 44.74] | 1.95e-05 | 1.52e-05 | raw only | raw only |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 1 | has_attribute_signal | P_now | 192 | 95.3 | 94.8 | -0.52 | [-5.18, +3.63] | 4/5 | 0.80 [0.16, 3.72] | 0.7389 | 1.0000 | raw only | raw only |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 1 | no_attribute_signal | P_now | 48 | 70.8 | 39.6 | -31.25 | [-50.94, -12.28] | 2/17 | 0.12 [0.01, 0.50] | 5.79e-04 | 7.29e-04 | raw only | raw only |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 2 | overall | P5 | 240 | 60.0 | 68.8 | +8.75 | [+3.33, +15.83] | 24/3 | 8.00 [2.43, 41.50] | 5.31e-05 | 4.92e-05 | 1.07e-04 | 9.85e-05 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 2 | overall | P_now | 240 | 90.8 | 85.8 | -5.00 | [-9.17, -1.25] | 7/19 | 0.37 [0.13, 0.92] | 0.0186 | 0.0290 | 0.0186 | 0.0290 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 2 | has_attribute_signal | P5 | 192 | 75.0 | 85.9 | +10.94 | [+4.04, +20.00] | 24/3 | 8.00 [2.43, 41.50] | 5.31e-05 | 4.92e-05 | 1.07e-04 | 9.85e-05 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 2 | has_attribute_signal | P_now | 192 | 94.8 | 96.9 | +2.08 | [-1.06, +5.73] | 6/2 | 3.00 [0.54, 30.39] | 0.1573 | 0.2891 | 0.7865 | 1.0000 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 2 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 2 | no_attribute_signal | P_now | 48 | 75.0 | 41.7 | -33.33 | [-50.88, -16.33] | 1/17 | 0.06 [0.00, 0.38] | 1.62e-04 | 1.45e-04 | 0.0011 | 0.0010 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 3 | overall | P5 | 240 | 59.2 | 68.3 | +9.17 | [+3.75, +15.84] | 24/2 | 12.00 [2.98, 104.76] | 1.60e-05 | 1.05e-05 | 8.00e-05 | 5.25e-05 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 3 | overall | P_now | 240 | 92.1 | 84.2 | -7.92 | [-12.50, -3.75] | 3/22 | 0.14 [0.03, 0.45] | 1.45e-04 | 1.57e-04 | 7.23e-04 | 7.83e-04 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 3 | has_attribute_signal | P5 | 192 | 74.0 | 85.4 | +11.46 | [+4.66, +20.42] | 24/2 | 12.00 [2.98, 104.76] | 1.60e-05 | 1.05e-05 | 8.00e-05 | 5.25e-05 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 3 | has_attribute_signal | P_now | 192 | 96.4 | 95.8 | -0.52 | [-3.61, +2.05] | 2/3 | 0.67 [0.06, 5.82] | 0.6547 | 1.0000 | 1.0000 | 1.0000 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 3 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, rep 3 | no_attribute_signal | P_now | 48 | 75.0 | 37.5 | -37.50 | [-54.35, -20.41] | 1/19 | 0.05 [0.00, 0.33] | 5.70e-05 | 4.01e-05 | 5.13e-04 | 3.60e-04 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, majority ≥2/3 | overall | P5 | 240 | 59.6 | 68.3 | +8.75 | [+3.33, +15.83] | 23/2 | 11.50 [2.84, 100.63] | 2.67e-05 | 1.94e-05 | 1.07e-04 | 7.77e-05 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, majority ≥2/3 | overall | P_now | 240 | 91.2 | 85.0 | -6.25 | [-10.00, -2.50] | 5/20 | 0.25 [0.07, 0.69] | 0.0027 | 0.0041 | 0.0081 | 0.0122 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, majority ≥2/3 | has_attribute_signal | P5 | 192 | 74.5 | 85.4 | +10.94 | [+4.10, +20.00] | 23/2 | 11.50 [2.84, 100.63] | 2.67e-05 | 1.94e-05 | 1.07e-04 | 7.77e-05 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, majority ≥2/3 | has_attribute_signal | P_now | 192 | 95.3 | 96.4 | +1.04 | [-1.59, +4.15] | 4/2 | 2.00 [0.29, 22.11] | 0.4142 | 0.6875 | 1.0000 | 1.0000 |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, majority ≥2/3 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (b) gpt-4.1 B_noVolatile×F1 vs B_full×F1, majority ≥2/3 | no_attribute_signal | P_now | 48 | 75.0 | 39.6 | -35.42 | [-52.09, -18.75] | 1/18 | 0.06 [0.00, 0.35] | 9.62e-05 | 7.63e-05 | 7.69e-04 | 6.10e-04 |

**Criterion** (Δ > 0 and bootstrap CI lower bound > 0 in rep 2 AND rep 3 (P5, overall)): **replicates**.

### (c) COP — B_noVolatile×F3 vs B_full×F1, gpt-4.1

| comparison (second − first) | stratum | pred | n | first % | second % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p χ² | p exact | p χ² Holm | p exact Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 | overall | P5 | 240 | 57.9 | 67.9 | +10.00 | [+4.17, +17.08] | 28/4 | 7.00 [2.45, 27.47] | 2.21e-05 | 1.93e-05 | raw only | raw only |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 | overall | P_now | 240 | 90.4 | 85.8 | -4.58 | [-9.17, -0.42] | 7/18 | 0.39 [0.14, 0.98] | 0.0278 | 0.0433 | raw only | raw only |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 | has_attribute_signal | P5 | 192 | 72.4 | 84.9 | +12.50 | [+5.08, +21.93] | 28/4 | 7.00 [2.45, 27.47] | 2.21e-05 | 1.93e-05 | raw only | raw only |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 | has_attribute_signal | P_now | 192 | 95.3 | 95.8 | +0.52 | [-2.56, +3.70] | 4/3 | 1.33 [0.23, 9.10] | 0.7055 | 1.0000 | raw only | raw only |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 | no_attribute_signal | P_now | 48 | 70.8 | 45.8 | -25.00 | [-42.31, -8.00] | 3/15 | 0.20 [0.04, 0.71] | 0.0047 | 0.0075 | raw only | raw only |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 2 | overall | P5 | 240 | 60.0 | 68.3 | +8.33 | [+2.50, +15.42] | 23/3 | 7.67 [2.32, 39.89] | 8.77e-05 | 8.80e-05 | 1.07e-04 | 9.85e-05 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 2 | overall | P_now | 240 | 90.8 | 84.6 | -6.25 | [-10.83, -1.67] | 7/22 | 0.32 [0.11, 0.77] | 0.0053 | 0.0081 | 0.0107 | 0.0163 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 2 | has_attribute_signal | P5 | 192 | 75.0 | 85.4 | +10.42 | [+3.12, +19.68] | 23/3 | 7.67 [2.32, 39.89] | 8.77e-05 | 8.80e-05 | 1.07e-04 | 9.85e-05 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 2 | has_attribute_signal | P_now | 192 | 94.8 | 95.8 | +1.04 | [-2.14, +4.74] | 5/3 | 1.67 [0.32, 10.73] | 0.4795 | 0.7266 | 1.0000 | 1.0000 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 2 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 2 | no_attribute_signal | P_now | 48 | 75.0 | 39.6 | -35.42 | [-53.19, -17.65] | 2/19 | 0.11 [0.01, 0.44] | 2.08e-04 | 2.21e-04 | 0.0012 | 0.0013 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 3 | overall | P5 | 240 | 59.2 | 68.3 | +9.17 | [+3.75, +16.25] | 25/3 | 8.33 [2.54, 43.12] | 3.22e-05 | 2.74e-05 | 1.07e-04 | 8.23e-05 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 3 | overall | P_now | 240 | 92.1 | 84.6 | -7.50 | [-12.08, -3.33] | 5/23 | 0.22 [0.06, 0.58] | 6.70e-04 | 9.12e-04 | 0.0027 | 0.0036 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 3 | has_attribute_signal | P5 | 192 | 74.0 | 85.4 | +11.46 | [+4.52, +20.74] | 25/3 | 8.33 [2.54, 43.12] | 3.22e-05 | 2.74e-05 | 1.07e-04 | 8.23e-05 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 3 | has_attribute_signal | P_now | 192 | 96.4 | 95.8 | -0.52 | [-2.72, +1.59] | 3/4 | 0.75 [0.11, 4.43] | 0.7055 | 1.0000 | 1.0000 | 1.0000 |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 3 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (c) gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 3 | no_attribute_signal | P_now | 48 | 75.0 | 39.6 | -35.42 | [-53.19, -17.65] | 2/19 | 0.11 [0.01, 0.44] | 2.08e-04 | 2.21e-04 | 0.0012 | 0.0013 |

Observation tokens (o200k_base, deterministic):

| rep | n | B_full×F1 mean | COP mean | Δ mean | B_full×F1 total | COP total | reduction % |
|---|---|---|---|---|---|---|---|
| 1 | 240 | 27096.7 | 17887.5 | -9209.2 | 6,503,210 | 4,292,990 | 33.99 |
| 2 | 240 | 27096.7 | 17887.5 | -9209.2 | 6,503,210 | 4,292,990 | 33.99 |
| 3 | 240 | 27096.7 | 17887.5 | -9209.2 | 6,503,210 | 4,292,990 | 33.99 |

### (d) F2 drop — B_noVolatile F2 vs F1

| comparison (second − first) | stratum | pred | n | first % | second % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p χ² | p exact | p χ² Holm | p exact Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 1 | overall | P5 | 240 | 67.5 | 55.4 | -12.08 | [-18.75, -5.83] | 4/33 | 0.12 [0.03, 0.34] | 1.86e-06 | 1.08e-06 | raw only | raw only |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 1 | overall | P_now | 240 | 83.8 | 69.6 | -14.17 | [-21.67, -7.08] | 5/39 | 0.13 [0.04, 0.33] | 2.96e-07 | 1.41e-07 | raw only | raw only |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 1 | has_attribute_signal | P5 | 192 | 84.4 | 69.3 | -15.10 | [-23.24, -7.22] | 4/33 | 0.12 [0.03, 0.34] | 1.86e-06 | 1.08e-06 | raw only | raw only |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 1 | has_attribute_signal | P_now | 192 | 94.8 | 78.1 | -16.67 | [-24.24, -9.57] | 2/34 | 0.06 [0.01, 0.23] | 9.64e-08 | 1.94e-08 | raw only | raw only |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 1 | no_attribute_signal | P_now | 48 | 39.6 | 35.4 | -4.17 | [-15.56, +7.27] | 3/5 | 0.60 [0.09, 3.08] | 0.4795 | 0.7266 | raw only | raw only |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 2 | overall | P5 | 240 | 68.8 | 56.7 | -12.08 | [-17.92, -6.67] | 2/31 | 0.06 [0.01, 0.25] | 4.46e-07 | 1.31e-07 | 3.12e-06 | 9.16e-07 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 2 | overall | P_now | 240 | 85.8 | 71.2 | -14.58 | [-20.83, -8.75] | 2/37 | 0.05 [0.01, 0.21] | 2.09e-08 | 2.84e-09 | 1.46e-07 | 1.99e-08 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 2 | has_attribute_signal | P5 | 192 | 85.9 | 70.8 | -15.10 | [-21.99, -8.60] | 2/31 | 0.06 [0.01, 0.25] | 4.46e-07 | 1.31e-07 | 3.12e-06 | 9.16e-07 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 2 | has_attribute_signal | P_now | 192 | 96.9 | 80.7 | -16.15 | [-22.80, -10.00] | 0/31 | 0.00 [0.00, 0.13] | 2.58e-08 | 9.31e-10 | 1.81e-07 | 6.52e-09 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 2 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 2 | no_attribute_signal | P_now | 48 | 41.7 | 33.3 | -8.33 | [-22.00, +3.92] | 2/6 | 0.33 [0.03, 1.86] | 0.1573 | 0.2891 | 0.6292 | 1.0000 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 3 | overall | P5 | 240 | 68.3 | 56.2 | -12.08 | [-17.50, -7.08] | 2/31 | 0.06 [0.01, 0.25] | 4.46e-07 | 1.31e-07 | 3.12e-06 | 9.16e-07 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 3 | overall | P_now | 240 | 84.2 | 71.2 | -12.92 | [-19.17, -7.08] | 5/36 | 0.14 [0.04, 0.36] | 1.29e-06 | 7.84e-07 | 7.74e-06 | 4.70e-06 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 3 | has_attribute_signal | P5 | 192 | 85.4 | 70.3 | -15.10 | [-21.94, -8.90] | 2/31 | 0.06 [0.01, 0.25] | 4.46e-07 | 1.31e-07 | 3.12e-06 | 9.16e-07 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 3 | has_attribute_signal | P_now | 192 | 95.8 | 79.7 | -16.15 | [-22.92, -9.95] | 1/32 | 0.03 [0.00, 0.19] | 6.80e-08 | 7.92e-09 | 4.08e-07 | 4.75e-08 |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 3 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 3 | no_attribute_signal | P_now | 48 | 37.5 | 37.5 | +0.00 | [-11.76, +11.36] | 4/4 | 1.00 [0.19, 5.37] | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 1 | overall | P5 | 240 | 67.9 | 29.2 | -38.75 | [-46.67, -30.83] | 7/100 | 0.07 [0.03, 0.15] | 2.46e-19 | 3.45e-22 | raw only | raw only |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 1 | overall | P_now | 240 | 73.8 | 37.1 | -36.67 | [-44.58, -28.75] | 12/100 | 0.12 [0.06, 0.22] | 9.16e-17 | 1.93e-18 | raw only | raw only |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 1 | has_attribute_signal | P5 | 192 | 84.9 | 36.5 | -48.44 | [-58.29, -38.27] | 7/100 | 0.07 [0.03, 0.15] | 2.46e-19 | 3.45e-22 | raw only | raw only |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 1 | has_attribute_signal | P_now | 192 | 87.5 | 42.2 | -45.31 | [-55.00, -35.23] | 9/96 | 0.09 [0.04, 0.19] | 2.06e-17 | 1.63e-19 | raw only | raw only |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 1 | no_attribute_signal | P_now | 48 | 18.8 | 16.7 | -2.08 | [-13.64, +8.51] | 3/4 | 0.75 [0.11, 4.43] | 0.7055 | 1.0000 | raw only | raw only |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 2 | overall | P5 | 240 | 67.9 | 27.5 | -40.42 | [-47.50, -32.92] | 5/102 | 0.05 [0.02, 0.12] | 6.77e-21 | 1.38e-24 | 5.41e-20 | 1.10e-23 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 2 | overall | P_now | 240 | 73.8 | 35.0 | -38.75 | [-46.25, -31.25] | 10/103 | 0.10 [0.05, 0.19] | 2.16e-18 | 1.32e-20 | 1.73e-17 | 1.06e-19 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 2 | has_attribute_signal | P5 | 192 | 84.9 | 34.4 | -50.52 | [-59.57, -40.93] | 5/102 | 0.05 [0.02, 0.12] | 6.77e-21 | 1.38e-24 | 5.41e-20 | 1.10e-23 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 2 | has_attribute_signal | P_now | 192 | 87.5 | 39.1 | -48.44 | [-58.08, -38.46] | 6/99 | 0.06 [0.02, 0.14] | 1.13e-19 | 8.44e-23 | 9.02e-19 | 6.75e-22 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 2 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 2 | no_attribute_signal | P_now | 48 | 18.8 | 18.8 | +0.00 | [-12.50, +11.11] | 4/4 | 1.00 [0.19, 5.37] | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 3 | overall | P5 | 240 | 68.3 | 26.7 | -41.67 | [-47.92, -35.42] | 4/104 | 0.04 [0.01, 0.10] | 6.42e-22 | 3.43e-26 | 5.78e-21 | 3.09e-25 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 3 | overall | P_now | 240 | 74.6 | 34.6 | -40.00 | [-46.67, -33.33] | 9/105 | 0.09 [0.04, 0.17] | 2.44e-19 | 6.81e-22 | 2.20e-18 | 6.13e-21 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 3 | has_attribute_signal | P5 | 192 | 85.4 | 33.3 | -52.08 | [-59.69, -43.85] | 4/104 | 0.04 [0.01, 0.10] | 6.42e-22 | 3.43e-26 | 5.78e-21 | 3.09e-25 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 3 | has_attribute_signal | P_now | 192 | 88.5 | 38.5 | -50.00 | [-58.33, -41.40] | 5/101 | 0.05 [0.02, 0.12] | 1.12e-20 | 2.63e-24 | 1.01e-19 | 2.36e-23 |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 3 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| (d) gpt-4.1-nano B_noVolatile F2 vs F1, rep 3 | no_attribute_signal | P_now | 48 | 18.8 | 18.8 | +0.00 | [-12.50, +11.11] | 4/4 | 1.00 [0.19, 5.37] | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## F2 — Single-attribute ablations (block 1, gpt-4.1, F1, rep 1)

| comparison (second − first) | stratum | pred | n | first % | second % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p χ² | p exact | p χ² Holm | p exact Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4.1 B_full_minus_volClass×F1 vs B_full×F1 | overall | P5 | 240 | 57.9 | 74.6 | +16.67 | [+10.00, +24.17] | 40/0 | inf [10.35, inf] | 2.54e-10 | 1.82e-12 | 7.62e-10 | 5.46e-12 |
| gpt-4.1 B_full_minus_volClass×F1 vs B_full×F1 | overall | P_now | 240 | 90.4 | 84.6 | -5.83 | [-10.00, -2.08] | 5/19 | 0.26 [0.08, 0.73] | 0.0043 | 0.0066 | 0.0128 | 0.0198 |
| gpt-4.1 B_full_minus_volClass×F1 vs B_full×F1 | has_attribute_signal | P5 | 192 | 72.4 | 93.2 | +20.83 | [+12.24, +30.85] | 40/0 | inf [10.35, inf] | 2.54e-10 | 1.82e-12 | 7.62e-10 | 5.46e-12 |
| gpt-4.1 B_full_minus_volClass×F1 vs B_full×F1 | has_attribute_signal | P_now | 192 | 95.3 | 95.8 | +0.52 | [-1.61, +2.99] | 3/2 | 1.50 [0.17, 17.96] | 0.6547 | 1.0000 | 0.6547 | 1.0000 |
| gpt-4.1 B_full_minus_volClass×F1 vs B_full×F1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_full_minus_volClass×F1 vs B_full×F1 | no_attribute_signal | P_now | 48 | 70.8 | 39.6 | -31.25 | [-48.08, -14.58] | 2/17 | 0.12 [0.01, 0.50] | 5.79e-04 | 7.29e-04 | 0.0017 | 0.0022 |
| gpt-4.1 B_full_minus_volId×F1 vs B_full×F1 | overall | P5 | 240 | 57.9 | 61.7 | +3.75 | [+0.42, +7.50] | 13/4 | 3.25 [1.00, 13.68] | 0.0290 | 0.0490 | 0.0290 | 0.0490 |
| gpt-4.1 B_full_minus_volId×F1 vs B_full×F1 | overall | P_now | 240 | 90.4 | 90.8 | +0.42 | [-1.67, +2.92] | 5/4 | 1.25 [0.27, 6.30] | 0.7389 | 1.0000 | 0.7389 | 1.0000 |
| gpt-4.1 B_full_minus_volId×F1 vs B_full×F1 | has_attribute_signal | P5 | 192 | 72.4 | 77.1 | +4.69 | [+0.51, +9.57] | 13/4 | 3.25 [1.00, 13.68] | 0.0290 | 0.0490 | 0.0290 | 0.0490 |
| gpt-4.1 B_full_minus_volId×F1 vs B_full×F1 | has_attribute_signal | P_now | 192 | 95.3 | 96.4 | +1.04 | [+0.00, +2.62] | 3/1 | 3.00 [0.24, 157.49] | 0.3173 | 0.6250 | 0.6346 | 1.0000 |
| gpt-4.1 B_full_minus_volId×F1 vs B_full×F1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_full_minus_volId×F1 vs B_full×F1 | no_attribute_signal | P_now | 48 | 70.8 | 68.8 | -2.08 | [-11.11, +6.82] | 2/3 | 0.67 [0.06, 5.82] | 0.6547 | 1.0000 | 0.8284 | 1.0000 |
| gpt-4.1 B_full_minus_state×F1 vs B_full×F1 | overall | P5 | 240 | 57.9 | 58.3 | +0.42 | [-2.92, +3.33] | 7/6 | 1.17 [0.34, 4.20] | 0.7815 | 1.0000 | raw only | raw only |
| gpt-4.1 B_full_minus_state×F1 vs B_full×F1 | overall | P_now | 240 | 90.4 | 91.2 | +0.83 | [-1.25, +3.33] | 4/2 | 2.00 [0.29, 22.11] | 0.4142 | 0.6875 | raw only | raw only |
| gpt-4.1 B_full_minus_state×F1 vs B_full×F1 | has_attribute_signal | P5 | 192 | 72.4 | 72.9 | +0.52 | [-3.59, +4.37] | 7/6 | 1.17 [0.34, 4.20] | 0.7815 | 1.0000 | raw only | raw only |
| gpt-4.1 B_full_minus_state×F1 vs B_full×F1 | has_attribute_signal | P_now | 192 | 95.3 | 96.4 | +1.04 | [-1.04, +3.14] | 3/1 | 3.00 [0.24, 157.49] | 0.3173 | 0.6250 | raw only | raw only |
| gpt-4.1 B_full_minus_state×F1 vs B_full×F1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_full_minus_state×F1 vs B_full×F1 | no_attribute_signal | P_now | 48 | 70.8 | 70.8 | +0.00 | [-6.12, +6.12] | 1/1 | 1.00 [0.01, 78.50] | 1.0000 | 1.0000 | raw only | raw only |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1 | overall | P5 | 240 | 57.9 | 49.6 | -8.33 | [-12.92, -3.75] | 6/26 | 0.23 [0.08, 0.57] | 4.07e-04 | 5.35e-04 | 8.14e-04 | 0.0011 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1 | overall | P_now | 240 | 90.4 | 86.2 | -4.17 | [-8.33, -0.42] | 4/14 | 0.29 [0.07, 0.91] | 0.0184 | 0.0309 | 0.0368 | 0.0618 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1 | has_attribute_signal | P5 | 192 | 72.4 | 62.0 | -10.42 | [-16.41, -4.64] | 6/26 | 0.23 [0.08, 0.57] | 4.07e-04 | 5.35e-04 | 8.14e-04 | 0.0011 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1 | has_attribute_signal | P_now | 192 | 95.3 | 91.1 | -4.17 | [-7.81, -1.03] | 2/10 | 0.20 [0.02, 0.94] | 0.0209 | 0.0386 | 0.0628 | 0.1157 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1 | no_attribute_signal | P_now | 48 | 70.8 | 66.7 | -4.17 | [-13.73, +6.25] | 2/4 | 0.50 [0.05, 3.49] | 0.4142 | 0.6875 | 0.8284 | 1.0000 |

- gpt-4.1 B_full_minus_volClass×F1 vs B_full×F1: n_called 200; reused pages (identical observation, concordant by construction): page_02, page_04, page_12, page_19
- gpt-4.1 B_full_minus_volId×F1 vs B_full×F1: n_called 220; reused pages (identical observation, concordant by construction): page_03, page_07
- gpt-4.1 B_full_minus_state×F1 vs B_full×F1: n_called 0; reused pages (identical observation, concordant by construction): page_01, page_02, page_03, page_04, page_05, page_06, page_07, page_08, page_09, page_10, page_11, page_12, page_13, page_14, page_15, page_16, page_17, page_18, page_19, page_20, page_21, page_22, page_23, page_24; both arms original corpus records → raw p only
- gpt-4.1 B_full_minus_aria×F1 vs B_full×F1: n_called 240; reused pages (identical observation, concordant by construction): none

minus_aria — 45 targets whose condition 5 becomes false by construction (only attribute signal = aria-label): page_01 t_03, page_01 t_09, page_02 t_05, page_03 t_08, page_04 t_10, page_05 t_07, page_05 t_08, page_06 t_05, page_06 t_08, page_06 t_10, page_07 t_05, page_07 t_08, page_08 t_09, page_09 t_08, page_10 t_03, page_10 t_05, page_10 t_08, page_11 t_05, page_12 t_07, page_13 t_04, page_13 t_08, page_14 t_02, page_14 t_06, page_14 t_09, page_15 t_05, page_15 t_06, page_15 t_07, page_16 t_06, page_16 t_08, page_17 t_04, page_17 t_05, page_18 t_04, page_20 t_09, page_21 t_04, page_21 t_06, page_21 t_08, page_22 t_02, page_22 t_04, page_22 t_05, page_23 t_02, page_23 t_04, page_23 t_05, page_24 t_02, page_24 t_04, page_24 t_05.

| comparison (second − first) | stratum | pred | n | first % | second % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p χ² | p exact | p χ² Holm | p exact Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, remaining 195 targets | overall | P5 | 195 | 60.0 | 61.0 | +1.03 | [-2.66, +4.66] | 6/4 | 1.50 [0.36, 7.23] | 0.5271 | 0.7539 | 0.5271 | 0.7539 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, remaining 195 targets | overall | P_now | 195 | 91.3 | 90.8 | -0.51 | [-3.14, +2.07] | 4/5 | 0.80 [0.16, 3.72] | 0.7389 | 1.0000 | 0.7389 | 1.0000 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, remaining 195 targets | has_attribute_signal | P5 | 147 | 79.6 | 81.0 | +1.36 | [-3.62, +6.25] | 6/4 | 1.50 [0.36, 7.23] | 0.5271 | 0.7539 | 0.5271 | 0.7539 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, remaining 195 targets | has_attribute_signal | P_now | 147 | 98.0 | 98.6 | +0.68 | [+0.00, +2.14] | 2/1 | 2.00 [0.10, 117.99] | 0.5637 | 1.0000 | 0.5637 | 1.0000 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, remaining 195 targets | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, remaining 195 targets | no_attribute_signal | P_now | 48 | 70.8 | 66.7 | -4.17 | [-13.73, +6.25] | 2/4 | 0.50 [0.05, 3.49] | 0.4142 | 0.6875 | 0.4142 | 0.6875 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, the 45 flipped targets | overall | P5 | 45 | 48.9 | 0.0 | -48.89 | [-68.09, -31.11] | 0/22 | 0.00 [0.00, 0.18] | 2.73e-06 | 4.77e-07 | 2.73e-06 | 4.77e-07 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, the 45 flipped targets | overall | P_now | 45 | 86.7 | 66.7 | -20.00 | [-32.00, -7.89] | 0/9 | 0.00 [0.00, 0.51] | 0.0027 | 0.0039 | 0.0027 | 0.0039 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, the 45 flipped targets | has_attribute_signal | P5 | 45 | 48.9 | 0.0 | -48.89 | [-68.09, -31.11] | 0/22 | 0.00 [0.00, 0.18] | 2.73e-06 | 4.77e-07 | 2.73e-06 | 4.77e-07 |
| gpt-4.1 B_full_minus_aria×F1 vs B_full×F1, the 45 flipped targets | has_attribute_signal | P_now | 45 | 86.7 | 66.7 | -20.00 | [-32.00, -7.89] | 0/9 | 0.00 [0.00, 0.51] | 0.0027 | 0.0039 | 0.0027 | 0.0039 |

## F3 — Key-name legend (block 2, rep 1)

| comparison (second − first) | stratum | pred | n | first % | second % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p χ² | p exact | p χ² Holm | p exact Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4.1 B_full: F2L vs F2 | overall | P5 | 240 | 47.1 | 59.6 | +12.50 | [+6.67, +18.75] | 34/4 | 8.50 [3.03, 32.97] | 1.14e-06 | 6.04e-07 | 4.54e-06 | 2.42e-06 |
| gpt-4.1 B_full: F2L vs F2 | overall | P_now | 240 | 75.8 | 90.4 | +14.58 | [+10.00, +19.58] | 38/3 | 12.67 [4.02, 64.14] | 4.60e-08 | 1.05e-08 | 2.30e-07 | 5.24e-08 |
| gpt-4.1 B_full: F2L vs F2 | has_attribute_signal | P5 | 192 | 58.9 | 74.5 | +15.62 | [+8.56, +22.84] | 34/4 | 8.50 [3.03, 32.97] | 1.14e-06 | 6.04e-07 | 4.54e-06 | 2.42e-06 |
| gpt-4.1 B_full: F2L vs F2 | has_attribute_signal | P_now | 192 | 79.7 | 94.3 | +14.58 | [+8.85, +21.13] | 30/2 | 15.00 [3.81, 129.54] | 7.43e-07 | 2.46e-07 | 2.97e-06 | 9.85e-07 |
| gpt-4.1 B_full: F2L vs F2 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_full: F2L vs F2 | no_attribute_signal | P_now | 48 | 60.4 | 75.0 | +14.58 | [+4.26, +24.49] | 8/1 | 8.00 [1.07, 354.98] | 0.0196 | 0.0391 | 0.1178 | 0.2344 |
| gpt-4.1 B_full: F2L vs F1 | overall | P5 | 240 | 57.9 | 59.6 | +1.67 | [-2.08, +5.83] | 11/7 | 1.57 [0.56, 4.78] | 0.3458 | 0.4807 | 0.6916 | 0.9614 |
| gpt-4.1 B_full: F2L vs F1 | overall | P_now | 240 | 90.4 | 90.4 | +0.00 | [-3.33, +3.33] | 6/6 | 1.00 [0.27, 3.74] | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| gpt-4.1 B_full: F2L vs F1 | has_attribute_signal | P5 | 192 | 72.4 | 74.5 | +2.08 | [-2.50, +7.18] | 11/7 | 1.57 [0.56, 4.78] | 0.3458 | 0.4807 | 0.6916 | 0.9614 |
| gpt-4.1 B_full: F2L vs F1 | has_attribute_signal | P_now | 192 | 95.3 | 94.3 | -1.04 | [-4.81, +2.63] | 4/6 | 0.67 [0.14, 2.81] | 0.5271 | 0.7539 | 0.5271 | 0.9062 |
| gpt-4.1 B_full: F2L vs F1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_full: F2L vs F1 | no_attribute_signal | P_now | 48 | 70.8 | 75.0 | +4.17 | [+0.00, +10.20] | 2/0 | inf [0.19, inf] | 0.1573 | 0.5000 | 0.7865 | 1.0000 |
| gpt-4.1 B_noVolatile: F2L vs F2 | overall | P5 | 240 | 55.4 | 67.5 | +12.08 | [+6.67, +17.92] | 31/2 | 15.50 [3.94, 133.66] | 4.46e-07 | 1.31e-07 | 2.23e-06 | 6.54e-07 |
| gpt-4.1 B_noVolatile: F2L vs F2 | overall | P_now | 240 | 69.6 | 81.2 | +11.67 | [+5.42, +18.33] | 35/7 | 5.00 [2.19, 13.34] | 1.56e-05 | 1.51e-05 | 6.23e-05 | 6.04e-05 |
| gpt-4.1 B_noVolatile: F2L vs F2 | has_attribute_signal | P5 | 192 | 69.3 | 84.4 | +15.10 | [+8.46, +22.11] | 31/2 | 15.50 [3.94, 133.66] | 4.46e-07 | 1.31e-07 | 2.23e-06 | 6.54e-07 |
| gpt-4.1 B_noVolatile: F2L vs F2 | has_attribute_signal | P_now | 192 | 78.1 | 93.2 | +15.10 | [+8.47, +22.28] | 31/2 | 15.50 [3.94, 133.66] | 4.46e-07 | 1.31e-07 | 2.23e-06 | 6.54e-07 |
| gpt-4.1 B_noVolatile: F2L vs F2 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_noVolatile: F2L vs F2 | no_attribute_signal | P_now | 48 | 35.4 | 33.3 | -2.08 | [-12.77, +8.51] | 4/5 | 0.80 [0.16, 3.72] | 0.7389 | 1.0000 | 1.0000 | 1.0000 |
| gpt-4.1 B_noVolatile: F2L vs F1 | overall | P5 | 240 | 67.5 | 67.5 | +0.00 | [-2.92, +3.75] | 5/5 | 1.00 [0.23, 4.35] | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| gpt-4.1 B_noVolatile: F2L vs F1 | overall | P_now | 240 | 83.8 | 81.2 | -2.50 | [-5.42, +0.42] | 4/10 | 0.40 [0.09, 1.39] | 0.1088 | 0.1796 | 0.2305 | 0.3591 |
| gpt-4.1 B_noVolatile: F2L vs F1 | has_attribute_signal | P5 | 192 | 84.4 | 84.4 | +0.00 | [-3.70, +4.76] | 5/5 | 1.00 [0.23, 4.35] | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| gpt-4.1 B_noVolatile: F2L vs F1 | has_attribute_signal | P_now | 192 | 94.8 | 93.2 | -1.56 | [-4.23, +1.60] | 2/5 | 0.40 [0.04, 2.44] | 0.2568 | 0.4531 | 0.5137 | 0.9062 |
| gpt-4.1 B_noVolatile: F2L vs F1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_noVolatile: F2L vs F1 | no_attribute_signal | P_now | 48 | 39.6 | 33.3 | -6.25 | [-15.22, +2.17] | 2/5 | 0.40 [0.04, 2.44] | 0.2568 | 0.4531 | 1.0000 | 1.0000 |
| gpt-4.1-nano B_noVolatile: F2L vs F2 | overall | P5 | 240 | 29.2 | 25.4 | -3.75 | [-8.75, +1.67] | 14/23 | 0.61 [0.29, 1.23] | 0.1390 | 0.1877 | 0.4169 | 0.5632 |
| gpt-4.1-nano B_noVolatile: F2L vs F2 | overall | P_now | 240 | 37.1 | 32.1 | -5.00 | [-10.00, -0.42] | 17/29 | 0.59 [0.30, 1.10] | 0.0768 | 0.1038 | 0.2305 | 0.3114 |
| gpt-4.1-nano B_noVolatile: F2L vs F2 | has_attribute_signal | P5 | 192 | 36.5 | 31.8 | -4.69 | [-11.11, +2.14] | 14/23 | 0.61 [0.29, 1.23] | 0.1390 | 0.1877 | 0.4169 | 0.5632 |
| gpt-4.1-nano B_noVolatile: F2L vs F2 | has_attribute_signal | P_now | 192 | 42.2 | 35.9 | -6.25 | [-11.79, -0.51] | 13/25 | 0.52 [0.24, 1.06] | 0.0516 | 0.0730 | 0.1547 | 0.2189 |
| gpt-4.1-nano B_noVolatile: F2L vs F2 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1-nano B_noVolatile: F2L vs F2 | no_attribute_signal | P_now | 48 | 16.7 | 16.7 | +0.00 | [-9.80, +10.87] | 4/4 | 1.00 [0.19, 5.37] | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| gpt-4.1-nano B_noVolatile: F2L vs F1 | overall | P5 | 240 | 67.9 | 25.4 | -42.50 | [-50.00, -34.58] | 9/111 | 0.08 [0.04, 0.16] | 1.26e-20 | 1.71e-23 | 7.58e-20 | 1.03e-22 |
| gpt-4.1-nano B_noVolatile: F2L vs F1 | overall | P_now | 240 | 73.8 | 32.1 | -41.67 | [-49.58, -33.75] | 13/113 | 0.12 [0.06, 0.20] | 5.16e-19 | 4.52e-21 | 3.10e-18 | 2.71e-20 |
| gpt-4.1-nano B_noVolatile: F2L vs F1 | has_attribute_signal | P5 | 192 | 84.9 | 31.8 | -53.12 | [-62.31, -43.43] | 9/111 | 0.08 [0.04, 0.16] | 1.26e-20 | 1.71e-23 | 7.58e-20 | 1.03e-22 |
| gpt-4.1-nano B_noVolatile: F2L vs F1 | has_attribute_signal | P_now | 192 | 87.5 | 35.9 | -51.56 | [-61.17, -41.62] | 10/109 | 0.09 [0.04, 0.18] | 1.13e-19 | 3.52e-22 | 6.80e-19 | 2.11e-21 |
| gpt-4.1-nano B_noVolatile: F2L vs F1 | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1-nano B_noVolatile: F2L vs F1 | no_attribute_signal | P_now | 48 | 18.8 | 16.7 | -2.08 | [-13.21, +8.70] | 3/4 | 0.75 [0.11, 4.43] | 0.7055 | 1.0000 | 1.0000 | 1.0000 |

Fixed interpretation (P5, overall, unadjusted bootstrap CIs): *legend restores* if F2L−F2 > 0 with CI lower bound > 0 AND the CI of F2L−F1 includes 0; *partial* if only the first holds; *no effect* otherwise.

| model | bundle | F2L−F2 > 0, CI lo > 0 | CI(F2L−F1) ∋ 0 | verdict |
|---|---|---|---|---|
| gpt-4.1 | B_full | True | True | **legend restores** |
| gpt-4.1 | B_noVolatile | True | True | **legend restores** |
| gpt-4.1-nano | B_noVolatile | False | False | **no effect** |

## F4 — o4-mini (block 4; decoding at the service default, no temperature)

| comparison (second − first) | stratum | pred | n | first % | second % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p χ² | p exact | p χ² Holm | p exact Holm |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, all events | overall | P5 | 240 | 66.2 | 75.4 | +9.17 | [+4.58, +14.58] | 23/1 | 23.00 [3.73, 947.45] | 7.10e-06 | 2.98e-06 | 1.42e-05 | 5.96e-06 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, all events | overall | P_now | 240 | 93.8 | 90.8 | -2.92 | [-5.42, -0.42] | 4/11 | 0.36 [0.08, 1.23] | 0.0707 | 0.1185 | 0.1414 | 0.2369 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, all events | has_attribute_signal | P5 | 192 | 82.8 | 94.3 | +11.46 | [+5.55, +18.32] | 23/1 | 23.00 [3.73, 947.45] | 7.10e-06 | 2.98e-06 | 1.42e-05 | 5.96e-06 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, all events | has_attribute_signal | P_now | 192 | 96.4 | 97.9 | +1.56 | [+0.00, +3.21] | 3/0 | inf [0.41, inf] | 0.0833 | 0.2500 | 0.1665 | 0.5000 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, all events | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, all events | no_attribute_signal | P_now | 48 | 83.3 | 62.5 | -20.83 | [-33.33, -9.09] | 1/11 | 0.09 [0.00, 0.63] | 0.0039 | 0.0063 | 0.0078 | 0.0127 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, without re-issued events | overall | P5 | 238 | 66.4 | 75.6 | +9.24 | [+4.58, +14.64] | 23/1 | 23.00 [3.73, 947.45] | 7.10e-06 | 2.98e-06 | 1.42e-05 | 5.96e-06 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, without re-issued events | overall | P_now | 238 | 93.7 | 91.2 | -2.52 | [-5.04, -0.42] | 4/10 | 0.40 [0.09, 1.39] | 0.1088 | 0.1796 | 0.1414 | 0.2369 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, without re-issued events | has_attribute_signal | P5 | 191 | 82.7 | 94.2 | +11.52 | [+5.58, +18.42] | 23/1 | 23.00 [3.73, 947.45] | 7.10e-06 | 2.98e-06 | 1.42e-05 | 5.96e-06 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, without re-issued events | has_attribute_signal | P_now | 191 | 96.3 | 97.9 | +1.57 | [+0.00, +3.23] | 3/0 | inf [0.41, inf] | 0.0833 | 0.2500 | 0.1665 | 0.5000 |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, without re-issued events | no_attribute_signal | P5 | 47 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| o4-mini B_noVolatile×F3 (COP) vs B_full×F1, without re-issued events | no_attribute_signal | P_now | 47 | 83.0 | 63.8 | -19.15 | [-32.00, -7.32] | 1/10 | 0.10 [0.00, 0.70] | 0.0067 | 0.0117 | 0.0078 | 0.0127 |
| gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 (reference) | overall | P5 | 240 | 57.9 | 67.9 | +10.00 | [+4.17, +17.08] | 28/4 | 7.00 [2.45, 27.47] | 2.21e-05 | 1.93e-05 | raw only | raw only |
| gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 (reference) | overall | P_now | 240 | 90.4 | 85.8 | -4.58 | [-9.17, -0.42] | 7/18 | 0.39 [0.14, 0.98] | 0.0278 | 0.0433 | raw only | raw only |
| gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 (reference) | has_attribute_signal | P5 | 192 | 72.4 | 84.9 | +12.50 | [+5.08, +21.93] | 28/4 | 7.00 [2.45, 27.47] | 2.21e-05 | 1.93e-05 | raw only | raw only |
| gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 (reference) | has_attribute_signal | P_now | 192 | 95.3 | 95.8 | +0.52 | [-2.56, +3.70] | 4/3 | 1.33 [0.23, 9.10] | 0.7055 | 1.0000 | raw only | raw only |
| gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 (reference) | no_attribute_signal | P5 | 48 | 0.0 | 0.0 | +0.00 | [+0.00, +0.00] | 0/0 | n/a | n/a | n/a | n/a | n/a |
| gpt-4.1 B_noVolatile×F3 (COP) vs B_full×F1, rep 1 (reference) | no_attribute_signal | P_now | 48 | 70.8 | 45.8 | -25.00 | [-42.31, -8.00] | 3/15 | 0.20 [0.04, 0.71] | 0.0047 | 0.0075 | raw only | raw only |

Direction: o4-mini Δ(COP − B_full×F1) = +9.17 pp; gpt-4.1 (rep 1) = +10.00 pp → same sign: **True**.
Re-issued events in block 4: 2 (excluded: page_01 t_10, page_02 t_09).

## Multiplicity note

The Holm sets above follow the committed analysis plan (`f1c78b5`). Under an alternative set membership with B_full_minus_state included in the F2 set, the exact Holm p for B_full_minus_volId×F1 vs B_full×F1 (P5) is 0.098 instead of 0.049; its Δ, b/c and CI are unchanged. The other alternatives (the F4 sensitivity row outside the F4 set, the minus_aria subset rows as raw-only instead of singleton sets, exact p = 1 kept in the set instead of n/a when b + c = 0) change no conclusion.

## Exploratory (not in the plan)

Failure modes per batch cell (records called in the batch):

| block | model | bundle | enc | rep | success | lacked | grabbed | unreachable |
|---|---|---|---|---|---|---|---|---|
| 1 | gpt-4.1 | B_full_minus_aria | F1 | 1 | 119 | 93 | 28 | 0 |
| 1 | gpt-4.1 | B_full_minus_volClass | F1 | 1 | 144 | 44 | 12 | 0 |
| 1 | gpt-4.1 | B_full_minus_volId | F1 | 1 | 136 | 43 | 41 | 0 |
| 2 | gpt-4.1 | B_full | F2L | 1 | 143 | 48 | 49 | 0 |
| 2 | gpt-4.1 | B_noVolatile | F2L | 1 | 162 | 48 | 30 | 0 |
| 2 | gpt-4.1-nano | B_noVolatile | F2L | 1 | 61 | 48 | 131 | 0 |
| 3 | gpt-4.1 | B_full | F1 | 2 | 144 | 48 | 48 | 0 |
| 3 | gpt-4.1 | B_full | F1 | 3 | 142 | 48 | 50 | 0 |
| 3 | gpt-4.1 | B_noVolatile | F1 | 2 | 165 | 48 | 27 | 0 |
| 3 | gpt-4.1 | B_noVolatile | F1 | 3 | 164 | 48 | 28 | 0 |
| 3 | gpt-4.1 | B_noVolatile | F2 | 2 | 136 | 48 | 56 | 0 |
| 3 | gpt-4.1 | B_noVolatile | F2 | 3 | 135 | 48 | 57 | 0 |
| 3 | gpt-4.1 | B_noVolatile | F3 | 2 | 164 | 48 | 28 | 0 |
| 3 | gpt-4.1 | B_noVolatile | F3 | 3 | 164 | 48 | 28 | 0 |
| 3 | gpt-4.1-nano | B_noVolatile | F1 | 2 | 163 | 48 | 29 | 0 |
| 3 | gpt-4.1-nano | B_noVolatile | F1 | 3 | 164 | 48 | 28 | 0 |
| 3 | gpt-4.1-nano | B_noVolatile | F2 | 2 | 66 | 48 | 126 | 0 |
| 3 | gpt-4.1-nano | B_noVolatile | F2 | 3 | 64 | 48 | 128 | 0 |
| 4 | o4-mini | B_full | F1 | 1 | 159 | 48 | 33 | 0 |

finish_reason by block: 1|Stop 660, 2|Length 1, 2|Stop 719, 3|Stop 2880, 4|Stop 240.
llm_attempts by block: 1|1 641, 1|2 18, 1|3 1, 2|1 720, 3|1 2877, 3|2 3, 4|1 238, 4|2 2.

Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: 120 SHA-256 equal.
