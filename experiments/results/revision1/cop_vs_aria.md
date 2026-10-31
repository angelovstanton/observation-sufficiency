# COP (B_noVolatile × F3) vs B_playwrightMCP × F4 — gpt-4.1, paired

**Not in the registered batch plan; existing records only, computed after the registered batch analysis and the real-site pilot results (f6a00d3).**

One attempt per task: each arm is one cell of one repetition, paired on the same 240 targets. COP rep 1 = original corpus run; COP reps 2-3 = revision-1 batch (block 3); B_playwrightMCP × F4 exists for rep 1 only and is the F4 arm of every row. Δ = COP − F4 (pp); b = COP-only, c = F4-only; OR = b/c with the exact conditional 95% CI; p exact = McNemar exact binomial; 95% CI = page-clustered percentile bootstrap (10,000 draws, seed 42; with 2 pages in the crossover row it is descriptive only). Strata from `shared/testbed/pages/*.truth.json` (`no_attribute_signal`: P5 is 0 by construction, shown for P_now only). Shadow level = truth.json `shadow` of the page. No multiplicity correction.

## COP rep 1 vs B_playwrightMCP × F4 rep 1

| COP rep | pages | stratum | pred | n | F4 % | COP % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p exact | p χ² |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | all pages | overall | P5 | 240 | 47.1 | 67.9 | +20.83 | [+11.67, +29.58] | 68/18 | 3.78 [2.22, 6.75] | 5.29e-08 | 6.98e-08 |
| 1 | all pages | overall | P_now | 240 | 52.5 | 85.8 | +33.33 | [+26.67, +40.83] | 84/4 | 21.00 [7.90, 78.86] | 1.58e-20 | 1.49e-17 |
| 1 | all pages | has_attribute_signal | P5 | 192 | 58.9 | 84.9 | +26.04 | [+14.81, +37.11] | 68/18 | 3.78 [2.22, 6.75] | 5.29e-08 | 6.98e-08 |
| 1 | all pages | has_attribute_signal | P_now | 192 | 60.9 | 95.8 | +34.90 | [+28.42, +42.11] | 70/3 | 23.33 [7.66, 115.87] | 1.37e-17 | 4.44e-15 |
| 1 | all pages | no_attribute_signal | P_now | 48 | 18.8 | 45.8 | +27.08 | [+13.04, +41.30] | 14/1 | 14.00 [2.13, 591.97] | 9.77e-04 | 7.89e-04 |
| 1 | S0 pages (8) | overall | P5 | 80 | 42.5 | 76.2 | +33.75 | [+23.75, +46.25] | 28/1 | 28.00 [4.63, 1144.94] | 1.12e-07 | 5.34e-07 |
| 1 | S0 pages (8) | overall | P_now | 80 | 50.0 | 90.0 | +40.00 | [+26.25, +57.50] | 33/1 | 33.00 [5.52, 1342.43] | 4.07e-09 | 4.07e-08 |
| 1 | S0 pages (8) | has_attribute_signal | P5 | 62 | 54.8 | 98.4 | +43.55 | [+29.03, +60.00] | 28/1 | 28.00 [4.63, 1144.94] | 1.12e-07 | 5.34e-07 |
| 1 | S0 pages (8) | has_attribute_signal | P_now | 62 | 58.1 | 98.4 | +40.32 | [+26.56, +56.92] | 26/1 | 26.00 [4.27, 1065.94] | 4.17e-07 | 1.50e-06 |
| 1 | S0 pages (8) | no_attribute_signal | P_now | 18 | 22.2 | 61.1 | +38.89 | [+17.65, +61.11] | 7/0 | inf [1.44, inf] | 0.0156 | 0.0082 |
| 1 | S1 pages (8) | overall | P5 | 80 | 53.8 | 77.5 | +23.75 | [+12.50, +35.00] | 22/3 | 7.33 [2.20, 38.27] | 1.57e-04 | 1.45e-04 |
| 1 | S1 pages (8) | overall | P_now | 80 | 57.5 | 87.5 | +30.00 | [+17.50, +41.25] | 26/2 | 13.00 [3.25, 113.02] | 3.03e-06 | 5.74e-06 |
| 1 | S1 pages (8) | has_attribute_signal | P5 | 67 | 64.2 | 92.5 | +28.36 | [+15.38, +40.91] | 22/3 | 7.33 [2.20, 38.27] | 1.57e-04 | 1.45e-04 |
| 1 | S1 pages (8) | has_attribute_signal | P_now | 67 | 65.7 | 94.0 | +28.36 | [+16.67, +39.71] | 21/2 | 10.50 [2.57, 92.37] | 6.60e-05 | 7.44e-05 |
| 1 | S1 pages (8) | no_attribute_signal | P_now | 13 | 15.4 | 53.8 | +38.46 | [+18.18, +57.14] | 5/0 | inf [0.92, inf] | 0.0625 | 0.0253 |
| 1 | S2 pages (8) | overall | P5 | 80 | 45.0 | 50.0 | +5.00 | [-11.25, +20.00] | 18/14 | 1.29 [0.60, 2.79] | 0.5966 | 0.4795 |
| 1 | S2 pages (8) | overall | P_now | 80 | 50.0 | 80.0 | +30.00 | [+25.00, +35.00] | 25/1 | 25.00 [4.09, 1026.45] | 8.05e-07 | 2.52e-06 |
| 1 | S2 pages (8) | has_attribute_signal | P5 | 63 | 57.1 | 63.5 | +6.35 | [-14.06, +25.81] | 18/14 | 1.29 [0.60, 2.79] | 0.5966 | 0.4795 |
| 1 | S2 pages (8) | has_attribute_signal | P_now | 63 | 58.7 | 95.2 | +36.51 | [+32.81, +40.00] | 23/0 | inf [5.75, inf] | 2.38e-07 | 1.62e-06 |
| 1 | S2 pages (8) | no_attribute_signal | P_now | 17 | 17.6 | 23.5 | +5.88 | [-13.33, +26.67] | 2/1 | 2.00 [0.10, 117.99] | 1.0000 | 0.5637 |
| 1 | page_17 + page_18 (crossover) | overall | P5 | 20 | 45.0 | 20.0 | -25.00 | [-30.00, -20.00] | 3/8 | 0.38 [0.06, 1.56] | 0.2266 | 0.1317 |
| 1 | page_17 + page_18 (crossover) | overall | P_now | 20 | 50.0 | 80.0 | +30.00 | [+20.00, +40.00] | 7/1 | 7.00 [0.90, 315.48] | 0.0703 | 0.0339 |
| 1 | page_17 + page_18 (crossover) | has_attribute_signal | P5 | 16 | 56.2 | 25.0 | -31.25 | [-37.50, -25.00] | 3/8 | 0.38 [0.06, 1.56] | 0.2266 | 0.1317 |
| 1 | page_17 + page_18 (crossover) | has_attribute_signal | P_now | 16 | 56.2 | 93.8 | +37.50 | [+37.50, +37.50] | 6/0 | inf [1.18, inf] | 0.0312 | 0.0143 |
| 1 | page_17 + page_18 (crossover) | no_attribute_signal | P_now | 4 | 25.0 | 25.0 | +0.00 | [-50.00, +50.00] | 1/1 | 1.00 [0.01, 78.50] | 1.0000 | 1.0000 |

## COP rep 2 vs B_playwrightMCP × F4 rep 1

| COP rep | pages | stratum | pred | n | F4 % | COP % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p exact | p χ² |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 | all pages | overall | P5 | 240 | 47.1 | 68.3 | +21.25 | [+12.08, +30.00] | 68/17 | 4.00 [2.32, 7.26] | 2.18e-08 | 3.17e-08 |
| 2 | all pages | overall | P_now | 240 | 52.5 | 84.6 | +32.08 | [+26.25, +38.75] | 81/4 | 20.25 [7.61, 76.11] | 1.10e-19 | 6.72e-17 |
| 2 | all pages | has_attribute_signal | P5 | 192 | 58.9 | 85.4 | +26.56 | [+15.03, +37.50] | 68/17 | 4.00 [2.32, 7.26] | 2.18e-08 | 3.17e-08 |
| 2 | all pages | has_attribute_signal | P_now | 192 | 60.9 | 95.8 | +34.90 | [+28.87, +41.97] | 70/3 | 23.33 [7.66, 115.87] | 1.37e-17 | 4.44e-15 |
| 2 | all pages | no_attribute_signal | P_now | 48 | 18.8 | 39.6 | +20.83 | [+9.09, +33.33] | 11/1 | 11.00 [1.60, 473.47] | 0.0063 | 0.0039 |
| 2 | S0 pages (8) | overall | P5 | 80 | 42.5 | 76.2 | +33.75 | [+23.75, +46.25] | 28/1 | 28.00 [4.63, 1144.94] | 1.12e-07 | 5.34e-07 |
| 2 | S0 pages (8) | overall | P_now | 80 | 50.0 | 87.5 | +37.50 | [+26.25, +51.25] | 31/1 | 31.00 [5.17, 1263.43] | 1.54e-08 | 1.14e-07 |
| 2 | S0 pages (8) | has_attribute_signal | P5 | 62 | 54.8 | 98.4 | +43.55 | [+29.03, +60.00] | 28/1 | 28.00 [4.63, 1144.94] | 1.12e-07 | 5.34e-07 |
| 2 | S0 pages (8) | has_attribute_signal | P_now | 62 | 58.1 | 98.4 | +40.32 | [+26.56, +56.92] | 26/1 | 26.00 [4.27, 1065.94] | 4.17e-07 | 1.50e-06 |
| 2 | S0 pages (8) | no_attribute_signal | P_now | 18 | 22.2 | 50.0 | +27.78 | [+11.76, +46.67] | 5/0 | inf [0.92, inf] | 0.0625 | 0.0253 |
| 2 | S1 pages (8) | overall | P5 | 80 | 53.8 | 78.8 | +25.00 | [+15.00, +35.00] | 22/2 | 11.00 [2.70, 96.50] | 3.59e-05 | 4.46e-05 |
| 2 | S1 pages (8) | overall | P_now | 80 | 57.5 | 87.5 | +30.00 | [+18.75, +41.25] | 25/1 | 25.00 [4.09, 1026.45] | 8.05e-07 | 2.52e-06 |
| 2 | S1 pages (8) | has_attribute_signal | P5 | 67 | 64.2 | 94.0 | +29.85 | [+18.46, +41.18] | 22/2 | 11.00 [2.70, 96.50] | 3.59e-05 | 4.46e-05 |
| 2 | S1 pages (8) | has_attribute_signal | P_now | 67 | 65.7 | 95.5 | +29.85 | [+20.00, +39.71] | 21/1 | 21.00 [3.38, 868.45] | 1.10e-05 | 2.01e-05 |
| 2 | S1 pages (8) | no_attribute_signal | P_now | 13 | 15.4 | 46.2 | +30.77 | [+8.33, +50.00] | 4/0 | inf [0.66, inf] | 0.1250 | 0.0455 |
| 2 | S2 pages (8) | overall | P5 | 80 | 45.0 | 50.0 | +5.00 | [-11.25, +20.00] | 18/14 | 1.29 [0.60, 2.79] | 0.5966 | 0.4795 |
| 2 | S2 pages (8) | overall | P_now | 80 | 50.0 | 78.8 | +28.75 | [+22.50, +35.00] | 25/2 | 12.50 [3.12, 108.89] | 5.65e-06 | 9.58e-06 |
| 2 | S2 pages (8) | has_attribute_signal | P5 | 63 | 57.1 | 63.5 | +6.35 | [-14.29, +26.24] | 18/14 | 1.29 [0.60, 2.79] | 0.5966 | 0.4795 |
| 2 | S2 pages (8) | has_attribute_signal | P_now | 63 | 58.7 | 93.7 | +34.92 | [+30.30, +39.34] | 23/1 | 23.00 [3.73, 947.45] | 2.98e-06 | 7.10e-06 |
| 2 | S2 pages (8) | no_attribute_signal | P_now | 17 | 17.6 | 23.5 | +5.88 | [-13.33, +26.67] | 2/1 | 2.00 [0.10, 117.99] | 1.0000 | 0.5637 |
| 2 | page_17 + page_18 (crossover) | overall | P5 | 20 | 45.0 | 15.0 | -30.00 | [-30.00, -30.00] | 3/9 | 0.33 [0.06, 1.34] | 0.1460 | 0.0833 |
| 2 | page_17 + page_18 (crossover) | overall | P_now | 20 | 50.0 | 75.0 | +25.00 | [+10.00, +40.00] | 7/2 | 3.50 [0.67, 34.53] | 0.1797 | 0.0956 |
| 2 | page_17 + page_18 (crossover) | has_attribute_signal | P5 | 16 | 56.2 | 18.8 | -37.50 | [-37.50, -37.50] | 3/9 | 0.33 [0.06, 1.34] | 0.1460 | 0.0833 |
| 2 | page_17 + page_18 (crossover) | has_attribute_signal | P_now | 16 | 56.2 | 87.5 | +31.25 | [+25.00, +37.50] | 6/1 | 6.00 [0.73, 275.99] | 0.1250 | 0.0588 |
| 2 | page_17 + page_18 (crossover) | no_attribute_signal | P_now | 4 | 25.0 | 25.0 | +0.00 | [-50.00, +50.00] | 1/1 | 1.00 [0.01, 78.50] | 1.0000 | 1.0000 |

## COP rep 3 vs B_playwrightMCP × F4 rep 1

| COP rep | pages | stratum | pred | n | F4 % | COP % | Δ pp | 95% CI (pp) | b/c | OR [95% CI] | p exact | p χ² |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | all pages | overall | P5 | 240 | 47.1 | 68.3 | +21.25 | [+12.08, +30.00] | 68/17 | 4.00 [2.32, 7.26] | 2.18e-08 | 3.17e-08 |
| 3 | all pages | overall | P_now | 240 | 52.5 | 84.6 | +32.08 | [+26.25, +38.75] | 81/4 | 20.25 [7.61, 76.11] | 1.10e-19 | 6.72e-17 |
| 3 | all pages | has_attribute_signal | P5 | 192 | 58.9 | 85.4 | +26.56 | [+15.03, +37.50] | 68/17 | 4.00 [2.32, 7.26] | 2.18e-08 | 3.17e-08 |
| 3 | all pages | has_attribute_signal | P_now | 192 | 60.9 | 95.8 | +34.90 | [+28.87, +41.97] | 70/3 | 23.33 [7.66, 115.87] | 1.37e-17 | 4.44e-15 |
| 3 | all pages | no_attribute_signal | P_now | 48 | 18.8 | 39.6 | +20.83 | [+9.09, +33.33] | 11/1 | 11.00 [1.60, 473.47] | 0.0063 | 0.0039 |
| 3 | S0 pages (8) | overall | P5 | 80 | 42.5 | 76.2 | +33.75 | [+23.75, +46.25] | 28/1 | 28.00 [4.63, 1144.94] | 1.12e-07 | 5.34e-07 |
| 3 | S0 pages (8) | overall | P_now | 80 | 50.0 | 87.5 | +37.50 | [+26.25, +51.25] | 31/1 | 31.00 [5.17, 1263.43] | 1.54e-08 | 1.14e-07 |
| 3 | S0 pages (8) | has_attribute_signal | P5 | 62 | 54.8 | 98.4 | +43.55 | [+29.03, +60.00] | 28/1 | 28.00 [4.63, 1144.94] | 1.12e-07 | 5.34e-07 |
| 3 | S0 pages (8) | has_attribute_signal | P_now | 62 | 58.1 | 98.4 | +40.32 | [+26.56, +56.92] | 26/1 | 26.00 [4.27, 1065.94] | 4.17e-07 | 1.50e-06 |
| 3 | S0 pages (8) | no_attribute_signal | P_now | 18 | 22.2 | 50.0 | +27.78 | [+11.76, +46.67] | 5/0 | inf [0.92, inf] | 0.0625 | 0.0253 |
| 3 | S1 pages (8) | overall | P5 | 80 | 53.8 | 78.8 | +25.00 | [+15.00, +35.00] | 22/2 | 11.00 [2.70, 96.50] | 3.59e-05 | 4.46e-05 |
| 3 | S1 pages (8) | overall | P_now | 80 | 57.5 | 87.5 | +30.00 | [+18.75, +41.25] | 25/1 | 25.00 [4.09, 1026.45] | 8.05e-07 | 2.52e-06 |
| 3 | S1 pages (8) | has_attribute_signal | P5 | 67 | 64.2 | 94.0 | +29.85 | [+18.46, +41.18] | 22/2 | 11.00 [2.70, 96.50] | 3.59e-05 | 4.46e-05 |
| 3 | S1 pages (8) | has_attribute_signal | P_now | 67 | 65.7 | 95.5 | +29.85 | [+20.00, +39.71] | 21/1 | 21.00 [3.38, 868.45] | 1.10e-05 | 2.01e-05 |
| 3 | S1 pages (8) | no_attribute_signal | P_now | 13 | 15.4 | 46.2 | +30.77 | [+8.33, +50.00] | 4/0 | inf [0.66, inf] | 0.1250 | 0.0455 |
| 3 | S2 pages (8) | overall | P5 | 80 | 45.0 | 50.0 | +5.00 | [-11.25, +20.00] | 18/14 | 1.29 [0.60, 2.79] | 0.5966 | 0.4795 |
| 3 | S2 pages (8) | overall | P_now | 80 | 50.0 | 78.8 | +28.75 | [+22.50, +35.00] | 25/2 | 12.50 [3.12, 108.89] | 5.65e-06 | 9.58e-06 |
| 3 | S2 pages (8) | has_attribute_signal | P5 | 63 | 57.1 | 63.5 | +6.35 | [-14.29, +26.24] | 18/14 | 1.29 [0.60, 2.79] | 0.5966 | 0.4795 |
| 3 | S2 pages (8) | has_attribute_signal | P_now | 63 | 58.7 | 93.7 | +34.92 | [+30.30, +39.34] | 23/1 | 23.00 [3.73, 947.45] | 2.98e-06 | 7.10e-06 |
| 3 | S2 pages (8) | no_attribute_signal | P_now | 17 | 17.6 | 23.5 | +5.88 | [-13.33, +26.67] | 2/1 | 2.00 [0.10, 117.99] | 1.0000 | 0.5637 |
| 3 | page_17 + page_18 (crossover) | overall | P5 | 20 | 45.0 | 15.0 | -30.00 | [-30.00, -30.00] | 3/9 | 0.33 [0.06, 1.34] | 0.1460 | 0.0833 |
| 3 | page_17 + page_18 (crossover) | overall | P_now | 20 | 50.0 | 75.0 | +25.00 | [+10.00, +40.00] | 7/2 | 3.50 [0.67, 34.53] | 0.1797 | 0.0956 |
| 3 | page_17 + page_18 (crossover) | has_attribute_signal | P5 | 16 | 56.2 | 18.8 | -37.50 | [-37.50, -37.50] | 3/9 | 0.33 [0.06, 1.34] | 0.1460 | 0.0833 |
| 3 | page_17 + page_18 (crossover) | has_attribute_signal | P_now | 16 | 56.2 | 87.5 | +31.25 | [+25.00, +37.50] | 6/1 | 6.00 [0.73, 275.99] | 0.1250 | 0.0588 |
| 3 | page_17 + page_18 (crossover) | no_attribute_signal | P_now | 4 | 25.0 | 25.0 | +0.00 | [-50.00, +50.00] | 1/1 | 1.00 [0.01, 78.50] | 1.0000 | 1.0000 |

COP reps 2 and 3 (separate calls, different event keys): P5 and P_now identical on 240/240 and 240/240 events, so their two tables coincide.

Pages per shadow level: S0: page_01, page_02, page_03, page_04, page_05, page_06, page_07, page_08; S1: page_09, page_10, page_11, page_12, page_13, page_14, page_15, page_16; S2: page_17, page_18, page_19, page_20, page_21, page_22, page_23, page_24.

## Observation tokens (o200k_base), COP rep 1 vs B_playwrightMCP × F4 rep 1

| pages | n | F4 mean | COP mean | F4 / COP (means) | F4 median | COP median | F4 / COP (medians) |
|---|---|---|---|---|---|---|---|
| all pages | 240 | 8,914 | 17,887 | 0.50 | 1,616 | 8,100 | 0.20 |
| S0 pages (8) | 80 | 11,531 | 21,657 | 0.53 | 3,930 | 11,378 | 0.35 |
| S1 pages (8) | 80 | 7,937 | 8,410 | 0.94 | 1,348 | 2,935 | 0.46 |
| S2 pages (8) | 80 | 7,275 | 23,595 | 0.31 | 1,504 | 11,419 | 0.13 |
| page_17 + page_18 (crossover) | 20 | 17,884 | 67,268 | 0.27 | 17,884 | 67,268 | 0.27 |

COP observations are identical across reps (same pages, bundle, encoding): rep 2 mean 17,887, rep 3 mean 17,887.
