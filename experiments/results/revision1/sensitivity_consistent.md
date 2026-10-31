# Revision 1 — sensitivity: B_noVolatileConsistent vs B_full

Facts only. B_noVolatileConsistent (NVC) removes every class/id token that the success predicate flags (`Oracle.LocatorUsesVolatileSignal`), in addition to what B_noVolatile (NV) removes (see `leak_scope.md`). Event set (960 = 24 pages × 10 targets × F0–F3):

- **new_run** — 240 records: the 24 (page, encoding) cells whose NVC observation differs from NV (page_17, page_18, page_21, page_22, page_23, page_24 × F0–F3); `SENSITIVITY_CONSISTENT=1`, gpt-4.1, temperature 0, full_page, repetition 0, canonical prompt; `experiments/results/revision1/consistent_runs/`.
- **original_B_noVolatile (identical observation)** — 720 records: the 72 cells whose NVC observation is byte-identical to NV; the stored corpus NV record is used unchanged.

Statistics: McNemar uncorrected χ² and exact binomial p; OR = b/c with exact conditional 95% CI; page-clustered percentile bootstrap of Δ (10,000 replicates, seed 42, draw sequence of `stats.py`). The NV columns repeat the corpus numbers for side-by-side reading.

Run checks: new-record observation tokens equal the dumped NVC tokens: yes; new-record condition 5 equals the stored NV record: yes; no_attribute_signal events = condition-5-false events under NVC: yes.

## 1. B_full vs B_noVolatileConsistent — 960 pairs

| predicate | B_full | NVC | Δ pp | both | NVC-only (b) | B_full-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P5 | 526/960 (54.79%) | 683/960 (71.15%) | +16.35 | 517 | 166 | 9 | 268 | 140.85 | 1.73e-32 | 1.52e-38 | 18.44 | [9.48, 41.05] | [+10.42, +23.12] |
| P_now | 824/960 (85.83%) | 755/960 (78.65%) | -7.19 | 728 | 27 | 96 | 109 | 38.71 | 4.92e-10 | 2.91e-10 | 0.28 | [0.18, 0.43] | [-11.46, -3.33] |
| P_now_np | 801/960 (83.44%) | 736/960 (76.67%) | -6.77 | 713 | 23 | 88 | 136 | 38.06 | 6.85e-10 | 3.80e-10 | 0.26 | [0.16, 0.42] | [-10.94, -2.92] |

Reference — B_full vs B_noVolatile (corpus), same 960 pairs:

| predicate | B_full | NV | Δ pp | both | NV-only (b) | B_full-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P5 | 526/960 (54.79%) | 617/960 (64.27%) | +9.48 | 515 | 102 | 11 | 332 | 73.28 | 1.12e-17 | 1.25e-19 | 9.27 | [4.97, 19.16] | [+4.90, +15.52] |
| P_now | 824/960 (85.83%) | 766/960 (79.79%) | -6.04 | 741 | 25 | 83 | 111 | 31.15 | 2.39e-08 | 1.88e-08 | 0.30 | [0.18, 0.48] | [-9.90, -2.50] |
| P_now_np | 801/960 (83.44%) | 751/960 (78.23%) | -5.21 | 729 | 22 | 72 | 137 | 26.60 | 2.51e-07 | 2.26e-07 | 0.31 | [0.18, 0.50] | [-8.85, -1.77] |

### 1a. By target design stratum (D1b)

| stratum | predicate | B_full | NVC | Δ pp | both | NVC-only (b) | B_full-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| has_attribute_signal (n=768) | P5 | 526/768 (68.49%) | 683/768 (88.93%) | +20.44 | 517 | 166 | 9 | 76 | 140.85 | 1.73e-32 | 1.52e-38 | 18.44 | [9.48, 41.05] | [+12.88, +29.23] |
| has_attribute_signal (n=768) | P_now | 700/768 (91.15%) | 685/768 (89.19%) | -1.95 | 663 | 22 | 37 | 46 | 3.81 | 0.0508 | 0.0674 | 0.59 | [0.33, 1.03] | [-5.47, +1.16] |
| has_attribute_signal (n=768) | P_now_np | 695/768 (90.49%) | 684/768 (89.06%) | -1.43 | 661 | 23 | 34 | 50 | 2.12 | 0.1451 | 0.1849 | 0.68 | [0.38, 1.18] | [-4.87, +1.66] |
| NONE (n=188) | P5 | 0/188 (0.00%) | 0/188 (0.00%) | +0.00 | 0 | 0 | 0 | 188 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| NONE (n=188) | P_now | 121/188 (64.36%) | 67/188 (35.64%) | -28.72 | 62 | 5 | 59 | 62 | 45.56 | 1.48e-11 | 9.00e-13 | 0.08 | [0.03, 0.21] | [-43.50, -15.10] |
| NONE (n=188) | P_now_np | 103/188 (54.79%) | 49/188 (26.06%) | -28.72 | 49 | 0 | 54 | 85 | 54.00 | 2.00e-13 | 1.11e-16 | 0.00 | [0.00, 0.07] | [-42.31, -16.49] |
| text_only_signal (n=4) | P5 | 0/4 (0.00%) | 0/4 (0.00%) | +0.00 | 0 | 0 | 0 | 4 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=4) | P_now | 3/4 (75.00%) | 3/4 (75.00%) | +0.00 | 3 | 0 | 0 | 1 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=4) | P_now_np | 3/4 (75.00%) | 3/4 (75.00%) | +0.00 | 3 | 0 | 0 | 1 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=192) | P5 | 0/192 (0.00%) | 0/192 (0.00%) | +0.00 | 0 | 0 | 0 | 192 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=192) | P_now | 124/192 (64.58%) | 70/192 (36.46%) | -28.12 | 65 | 5 | 59 | 63 | 45.56 | 1.48e-11 | 9.00e-13 | 0.08 | [0.03, 0.21] | [-42.79, -14.71] |
| no_attribute_signal (NONE + text-only) (n=192) | P_now_np | 106/192 (55.21%) | 52/192 (27.08%) | -28.12 | 52 | 0 | 54 | 86 | 54.00 | 2.00e-13 | 1.11e-16 | 0.00 | [0.00, 0.07] | [-41.67, -16.15] |

Reference — B_full vs NV by stratum:

| stratum | predicate | B_full | NV | Δ pp | both | NV-only (b) | B_full-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| has_attribute_signal (n=768) | P5 | 526/768 (68.49%) | 617/768 (80.34%) | +11.85 | 515 | 102 | 11 | 140 | 73.28 | 1.12e-17 | 1.25e-19 | 9.27 | [4.97, 19.16] | [+6.12, +19.60] |
| has_attribute_signal (n=768) | P_now | 700/768 (91.15%) | 695/768 (90.49%) | -0.65 | 674 | 21 | 26 | 47 | 0.53 | 0.4658 | 0.5601 | 0.81 | [0.43, 1.49] | [-3.99, +2.45] |
| has_attribute_signal (n=768) | P_now_np | 695/768 (90.49%) | 694/768 (90.36%) | -0.13 | 672 | 22 | 23 | 51 | 0.02 | 0.8815 | 1.0000 | 0.96 | [0.51, 1.80] | [-3.44, +2.84] |
| NONE (n=188) | P5 | 0/188 (0.00%) | 0/188 (0.00%) | +0.00 | 0 | 0 | 0 | 188 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| NONE (n=188) | P_now | 121/188 (64.36%) | 68/188 (36.17%) | -28.19 | 64 | 4 | 57 | 63 | 46.05 | 1.15e-11 | 4.85e-13 | 0.07 | [0.02, 0.19] | [-42.61, -15.12] |
| NONE (n=188) | P_now_np | 103/188 (54.79%) | 54/188 (28.72%) | -26.06 | 54 | 0 | 49 | 85 | 49.00 | 2.56e-12 | 3.55e-15 | 0.00 | [0.00, 0.08] | [-38.89, -14.80] |
| text_only_signal (n=4) | P5 | 0/4 (0.00%) | 0/4 (0.00%) | +0.00 | 0 | 0 | 0 | 4 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=4) | P_now | 3/4 (75.00%) | 3/4 (75.00%) | +0.00 | 3 | 0 | 0 | 1 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=4) | P_now_np | 3/4 (75.00%) | 3/4 (75.00%) | +0.00 | 3 | 0 | 0 | 1 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=192) | P5 | 0/192 (0.00%) | 0/192 (0.00%) | +0.00 | 0 | 0 | 0 | 192 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=192) | P_now | 124/192 (64.58%) | 71/192 (36.98%) | -27.60 | 67 | 4 | 57 | 64 | 46.05 | 1.15e-11 | 4.85e-13 | 0.07 | [0.02, 0.19] | [-41.86, -14.77] |
| no_attribute_signal (NONE + text-only) (n=192) | P_now_np | 106/192 (55.21%) | 57/192 (29.69%) | -25.52 | 57 | 0 | 49 | 86 | 49.00 | 2.56e-12 | 3.55e-15 | 0.00 | [0.00, 0.08] | [-38.30, -14.42] |

### 1b. Transition matrices

B_full state → NVC state (960):

| B_full ↓ / NVC → | success | grabbed | lacked | unreach | total |
|---|---|---|---|---|---|
| success | 517 | 9 | 0 | 0 | 526 |
| grabbed | 166 | 76 | 0 | 0 | 242 |
| lacked | 0 | 0 | 192 | 0 | 192 |
| unreach | 0 | 0 | 0 | 0 | 0 |
| total | 683 | 85 | 192 | 0 | 960 |

Reference — B_full state → NV state (960):

| B_full ↓ / NV → | success | grabbed | lacked | unreach | total |
|---|---|---|---|---|---|
| success | 515 | 11 | 0 | 0 | 526 |
| grabbed | 102 | 140 | 0 | 0 | 242 |
| lacked | 0 | 0 | 192 | 0 | 192 |
| unreach | 0 | 0 | 0 | 0 | 0 |
| total | 617 | 151 | 192 | 0 | 960 |

NV state → NVC state on the 240 re-run events (the other 720 are identical by construction):

| NV ↓ / NVC → | success | grabbed | lacked | unreach | total |
|---|---|---|---|---|---|
| success | 94 | 6 | 0 | 0 | 100 |
| grabbed | 72 | 16 | 0 | 0 | 88 |
| lacked | 0 | 0 | 52 | 0 | 52 |
| unreach | 0 | 0 | 0 | 0 | 0 |

Volatile locators (`predicate_non_volatile = false`), all 960: NVC 7, NV 119. Grabbed: NVC 85 (volatile 2), NV 151 (volatile 84).

### 1c. NV vs NVC on the 240 re-run events

| predicate | NV | NVC | Δ pp | both | NVC-only (b) | NV-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| P5 | 100/240 (41.67%) | 166/240 (69.17%) | +27.50 | 94 | 72 | 6 | 68 | 55.85 | 7.84e-14 | 1.85e-15 | 12.00 | [5.25, 33.78] | [+10.00, +42.50] |
| P_now | 187/240 (77.92%) | 176/240 (73.33%) | -4.58 | 167 | 9 | 20 | 44 | 4.17 | 0.0411 | 0.0614 | 0.45 | [0.18, 1.03] | [-7.50, -1.25] |
| P_now_np | 184/240 (76.67%) | 169/240 (70.42%) | -6.25 | 164 | 5 | 20 | 51 | 9.00 | 0.0027 | 0.0041 | 0.25 | [0.07, 0.69] | [-9.17, -2.92] |

## 2. COP cell — NVC×F3 vs B_full×F1 (240 pairs)

| stratum | predicate | B_full×F1 | NVC×F3 | Δ pp | both | NVC×F3-only (b) | B_full×F1-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all (n=240) | P5 | 139/240 (57.92%) | 184/240 (76.67%) | +18.75 | 138 | 46 | 1 | 55 | 43.09 | 5.24e-11 | 6.82e-13 | 46.00 | [7.85, 1855.90] | [+11.25, +27.50] |
| all (n=240) | P_now | 217/240 (90.42%) | 209/240 (87.08%) | -3.33 | 200 | 9 | 17 | 14 | 2.46 | 0.1167 | 0.1686 | 0.53 | [0.21, 1.26] | [-8.33, +1.67] |
| all (n=240) | P_now_np | 212/240 (88.33%) | 200/240 (83.33%) | -5.00 | 195 | 5 | 17 | 23 | 6.55 | 0.0105 | 0.0169 | 0.29 | [0.08, 0.83] | [-9.58, -0.83] |
| has_attribute_signal (n=192) | P5 | 139/192 (72.40%) | 184/192 (95.83%) | +23.44 | 138 | 46 | 1 | 7 | 43.09 | 5.24e-11 | 6.82e-13 | 46.00 | [7.85, 1855.90] | [+13.76, +34.60] |
| has_attribute_signal (n=192) | P_now | 183/192 (95.31%) | 185/192 (96.35%) | +1.04 | 180 | 5 | 3 | 4 | 0.50 | 0.4795 | 0.7266 | 1.67 | [0.32, 10.73] | [-2.14, +4.76] |
| has_attribute_signal (n=192) | P_now_np | 182/192 (94.79%) | 184/192 (95.83%) | +1.04 | 179 | 5 | 3 | 5 | 0.50 | 0.4795 | 0.7266 | 1.67 | [0.32, 10.73] | [-2.14, +4.76] |
| NONE (n=47) | P5 | 0/47 (0.00%) | 0/47 (0.00%) | +0.00 | 0 | 0 | 0 | 47 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| NONE (n=47) | P_now | 33/47 (70.21%) | 23/47 (48.94%) | -21.28 | 19 | 4 | 14 | 10 | 5.56 | 0.0184 | 0.0309 | 0.29 | [0.07, 0.91] | [-39.53, -2.50] |
| NONE (n=47) | P_now_np | 29/47 (61.70%) | 15/47 (31.91%) | -29.79 | 15 | 0 | 14 | 18 | 14.00 | 1.83e-04 | 1.22e-04 | 0.00 | [0.00, 0.30] | [-45.24, -15.55] |
| text_only_signal (n=1) | P5 | 0/1 (0.00%) | 0/1 (0.00%) | +0.00 | 0 | 0 | 0 | 1 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=1) | P_now | 1/1 (100.00%) | 1/1 (100.00%) | +0.00 | 1 | 0 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=1) | P_now_np | 1/1 (100.00%) | 1/1 (100.00%) | +0.00 | 1 | 0 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=48) | P5 | 0/48 (0.00%) | 0/48 (0.00%) | +0.00 | 0 | 0 | 0 | 48 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=48) | P_now | 34/48 (70.83%) | 24/48 (50.00%) | -20.83 | 20 | 4 | 14 | 10 | 5.56 | 0.0184 | 0.0309 | 0.29 | [0.07, 0.91] | [-38.78, -2.44] |
| no_attribute_signal (NONE + text-only) (n=48) | P_now_np | 30/48 (62.50%) | 16/48 (33.33%) | -29.17 | 16 | 0 | 14 | 18 | 14.00 | 1.83e-04 | 1.22e-04 | 0.00 | [0.00, 0.30] | [-44.68, -14.89] |

Reference — NV×F3 (published COP) vs B_full×F1:

| stratum | predicate | B_full×F1 | NV×F3 | Δ pp | both | NV×F3-only (b) | B_full×F1-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all (n=240) | P5 | 139/240 (57.92%) | 163/240 (67.92%) | +10.00 | 135 | 28 | 4 | 73 | 18.00 | 2.21e-05 | 1.93e-05 | 7.00 | [2.45, 27.47] | [+4.17, +17.08] |
| all (n=240) | P_now | 217/240 (90.42%) | 206/240 (85.83%) | -4.58 | 199 | 7 | 18 | 16 | 4.84 | 0.0278 | 0.0433 | 0.39 | [0.14, 0.98] | [-9.17, -0.42] |
| all (n=240) | P_now_np | 212/240 (88.33%) | 199/240 (82.92%) | -5.42 | 195 | 4 | 17 | 24 | 8.05 | 0.0046 | 0.0072 | 0.24 | [0.06, 0.72] | [-9.58, -1.67] |
| has_attribute_signal (n=192) | P5 | 139/192 (72.40%) | 163/192 (84.90%) | +12.50 | 135 | 28 | 4 | 25 | 18.00 | 2.21e-05 | 1.93e-05 | 7.00 | [2.45, 27.47] | [+5.08, +21.93] |
| has_attribute_signal (n=192) | P_now | 183/192 (95.31%) | 184/192 (95.83%) | +0.52 | 180 | 4 | 3 | 5 | 0.14 | 0.7055 | 1.0000 | 1.33 | [0.23, 9.10] | [-2.56, +3.70] |
| has_attribute_signal (n=192) | P_now_np | 182/192 (94.79%) | 183/192 (95.31%) | +0.52 | 179 | 4 | 3 | 6 | 0.14 | 0.7055 | 1.0000 | 1.33 | [0.23, 9.10] | [-2.56, +3.70] |
| NONE (n=47) | P5 | 0/47 (0.00%) | 0/47 (0.00%) | +0.00 | 0 | 0 | 0 | 47 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| NONE (n=47) | P_now | 33/47 (70.21%) | 21/47 (44.68%) | -25.53 | 18 | 3 | 15 | 11 | 8.00 | 0.0047 | 0.0075 | 0.20 | [0.04, 0.71] | [-43.14, -8.16] |
| NONE (n=47) | P_now_np | 29/47 (61.70%) | 15/47 (31.91%) | -29.79 | 15 | 0 | 14 | 18 | 14.00 | 1.83e-04 | 1.22e-04 | 0.00 | [0.00, 0.30] | [-45.24, -15.55] |
| text_only_signal (n=1) | P5 | 0/1 (0.00%) | 0/1 (0.00%) | +0.00 | 0 | 0 | 0 | 1 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=1) | P_now | 1/1 (100.00%) | 1/1 (100.00%) | +0.00 | 1 | 0 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| text_only_signal (n=1) | P_now_np | 1/1 (100.00%) | 1/1 (100.00%) | +0.00 | 1 | 0 | 0 | 0 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=48) | P5 | 0/48 (0.00%) | 0/48 (0.00%) | +0.00 | 0 | 0 | 0 | 48 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=48) | P_now | 34/48 (70.83%) | 22/48 (45.83%) | -25.00 | 19 | 3 | 15 | 11 | 8.00 | 0.0047 | 0.0075 | 0.20 | [0.04, 0.71] | [-42.31, -8.00] |
| no_attribute_signal (NONE + text-only) (n=48) | P_now_np | 30/48 (62.50%) | 16/48 (33.33%) | -29.17 | 16 | 0 | 14 | 18 | 14.00 | 1.83e-04 | 1.22e-04 | 0.00 | [0.00, 0.30] | [-44.68, -14.89] |

## 3. Tokens (mean observation tokens per event, o200k_base)

| encoding | B_full | B_noVolatile | NVC | NVC − NV |
|---|---|---|---|---|
| F0 | 22,267.9 | 20,510.5 | 18,976.9 | -1,533.6 |
| F1 | 27,096.7 | 25,238.1 | 23,615.1 | -1,623.0 |
| F2 | 27,047.3 | 25,188.9 | 23,566.0 | -1,622.9 |
| F3 | 19,633.0 | 17,887.5 | 16,394.2 | -1,493.2 |

B_playwrightMCP×F4: 8,914.2.

| reduction | % |
|---|---|
| NVC×F3 vs B_full×F1 % | 39.5 |
| NV×F3 vs B_full×F1 % (published COP) | 34.0 |
| NVC×F3 vs NV×F3 % | 8.3 |
| NVC×F3 vs NVC×F1 % | 30.6 |

## 4. Pareto position (25 cells: the 21 published cells + 4 NVC cells)

Frontier walk of `pareto.py` (sort by cost, keep strictly improving success); COP rule = first frontier cell with success > 50%.

*Cost = observation tokens (o200k_base)*

| bundle | enc | success | mean cost | status |
|---|---|---|---|---|
| B_identityCore | F3 | 98/240 (40.83%) | 179.7 | FRONTIER |
| B_identityCore | F0 | 100/240 (41.67%) | 225.0 | FRONTIER |
| B_identityCore | F2 | 90/240 (37.50%) | 237.8 | dominated |
| B_identityCore | F1 | 92/240 (38.33%) | 249.9 | dominated |
| B_playwrightMCP | F4 | 113/240 (47.08%) | 8,914.2 | FRONTIER |
| B_noSemantic | F3 | 98/240 (40.83%) | 9,212.0 | dominated |
| B_noSemantic | F0 | 87/240 (36.25%) | 11,049.8 | dominated |
| B_noSemantic | F2 | 61/240 (25.42%) | 11,881.2 | dominated |
| B_noSemantic | F1 | 93/240 (38.75%) | 11,909.8 | dominated |
| B_noVolatileConsistent | F3 | 184/240 (76.67%) | 16,394.2 | FRONTIER |
| B_noVolatile | F3 | 163/240 (67.92%) | 17,887.5 | dominated |
| B_noVolatileConsistent | F0 | 170/240 (70.83%) | 18,976.9 | dominated |
| B_noState | F3 | 139/240 (57.92%) | 19,609.3 | dominated |
| B_full | F3 | 138/240 (57.50%) | 19,633.0 | dominated |
| B_noVolatile | F0 | 159/240 (66.25%) | 20,510.5 | dominated |
| B_noState | F0 | 136/240 (56.67%) | 22,240.8 | dominated |
| B_full | F0 | 136/240 (56.67%) | 22,267.9 | dominated |
| B_noVolatileConsistent | F2 | 148/240 (61.67%) | 23,566.0 | dominated |
| B_noVolatileConsistent | F1 | 181/240 (75.42%) | 23,615.1 | dominated |
| B_noVolatile | F2 | 133/240 (55.42%) | 25,188.9 | dominated |
| B_noVolatile | F1 | 162/240 (67.50%) | 25,238.1 | dominated |
| B_noState | F2 | 114/240 (47.50%) | 27,016.9 | dominated |
| B_full | F2 | 113/240 (47.08%) | 27,047.3 | dominated |
| B_noState | F1 | 140/240 (58.33%) | 27,066.3 | dominated |
| B_full | F1 | 139/240 (57.92%) | 27,096.7 | dominated |

COP under this cost: B_noVolatileConsistent×F3. Frontier: B_identityCore×F3, B_identityCore×F0, B_playwrightMCP×F4, B_noVolatileConsistent×F3.

*Cost = prompt tokens (`prompt_tokens_total`)*

| bundle | enc | success | mean cost | status |
|---|---|---|---|---|
| B_identityCore | F3 | 98/240 (40.83%) | 276.1 | FRONTIER |
| B_identityCore | F0 | 100/240 (41.67%) | 320.4 | FRONTIER |
| B_identityCore | F2 | 90/240 (37.50%) | 333.2 | dominated |
| B_identityCore | F1 | 92/240 (38.33%) | 345.3 | dominated |
| B_playwrightMCP | F4 | 113/240 (47.08%) | 9,010.3 | FRONTIER |
| B_noSemantic | F3 | 98/240 (40.83%) | 9,308.4 | dominated |
| B_noSemantic | F0 | 87/240 (36.25%) | 11,145.2 | dominated |
| B_noSemantic | F2 | 61/240 (25.42%) | 11,976.6 | dominated |
| B_noSemantic | F1 | 93/240 (38.75%) | 12,005.2 | dominated |
| B_noVolatileConsistent | F3 | 184/240 (76.67%) | 16,490.3 | FRONTIER |
| B_noVolatile | F3 | 163/240 (67.92%) | 17,983.5 | dominated |
| B_noVolatileConsistent | F0 | 170/240 (70.83%) | 19,073.0 | dominated |
| B_noState | F3 | 139/240 (57.92%) | 19,704.7 | dominated |
| B_full | F3 | 138/240 (57.50%) | 19,728.4 | dominated |
| B_noVolatile | F0 | 159/240 (66.25%) | 20,606.6 | dominated |
| B_noState | F0 | 136/240 (56.67%) | 22,336.2 | dominated |
| B_full | F0 | 136/240 (56.67%) | 22,363.3 | dominated |
| B_noVolatileConsistent | F2 | 148/240 (61.67%) | 23,662.2 | dominated |
| B_noVolatileConsistent | F1 | 181/240 (75.42%) | 23,711.3 | dominated |
| B_noVolatile | F2 | 133/240 (55.42%) | 25,285.1 | dominated |
| B_noVolatile | F1 | 162/240 (67.50%) | 25,334.4 | dominated |
| B_noState | F2 | 114/240 (47.50%) | 27,112.4 | dominated |
| B_full | F2 | 113/240 (47.08%) | 27,142.8 | dominated |
| B_noState | F1 | 140/240 (58.33%) | 27,161.7 | dominated |
| B_full | F1 | 139/240 (57.92%) | 27,192.1 | dominated |

COP under this cost: B_noVolatileConsistent×F3. Frontier: B_identityCore×F3, B_identityCore×F0, B_playwrightMCP×F4, B_noVolatileConsistent×F3.

Frontier without the NVC cells (21 cells, observation tokens): B_identityCore×F3, B_identityCore×F0, B_playwrightMCP×F4, B_noVolatile×F3; COP B_noVolatile×F3.

## 5. Per page — the six affected pages (successes out of 10 per cell)

| page | enc | NVC source | B_full | NV | NVC | obs tokens NV | obs tokens NVC |
|---|---|---|---|---|---|---|---|
| page_17 | F0 | new_run | 0 | 0 | 3 | 92,432 | 73,981 |
| page_17 | F1 | new_run | 2 | 0 | 6 | 107,788 | 88,327 |
| page_17 | F2 | new_run | 2 | 2 | 7 | 107,531 | 88,072 |
| page_17 | F3 | new_run | 1 | 1 | 8 | 81,880 | 63,876 |
| page_18 | F0 | new_run | 3 | 2 | 3 | 58,542 | 47,377 |
| page_18 | F1 | new_run | 2 | 3 | 8 | 67,506 | 55,646 |
| page_18 | F2 | new_run | 3 | 3 | 8 | 67,458 | 55,598 |
| page_18 | F3 | new_run | 2 | 3 | 8 | 52,655 | 41,628 |
| page_21 | F0 | new_run | 0 | 5 | 4 | 4,454 | 3,427 |
| page_21 | F1 | new_run | 0 | 7 | 7 | 5,655 | 4,575 |
| page_21 | F2 | new_run | 0 | 7 | 5 | 5,631 | 4,551 |
| page_21 | F3 | new_run | 0 | 7 | 7 | 4,070 | 3,074 |
| page_22 | F0 | new_run | 2 | 4 | 7 | 28,791 | 28,233 |
| page_22 | F1 | new_run | 5 | 4 | 8 | 36,973 | 36,412 |
| page_22 | F2 | new_run | 4 | 4 | 7 | 36,916 | 36,356 |
| page_22 | F3 | new_run | 4 | 4 | 8 | 23,190 | 22,674 |
| page_23 | F0 | new_run | 7 | 7 | 8 | 13,328 | 11,920 |
| page_23 | F1 | new_run | 4 | 7 | 8 | 15,065 | 13,555 |
| page_23 | F2 | new_run | 7 | 7 | 7 | 15,027 | 13,517 |
| page_23 | F3 | new_run | 7 | 7 | 8 | 11,788 | 10,394 |
| page_24 | F0 | new_run | 3 | 3 | 7 | 12,388 | 8,190 |
| page_24 | F1 | new_run | 5 | 5 | 8 | 14,258 | 9,777 |
| page_24 | F2 | new_run | 4 | 4 | 8 | 14,218 | 9,737 |
| page_24 | F3 | new_run | 5 | 4 | 8 | 11,050 | 7,150 |

Page totals over F0–F3 (out of 40):

| page | B_full | NV | NVC |
|---|---|---|---|
| page_17 | 5 | 3 | 24 |
| page_18 | 10 | 11 | 27 |
| page_21 | 0 | 26 | 23 |
| page_22 | 15 | 16 | 30 |
| page_23 | 25 | 28 | 31 |
| page_24 | 17 | 16 | 31 |

Events that change P5 outcome NV → NVC (78):

| page | task | enc | NV state | NVC state | NV locator | NVC locator |
|---|---|---|---|---|---|---|
| page_17 | t_01 | F0 | grabbed | success | `button.Toolbar_newUserBtn__e4f5g6` | `button[data-testid="new-user-btn"]` |
| page_17 | t_02 | F0 | grabbed | success | `select.Toolbar_roleFilter__b1c2d3` | `#role-filter-select` |
| page_17 | t_08 | F0 | grabbed | success | `[data-shadow="true"] .EditPanel_select__p7q8r9#edit-role` | `#edit-role` |
| page_17 | t_01 | F1 | grabbed | success | `button.Toolbar_newUserBtn__e4f5g6` | `button[data-testid="new-user-btn"]` |
| page_17 | t_02 | F1 | grabbed | success | `select.Toolbar_roleFilter__b1c2d3` | `#role-filter-select` |
| page_17 | t_04 | F1 | grabbed | success | `input.ConsolePanel_toggleInput__w6x7y8[aria-label="Toggle active status for alice.johnson"]` | `input[type="checkbox"][aria-label="Toggle active status for alice.johnson"]` |
| page_17 | t_07 | F1 | grabbed | success | `input#edit-username.EditPanel_input__m4n5o6` | `input#edit-username` |
| page_17 | t_08 | F1 | grabbed | success | `select#edit-role.EditPanel_select__p7q8r9[aria-label="Assign role to user"]` | `select#edit-role[aria-label="Assign role to user"]` |
| page_17 | t_10 | F1 | grabbed | success | `button.EditPanel_saveBtn__x6y7z8[data-testid="save-changes-btn"]` | `button[data-testid="save-changes-btn"]` |
| page_17 | t_01 | F2 | grabbed | success | `button.Toolbar_newUserBtn__e4f5g6` | `button[aria-label="Create new user"]` |
| page_17 | t_02 | F2 | grabbed | success | `select.Toolbar_roleFilter__b1c2d3` | `select#role-filter-select` |
| page_17 | t_04 | F2 | grabbed | success | `input.ConsolePanel_toggleInput__w6x7y8[aria-label="Toggle active status for alice.johnson"]` | `input[type="checkbox"][aria-label="Toggle active status for alice.johnson"]` |
| page_17 | t_09 | F2 | grabbed | success | `.EditPanel_input__m4n5o6[type="email"]` | `input[type="email"][placeholder="user@domain.com"]` |
| page_17 | t_10 | F2 | grabbed | success | `button.EditPanel_saveBtn__x6y7z8` | `button[data-testid="save-changes-btn"]` |
| page_17 | t_01 | F3 | grabbed | success | `button.Toolbar_newUserBtn__e4f5g6[data-testid="new-user-btn"]` | `button[data-testid="new-user-btn"]` |
| page_17 | t_02 | F3 | grabbed | success | `select.Toolbar_roleFilter__b1c2d3` | `#role-filter-select` |
| page_17 | t_04 | F3 | grabbed | success | `input.ConsolePanel_toggleInput__w6x7y8[aria-label="Toggle active status for alice.johnson"]` | `input[type="checkbox"][aria-label="Toggle active status for alice.johnson"]` |
| page_17 | t_05 | F3 | grabbed | success | `tr:has(.UserCell_username__e5f6g7:contains("alice.johnson")) .ActionMenu_editBtn__l8m9n0` | `button[aria-label="Edit user alice.johnson"]` |
| page_17 | t_08 | F3 | grabbed | success | `select.EditPanel_select__p7q8r9#edit-role[aria-label="Assign role to user"]` | `#edit-role` |
| page_17 | t_09 | F3 | grabbed | success | `.EditPanel_input__m4n5o6[type="email"]` | `.EditPanel_root__a2b3c4 input[type="email"]` |
| page_17 | t_10 | F3 | grabbed | success | `button.EditPanel_saveBtn__x6y7z8[data-testid="save-changes-btn"]` | `[data-testid="save-changes-btn"]` |
| page_18 | t_01 | F0 | grabbed | success | `button.BoardToolbar_newBtn__o4p5q6[aria-label="Create new task card"]` | `button[data-testid="new-card-btn"][aria-label="Create new task card"]` |
| page_18 | t_02 | F0 | grabbed | success | `input.BoardToolbar_filterInput__l1m2n3` | `#board-filter` |
| page_18 | t_04 | F0 | grabbed | success | `button.KanbanPanel_addBtn__w9x0y1[aria-label="Quick-add card to In Progress"]` | `button[aria-label="Quick-add card to In Progress"]` |
| page_18 | t_08 | F0 | success | grabbed | `select#card-assignee.EditPanel_sel__b9c0d1` | `[data-shadow="true"] select#card-assignee.EditPanel_sel__b9c0d1[aria-label="Assign to team member"][name="assignee"]` |
| page_18 | t_09 | F0 | success | grabbed | `input[type="date"].EditPanel_inp__y6z7a8` | `[data-shadow="true"] input[type="date"]` |
| page_18 | t_01 | F1 | grabbed | success | `button.BoardToolbar_newBtn__o4p5q6` | `button[data-testid="new-card-btn"]` |
| page_18 | t_02 | F1 | grabbed | success | `input.BoardToolbar_filterInput__l1m2n3` | `#board-filter` |
| page_18 | t_04 | F1 | grabbed | success | `button.KanbanPanel_addBtn__w9x0y1[aria-label="Quick-add card to In Progress"]` | `button[aria-label="Quick-add card to In Progress"]` |
| page_18 | t_05 | F1 | grabbed | success | `select.KanbanPanel_sortSel__d7e8f9[aria-label="Sort cards by"]` | `select[aria-label="Sort cards by"]` |
| page_18 | t_10 | F1 | grabbed | success | `button.EditPanel_saveBtn__k8l9m0[aria-label="Save card changes"]` | `button[data-testid="save-card-btn"]` |
| page_18 | t_01 | F2 | grabbed | success | `button.BoardToolbar_newBtn__o4p5q6` | `button[data-testid="new-card-btn"]` |
| page_18 | t_02 | F2 | grabbed | success | `input.BoardToolbar_filterInput__l1m2n3` | `input#board-filter` |
| page_18 | t_04 | F2 | grabbed | success | `button.KanbanPanel_addBtn__w9x0y1` | `button[aria-label="Quick-add card to In Progress"]` |
| page_18 | t_05 | F2 | grabbed | success | `select.KanbanPanel_sortSel__d7e8f9` | `select[name="sort_by"]` |
| page_18 | t_10 | F2 | grabbed | success | `button.EditPanel_saveBtn__k8l9m0[al="Save card changes"]` | `button[data-testid="save-card-btn"]` |
| page_18 | t_01 | F3 | grabbed | success | `button.BoardToolbar_newBtn__o4p5q6[data-testid="new-card-btn"]` | `button[data-testid="new-card-btn"]` |
| page_18 | t_02 | F3 | grabbed | success | `input.BoardToolbar_filterInput__l1m2n3#board-filter` | `#board-filter` |
| page_18 | t_04 | F3 | grabbed | success | `button.KanbanPanel_addBtn__w9x0y1[aria-label="Quick-add card to In Progress"]` | `button[aria-label="Quick-add card to In Progress"]` |
| page_18 | t_05 | F3 | grabbed | success | `select.KanbanPanel_sortSel__d7e8f9` | `select[aria-label="Sort cards by"]` |
| page_18 | t_10 | F3 | grabbed | success | `button.EditPanel_saveBtn__k8l9m0[data-testid="save-card-btn"]` | `button[data-testid="save-card-btn"]` |
| page_21 | t_08 | F0 | success | grabbed | `button[aria-label="Mute audio"]` | `button[data-shadow="true"][aria-label="Mute audio"]` |
| page_21 | t_02 | F2 | success | grabbed | `button[data-testid="like-btn"]` | `button[data-dt="like-btn"]` |
| page_21 | t_10 | F2 | success | grabbed | `button[data-testid="caption-toggle"]` | `button[aria-label="Toggle captions"][data-caption-toggle]` |
| page_22 | t_02 | F0 | grabbed | success | `button.TfAction_refreshBtn__a1b2c3[aria-label="Refresh tracking data"]` | `button[aria-label="Refresh tracking data"]` |
| page_22 | t_04 | F0 | grabbed | success | `select.TfTable_root__j0k1l2 ~ select[aria-label="Filter by carrier"], select.TrackPanel_carrierSel__c6d7e8[aria-label="Filter by carrier"]` | `select[aria-label="Filter by carrier"]` |
| page_22 | t_05 | F0 | grabbed | success | `button.TrackPanel_exportBtn__f9g0h1[aria-label="Export shipment report as CSV"]` | `button[aria-label="Export shipment report as CSV"]` |
| page_22 | t_07 | F0 | success | grabbed | `.EditForm_inp__b9c0d1#shipment-ref` | `[data-shadow="true"] .EditForm_inp__b9c0d1#shipment-ref` |
| page_22 | t_10 | F0 | grabbed | success | `button.EditForm_saveBtn__q4r5s6[data-testid="save-shipment-btn"]` | `button[data-testid="save-shipment-btn"]` |
| page_22 | t_02 | F1 | grabbed | success | `button.TfAction_refreshBtn__a1b2c3[aria-label="Refresh tracking data"]` | `button[aria-label="Refresh tracking data"]` |
| page_22 | t_04 | F1 | grabbed | success | `select.TfPanel_carrierSel__c6d7e8,select.TrackPanel_carrierSel__c6d7e8` | `select[aria-label="Filter by carrier"]` |
| page_22 | t_05 | F1 | grabbed | success | `.TrackPanel_exportBtn__f9g0h1` | `button[aria-label="Export shipment report as CSV"]` |
| page_22 | t_10 | F1 | grabbed | success | `button.EditForm_saveBtn__q4r5s6` | `button[data-testid="save-shipment-btn"]` |
| page_22 | t_02 | F2 | grabbed | success | `button.TfAction_refreshBtn__a1b2c3[aria-label="Refresh tracking data"]` | `button[aria-label="Refresh tracking data"]` |
| page_22 | t_04 | F2 | grabbed | success | `select.TrackPanel_carrierSel__c6d7e8` | `select[aria-label="Filter by carrier"]` |
| page_22 | t_05 | F2 | grabbed | success | `button.TrackPanel_exportBtn__f9g0h1` | `button[aria-label="Export shipment report as CSV"]` |
| page_22 | t_02 | F3 | grabbed | success | `button.TfAction_refreshBtn__a1b2c3[aria-label="Refresh tracking data"]` | `button[aria-label="Refresh tracking data"]` |
| page_22 | t_04 | F3 | grabbed | success | `select.TfSearch_inp__i8j9k0[aria-label="Filter by carrier"], select.TrackPanel_carrierSel__c6d7e8[aria-label="Filter by carrier"]` | `select[aria-label="Filter by carrier"]` |
| page_22 | t_05 | F3 | grabbed | success | `button.TrackPanel_exportBtn__f9g0h1[aria-label="Export shipment report as CSV"]` | `button[aria-label="Export shipment report as CSV"]` |
| page_22 | t_10 | F3 | grabbed | success | `button.EditForm_saveBtn__q4r5s6[data-testid="save-shipment-btn"]` | `button[data-testid="save-shipment-btn"]` |
| page_23 | t_10 | F0 | grabbed | success | `button.PayWidget_submitBtn__k2l3m4[aria-label="Pay and place order"]` | `button[data-testid="submit-payment-btn"]` |
| page_23 | t_10 | F1 | grabbed | success | `button.PayWidget_submitBtn__k2l3m4[aria-label="Pay and place order"]` | `button[data-testid="submit-payment-btn"]` |
| page_23 | t_10 | F3 | grabbed | success | `button.PayWidget_submitBtn__k2l3m4[aria-label="Pay and place order"]` | `button[type="submit"][aria-label="Pay and place order"][data-testid="submit-payment-btn"]` |
| page_24 | t_02 | F0 | grabbed | success | `button.AccountSection_btnOutline__k7l8m9[aria-label="Change account password"]` | `button[aria-label="Change account password"]` |
| page_24 | t_04 | F0 | grabbed | success | `input.SettingsPanel_check__f8g9h0[aria-label="Toggle data sharing"]` | `input[type="checkbox"][aria-label="Toggle data sharing"]` |
| page_24 | t_05 | F0 | grabbed | success | `input.SettingsPanel_check__f8g9h0[aria-label="Toggle marketing emails"]` | `input[type="checkbox"][aria-label="Toggle marketing emails"]` |
| page_24 | t_10 | F0 | grabbed | success | `button.PrefPanel_saveBtn__y2z3a4[aria-label="Save all preferences"]` | `button[data-testid="save-prefs-btn"]` |
| page_24 | t_04 | F1 | grabbed | success | `input.SettingsPanel_check__f8g9h0[aria-label="Toggle data sharing"]` | `input[aria-label="Toggle data sharing"]` |
| page_24 | t_05 | F1 | grabbed | success | `input.SettingsPanel_check__f8g9h0[aria-label="Toggle marketing emails"]` | `input[aria-label="Toggle marketing emails"]` |
| page_24 | t_10 | F1 | grabbed | success | `button.PrefPanel_saveBtn__y2z3a4[aria-label="Save all preferences"]` | `button[data-testid="save-prefs-btn"]` |
| page_24 | t_02 | F2 | grabbed | success | `button.AccountSection_btnOutline__k7l8m9[aria-label="Change account password"]` | `button[aria-label="Change account password"]` |
| page_24 | t_04 | F2 | grabbed | success | `input[type="checkbox"].SettingsPanel_check__f8g9h0[alt="Toggle data sharing"]` | `input[aria-label="Toggle data sharing"]` |
| page_24 | t_05 | F2 | grabbed | success | `input[type="checkbox"].SettingsPanel_check__f8g9h0[aria-label="Toggle marketing emails"]` | `input[aria-label="Toggle marketing emails"]` |
| page_24 | t_10 | F2 | grabbed | success | `button.PrefPanel_saveBtn__y2z3a4` | `button[aria-label="Save all preferences"]` |
| page_24 | t_02 | F3 | grabbed | success | `button.AccountSection_btnOutline__k7l8m9[aria-label="Change account password"]` | `button[aria-label="Change account password"]` |
| page_24 | t_04 | F3 | grabbed | success | `input.SettingsPanel_check__f8g9h0[aria-label="Toggle data sharing"]` | `input[type="checkbox"][aria-label="Toggle data sharing"]` |
| page_24 | t_05 | F3 | grabbed | success | `input.SettingsPanel_check__f8g9h0[aria-label="Toggle marketing emails"]` | `input[type="checkbox"][aria-label="Toggle marketing emails"]` |
| page_24 | t_10 | F3 | grabbed | success | `button.PrefPanel_saveBtn__y2z3a4[data-testid="save-prefs-btn"]` | `button[aria-label="Save all preferences"][data-testid="save-prefs-btn"]` |

## 6. page_17 / page_18 — NVC vs B_playwrightMCP×F4

FINDINGS.md line 55 states p17: F4 40% vs NV 20%; p18: F4 50% vs NV 30% (these NV figures equal the best NV encoding per page: p17 F2, p18 F1/F2/F3).

| page | bundle | F0 | F1 | F2 | F3 | total | best encoding | F4 | encodings > F4 | encodings = F4 |
|---|---|---|---|---|---|---|---|---|---|---|
| page_17 | B_noVolatile | 0 | 0 | 2 | 1 | 3/40 (7.5%) | 20% | 4/10 (40%) | none | none |
| page_17 | B_noVolatileConsistent | 3 | 6 | 7 | 8 | 24/40 (60.0%) | 80% | 4/10 (40%) | F1, F2, F3 | none |
| page_18 | B_noVolatile | 2 | 3 | 3 | 3 | 11/40 (27.5%) | 30% | 5/10 (50%) | none | none |
| page_18 | B_noVolatileConsistent | 3 | 8 | 8 | 8 | 27/40 (67.5%) | 80% | 5/10 (50%) | F1, F2, F3 | none |

page_17 per target (1 = success):

| task | F4 | NV F0 | NV F1 | NV F2 | NV F3 | NVC F0 | NVC F1 | NVC F2 | NVC F3 |
|---|---|---|---|---|---|---|---|---|---|
| t_01 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
| t_02 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
| t_03 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| t_04 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 |
| t_05 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| t_06 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| t_07 | 0 | 0 | 0 | 1 | 1 | 0 | 1 | 1 | 1 |
| t_08 | 1 | 0 | 0 | 1 | 0 | 1 | 1 | 1 | 1 |
| t_09 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |
| t_10 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 |

page_18 per target (1 = success):

| task | F4 | NV F0 | NV F1 | NV F2 | NV F3 | NVC F0 | NVC F1 | NVC F2 | NVC F3 |
|---|---|---|---|---|---|---|---|---|---|
| t_01 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
| t_02 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
| t_03 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| t_04 | 1 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 1 |
| t_05 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 |
| t_06 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| t_07 | 0 | 0 | 1 | 1 | 1 | 0 | 1 | 1 | 1 |
| t_08 | 0 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 |
| t_09 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 |
| t_10 | 1 | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 |

## 7. CSS-module-shaped class tokens not matched by `VolatileClassRe`

`VolatileClassRe` flags `Name_xxxxx__hash` only when the middle segment has ≥ 5 characters (`[A-Za-z]+_[A-Za-z0-9]{5,}__`). Class tokens of the form `Name_x__hash` with a 1–4 character middle segment are not flagged by the predicate, so both NV and NVC keep them: 112 distinct (page, token) in the DOM census, pages page_17 24, page_18 20, page_21 18, page_22 19, page_23 18, page_24 13. Examples: `ActionMenu_root__i5j6k7`, `AdminLayout_main__j0k1l2`, `AdminLayout_nav__g7h8i9`, `ConsolePanel_root__c8d9e0`, `DeptBadge_root__k1l2m3`, `EditPanel_grid__e8f9g0`.

| event set | locators containing such a token | of which P5 success |
|---|---|---|
| NVC (960) | 53 | 20 |
| B_noVolatile (960) | 48 | 26 |
| B_full F0–F3 (960) | 43 | 24 |

Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: 120 SHA-256 equal.
