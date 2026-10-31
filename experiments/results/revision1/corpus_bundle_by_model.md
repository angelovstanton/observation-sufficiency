# Corpus — B_full vs B_noVolatile per model

**EXPLORATORY — not pre-registered; existing corpus and batch records only, computed after the registered batch analysis and the real-site pilot results (f6a00d3).**

Existing records only, no model calls. Loading, checks, strata (`has_attribute_signal` / `no_attribute_signal` from `shared/testbed/pages/*.truth.json`) and statistics are those of the registered `revision1_batch_analysis.py`: Δ = second − first (pp); McNemar exact binomial p (b = second-only, c = first-only); 95% CI = page-clustered percentile bootstrap (10,000 draws, seed 42). P5 is 0 in `no_attribute_signal` by construction, so that stratum is shown for P_now only. Claude's arms are paired on the events present in both cells (TPM-skipped events are missing). gpt-4.1 and gpt-4.1-nano at temperature 0; o4-mini at the service default; rep 1 = the original corpus run, reps 2-3 and F2L = the revision-1 batch. No multiplicity correction (exploratory).

## Paired comparisons

| model | comparison | stratum | n | P5 first % | P5 second % | Δ P5 pp [95% CI] | p exact | P_now first % | P_now second % | Δ P_now pp [95% CI] | p exact |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-4.1 | B_noVolatile vs B_full, F0, rep 1 | overall | 240 | 56.7 | 66.2 | +9.58 [+4.17, +15.83] | 5.65e-06 | 86.7 | 80.0 | -6.67 [-12.08, -1.67] | 0.0037 |
| gpt-4.1 | B_noVolatile vs B_full, F0, rep 1 | has_attribute_signal | 192 | 70.8 | 82.8 | +11.98 [+5.29, +19.78] | 5.65e-06 | 94.8 | 93.2 | -1.56 [-6.32, +3.55] | 0.5811 |
| gpt-4.1 | B_noVolatile vs B_full, F0, rep 1 | no_attribute_signal | 48 | — | — | — | — | 54.2 | 27.1 | -27.08 [-42.00, -13.95] | 9.77e-04 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 1 | overall | 240 | 57.9 | 67.5 | +9.58 [+3.33, +16.67] | 1.52e-05 | 90.4 | 83.8 | -6.67 [-11.67, -2.08] | 0.0037 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 1 | has_attribute_signal | 192 | 72.4 | 84.4 | +11.98 [+4.19, +21.39] | 1.52e-05 | 95.3 | 94.8 | -0.52 [-5.18, +3.63] | 1.0000 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 1 | no_attribute_signal | 48 | — | — | — | — | 70.8 | 39.6 | -31.25 [-50.94, -12.28] | 7.29e-04 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 2 | overall | 240 | 60.0 | 68.8 | +8.75 [+3.33, +15.83] | 4.92e-05 | 90.8 | 85.8 | -5.00 [-9.17, -1.25] | 0.0290 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 2 | has_attribute_signal | 192 | 75.0 | 85.9 | +10.94 [+4.04, +20.00] | 4.92e-05 | 94.8 | 96.9 | +2.08 [-1.06, +5.73] | 0.2891 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 2 | no_attribute_signal | 48 | — | — | — | — | 75.0 | 41.7 | -33.33 [-50.88, -16.33] | 1.45e-04 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 3 | overall | 240 | 59.2 | 68.3 | +9.17 [+3.75, +15.84] | 1.05e-05 | 92.1 | 84.2 | -7.92 [-12.50, -3.75] | 1.57e-04 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 3 | has_attribute_signal | 192 | 74.0 | 85.4 | +11.46 [+4.66, +20.42] | 1.05e-05 | 96.4 | 95.8 | -0.52 [-3.61, +2.05] | 1.0000 |
| gpt-4.1 | B_noVolatile vs B_full, F1, rep 3 | no_attribute_signal | 48 | — | — | — | — | 75.0 | 37.5 | -37.50 [-54.35, -20.41] | 4.01e-05 |
| gpt-4.1 | B_noVolatile vs B_full, F2, rep 1 | overall | 240 | 47.1 | 55.4 | +8.33 [+2.50, +15.42] | 3.25e-04 | 75.8 | 69.6 | -6.25 [-11.25, -1.25] | 0.0107 |
| gpt-4.1 | B_noVolatile vs B_full, F2, rep 1 | has_attribute_signal | 192 | 58.9 | 69.3 | +10.42 [+3.16, +19.36] | 3.25e-04 | 79.7 | 78.1 | -1.56 [-6.95, +3.55] | 0.6476 |
| gpt-4.1 | B_noVolatile vs B_full, F2, rep 1 | no_attribute_signal | 48 | — | — | — | — | 60.4 | 35.4 | -25.00 [-40.43, -12.00] | 4.88e-04 |
| gpt-4.1 | B_noVolatile vs B_full, F2L, rep 1 | overall | 240 | 59.6 | 67.5 | +7.92 [+2.92, +15.00] | 1.57e-04 | 90.4 | 81.2 | -9.17 [-13.75, -5.00] | 1.13e-04 |
| gpt-4.1 | B_noVolatile vs B_full, F2L, rep 1 | has_attribute_signal | 192 | 74.5 | 84.4 | +9.90 [+3.52, +18.82] | 1.57e-04 | 94.3 | 93.2 | -1.04 [-4.04, +1.64] | 0.7539 |
| gpt-4.1 | B_noVolatile vs B_full, F2L, rep 1 | no_attribute_signal | 48 | — | — | — | — | 75.0 | 33.3 | -41.67 [-58.33, -25.45] | 1.10e-05 |
| gpt-4.1 | B_noVolatile vs B_full, F3, rep 1 | overall | 240 | 57.5 | 67.9 | +10.42 [+5.00, +17.08] | 4.17e-07 | 90.4 | 85.8 | -4.58 [-8.33, -0.83] | 0.0266 |
| gpt-4.1 | B_noVolatile vs B_full, F3, rep 1 | has_attribute_signal | 192 | 71.9 | 84.9 | +13.02 [+6.15, +21.70] | 4.17e-07 | 94.8 | 95.8 | +1.04 [-1.55, +3.61] | 0.6875 |
| gpt-4.1 | B_noVolatile vs B_full, F3, rep 1 | no_attribute_signal | 48 | — | — | — | — | 72.9 | 45.8 | -27.08 [-44.68, -11.32] | 9.77e-04 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | overall | 240 | 57.9 | 67.9 | +10.00 [+4.17, +17.08] | 1.93e-05 | 90.4 | 85.8 | -4.58 [-9.17, -0.42] | 0.0433 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | has_attribute_signal | 192 | 72.4 | 84.9 | +12.50 [+5.08, +21.93] | 1.93e-05 | 95.3 | 95.8 | +0.52 [-2.56, +3.70] | 1.0000 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | no_attribute_signal | 48 | — | — | — | — | 70.8 | 45.8 | -25.00 [-42.31, -8.00] | 0.0075 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 2 | overall | 240 | 60.0 | 68.3 | +8.33 [+2.50, +15.42] | 8.80e-05 | 90.8 | 84.6 | -6.25 [-10.83, -1.67] | 0.0081 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 2 | has_attribute_signal | 192 | 75.0 | 85.4 | +10.42 [+3.12, +19.68] | 8.80e-05 | 94.8 | 95.8 | +1.04 [-2.14, +4.74] | 0.7266 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 2 | no_attribute_signal | 48 | — | — | — | — | 75.0 | 39.6 | -35.42 [-53.19, -17.65] | 2.21e-04 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 3 | overall | 240 | 59.2 | 68.3 | +9.17 [+3.75, +16.25] | 2.74e-05 | 92.1 | 84.6 | -7.50 [-12.08, -3.33] | 9.12e-04 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 3 | has_attribute_signal | 192 | 74.0 | 85.4 | +11.46 [+4.52, +20.74] | 2.74e-05 | 96.4 | 95.8 | -0.52 [-2.72, +1.59] | 1.0000 |
| gpt-4.1 | COP (B_noVolatile×F3) vs B_full×F1, rep 3 | no_attribute_signal | 48 | — | — | — | — | 75.0 | 39.6 | -35.42 [-53.19, -17.65] | 2.21e-04 |
| gpt-4.1-nano | B_noVolatile vs B_full, F1, rep 1 | overall | 240 | 61.3 | 67.9 | +6.67 [+0.42, +13.33] | 0.0037 | 80.4 | 73.8 | -6.67 [-12.08, -1.25] | 0.0090 |
| gpt-4.1-nano | B_noVolatile vs B_full, F1, rep 1 | has_attribute_signal | 192 | 76.6 | 84.9 | +8.33 [+0.51, +16.76] | 0.0037 | 87.5 | 87.5 | +0.00 [-5.56, +5.29] | 1.0000 |
| gpt-4.1-nano | B_noVolatile vs B_full, F1, rep 1 | no_attribute_signal | 48 | — | — | — | — | 52.1 | 18.8 | -33.33 [-51.02, -16.67] | 1.45e-04 |
| gpt-4.1-nano | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | overall | 240 | 61.3 | 66.2 | +5.00 [-2.08, +12.08] | 0.1114 | 80.4 | 72.1 | -8.33 [-14.17, -2.50] | 0.0055 |
| gpt-4.1-nano | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | has_attribute_signal | 192 | 76.6 | 82.8 | +6.25 [-2.55, +15.26] | 0.1114 | 87.5 | 84.9 | -2.60 [-8.76, +3.13] | 0.4421 |
| gpt-4.1-nano | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | no_attribute_signal | 48 | — | — | — | — | 52.1 | 20.8 | -31.25 [-50.00, -13.04] | 0.0015 |
| o4-mini | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | overall | 240 | 66.2 | 75.4 | +9.17 [+4.58, +14.58] | 2.98e-06 | 93.8 | 90.8 | -2.92 [-5.42, -0.42] | 0.1185 |
| o4-mini | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | has_attribute_signal | 192 | 82.8 | 94.3 | +11.46 [+5.55, +18.32] | 2.98e-06 | 96.4 | 97.9 | +1.56 [+0.00, +3.21] | 0.2500 |
| o4-mini | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | no_attribute_signal | 48 | — | — | — | — | 83.3 | 62.5 | -20.83 [-33.33, -9.09] | 0.0063 |
| claude-sonnet-4-6 | B_noVolatile vs B_full, F1, rep 1 | overall | 210 | 71.4 | 77.6 | +6.19 [+2.38, +10.95] | 2.44e-04 | 94.3 | 87.6 | -6.67 [-10.95, -2.38] | 0.0013 |
| claude-sonnet-4-6 | B_noVolatile vs B_full, F1, rep 1 | has_attribute_signal | 168 | 89.3 | 97.0 | +7.74 [+2.94, +13.94] | 2.44e-04 | 98.8 | 98.2 | -0.60 [-1.83, +0.00] | 1.0000 |
| claude-sonnet-4-6 | B_noVolatile vs B_full, F1, rep 1 | no_attribute_signal | 42 | — | — | — | — | 76.2 | 45.2 | -30.95 [-51.11, -10.81] | 0.0023 |
| claude-sonnet-4-6 | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | overall | 210 | 71.4 | 75.7 | +4.29 [-0.48, +10.00] | 0.0490 | 94.3 | 87.6 | -6.67 [-10.48, -2.38] | 0.0013 |
| claude-sonnet-4-6 | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | has_attribute_signal | 168 | 89.3 | 94.6 | +5.36 [-0.60, +12.57] | 0.0490 | 98.8 | 96.4 | -2.38 [-4.65, -0.59] | 0.1250 |
| claude-sonnet-4-6 | COP (B_noVolatile×F3) vs B_full×F1, rep 1 | no_attribute_signal | 42 | — | — | — | — | 76.2 | 52.4 | -23.81 [-41.67, -5.13] | 0.0129 |

Paired events where a cell is incomplete: claude-sonnet-4-6 B_noVolatile vs B_full, F1, rep 1: 210 paired (210 / 220 in the cells); claude-sonnet-4-6 COP (B_noVolatile×F3) vs B_full×F1, rep 1: 210 paired (210 / 230 in the cells).

## Comparisons not possible (cell missing)

| model | comparison | missing arm |
|---|---|---|
| gpt-4.1 | B_noVolatile vs B_full, F2, rep 2 | B_full |
| gpt-4.1 | B_noVolatile vs B_full, F2, rep 3 | B_full |
| gpt-4.1 | B_noVolatile vs B_full, F3, rep 2 | B_full |
| gpt-4.1 | B_noVolatile vs B_full, F3, rep 3 | B_full |
| gpt-4.1-nano | B_noVolatile vs B_full, F1, rep 2 | B_full |
| gpt-4.1-nano | B_noVolatile vs B_full, F1, rep 3 | B_full |
| gpt-4.1-nano | B_noVolatile vs B_full, F2, rep 1 | B_full |
| gpt-4.1-nano | B_noVolatile vs B_full, F2, rep 2 | B_full |
| gpt-4.1-nano | B_noVolatile vs B_full, F2, rep 3 | B_full |
| gpt-4.1-nano | B_noVolatile vs B_full, F2L, rep 1 | B_full |
| gpt-4.1-nano | B_noVolatile vs B_full, F3, rep 1 | B_full |
| o4-mini | B_noVolatile vs B_full, F1, rep 1 | B_noVolatile |
| o4-mini | B_noVolatile vs B_full, F3, rep 1 | B_full |
| claude-sonnet-4-6 | B_noVolatile vs B_full, F2, rep 1 | B_full |
| claude-sonnet-4-6 | B_noVolatile vs B_full, F3, rep 1 | B_full |

Also not in these records: B_noVolatileConsistent exists for gpt-4.1 only, on 6 pages (`consistent_runs/`, see `sensitivity_consistent.md`); no model other than gpt-4.1 has F0 or B_noVolatile×F2L with B_full.

## Cells present (B_full, B_noVolatile)

| model | bundle | enc | rep | records | pages | missing pages | partial pages | origin |
|---|---|---|---|---|---|---|---|---|
| gpt-4.1 | B_full | F0 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_full | F1 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_full | F1 | 2 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_full | F1 | 3 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_full | F2 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_full | F2L | 1 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_full | F3 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_noVolatile | F0 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_noVolatile | F1 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_noVolatile | F1 | 2 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_noVolatile | F1 | 3 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_noVolatile | F2 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_noVolatile | F2 | 2 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_noVolatile | F2 | 3 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_noVolatile | F2L | 1 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_noVolatile | F3 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1 | B_noVolatile | F3 | 2 | 240 | 24 | — | — | batch |
| gpt-4.1 | B_noVolatile | F3 | 3 | 240 | 24 | — | — | batch |
| gpt-4.1-nano | B_full | F1 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1-nano | B_noVolatile | F1 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1-nano | B_noVolatile | F1 | 2 | 240 | 24 | — | — | batch |
| gpt-4.1-nano | B_noVolatile | F1 | 3 | 240 | 24 | — | — | batch |
| gpt-4.1-nano | B_noVolatile | F2 | 1 | 240 | 24 | — | — | corpus |
| gpt-4.1-nano | B_noVolatile | F2 | 2 | 240 | 24 | — | — | batch |
| gpt-4.1-nano | B_noVolatile | F2 | 3 | 240 | 24 | — | — | batch |
| gpt-4.1-nano | B_noVolatile | F2L | 1 | 240 | 24 | — | — | batch |
| gpt-4.1-nano | B_noVolatile | F3 | 1 | 240 | 24 | — | — | corpus |
| o4-mini | B_full | F1 | 1 | 240 | 24 | — | — | batch |
| o4-mini | B_noVolatile | F3 | 1 | 240 | 24 | — | — | corpus |
| claude-sonnet-4-6 | B_full | F1 | 1 | 210 | 21 | page_08, page_17, page_18 | — | corpus |
| claude-sonnet-4-6 | B_noVolatile | F1 | 1 | 220 | 22 | page_08, page_17 | — | corpus |
| claude-sonnet-4-6 | B_noVolatile | F2 | 1 | 220 | 22 | page_08, page_17 | — | corpus |
| claude-sonnet-4-6 | B_noVolatile | F3 | 1 | 230 | 23 | page_17 | — | corpus |
