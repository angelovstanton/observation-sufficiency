# EXPLORATORY — CIs for Tables 2 and 5 (existing records only; not in the registered plan)

Run: `python -B experiments/analysis/revision1_table_cis.py`. Zero LLM calls, zero network; reads existing records only and modifies no existing file.

Data: gpt-4.1, main corpus (`experiments/runs/matrix_page_*.jsonl`, 6,000 records, one generation per event). (a) Table 2: 960 paired events (24 pages × 10 tasks × F0–F3), first = B_full. (b) Table 5: 240 paired events within B_noVolatile (24 pages × 10 tasks), first = F1.

Conventions: Δ = second − first (pp); b = second-only successes, c = first-only. 95% CI = page-clustered percentile bootstrap, 10,000 replicates, seed 42, fresh generator per statistic, same draw sequence as `stats.py`. OR = b/c with exact conditional 95% CI (Clopper–Pearson on b/(b+c)). p χ² = uncorrected McNemar; p exact = binomial. No multiplicity adjustment. P5 = five-condition predicate (`success`); P_now = condition 1 ∧ 2 (unique match ∧ matches oracle). Statistics imported from `revision1_diagnostics.py`; `per_page_success` and `delta_stat` are closures inside its `main()`, so their bodies are restated here and pinned to `stats._cluster_bootstrap_ci` by a control.

## Controls (all passed before any output was written)

| control | recomputed | reference | ok |
|---|---|---|---|
| B_full→B_noVolatile Δ pp (2 dp) | +9.48 | +9.48 | yes |
| B_full→B_noVolatile CI (2 dp) | [+4.90, +15.52] | [+4.90, +15.52] | yes |
| B_full→B_noVolatile b/c | 102/11 | 102/11 | yes |
| local bootstrap == stats._cluster_bootstrap_ci (lo, 1e-9) | 4.895833333 | 4.895833333 | yes |
| local bootstrap == stats._cluster_bootstrap_ci (hi, 1e-9) | 15.520833333 | 15.520833333 | yes |
| F1→F2 (B_noVolatile) Δ pp (2 dp) | -12.08 | -12.08 | yes |
| F1→F2 (B_noVolatile) b/c | 4/33 | 4/33 | yes |
| F1→F2 (B_noVolatile) P5 CI == batch_analysis.md (d) rep 1 | [-18.75, -5.83] | [-18.75, -5.83] | yes |
| F1→F2 (B_noVolatile) P5 Δ, b/c == batch_analysis.md (d) rep 1 | -12.08 4/33 | -12.08 4/33 | yes |
| F1→F2 (B_noVolatile) P_now CI == batch_analysis.md (d) rep 1 | [-21.67, -7.08] | [-21.67, -7.08] | yes |
| F1→F2 (B_noVolatile) P_now Δ, b/c == batch_analysis.md (d) rep 1 | -14.17 5/39 | -14.17 5/39 | yes |
| B_full → B_noVolatile Δ, b/c == holm_bfull_family.md | +9.48 102/11 | +9.48 102/11 | yes |
| B_full → B_noState Δ, b/c == holm_bfull_family.md | +0.31 17/14 | +0.31 17/14 | yes |
| B_full → B_noSemantic Δ, b/c == holm_bfull_family.md | -19.48 17/204 | -19.48 17/204 | yes |
| B_full → B_identityCore Δ, b/c == holm_bfull_family.md | -15.21 77/223 | -15.21 77/223 | yes |
| B_full → B_minimalCore Δ, b/c == holm_bfull_family.md | -54.79 0/526 | -54.79 0/526 | yes |
| B_noVolatile: F1 → F0 Δ, b/c == holm_bfull_family.md | -1.25 3/6 | -1.25 3/6 | yes |
| B_noVolatile: F1 → F2 Δ, b/c == holm_bfull_family.md | -12.08 4/33 | -12.08 4/33 | yes |
| B_noVolatile: F1 → F3 Δ, b/c == holm_bfull_family.md | +0.42 4/3 | +0.42 4/3 | yes |
| B_full→B_noVolatile P_now b/c, Δ, CI == diagnostics.json D1 (full precision) | [25, 83, -6.041666666666667, -9.895833333333325, -2.500000000000002] | [25, 83, -6.041666666666667, -9.895833333333325, -2.500000000000002] | yes |

## Results — P5 (primary)

| comparison (second − first) | n pairs | first % | second % | Δ pp | 95% CI (pp) | b (second-only) | c (first-only) | OR = b/c [exact 95% CI] | p χ² | p exact |
|---|---|---|---|---|---|---|---|---|---|---|
| B_full → B_noVolatile | 960 | 54.8 | 64.3 | +9.48 | [+4.90, +15.52] | 102 | 11 | 9.27 [4.97, 19.16] | 1.12e-17 | 1.25e-19 |
| B_full → B_noState | 960 | 54.8 | 55.1 | +0.31 | [-1.04, +1.77] | 17 | 14 | 1.21 [0.56, 2.66] | 0.5900 | 0.7201 |
| B_full → B_noSemantic | 960 | 54.8 | 35.3 | -19.48 | [-25.62, -13.85] | 17 | 204 | 0.08 [0.05, 0.14] | 2.76e-36 | 6.92e-42 |
| B_full → B_identityCore | 960 | 54.8 | 39.6 | -15.21 | [-24.38, -5.62] | 77 | 223 | 0.35 [0.26, 0.45] | 3.48e-17 | 1.26e-17 |
| B_full → B_minimalCore | 960 | 54.8 | 0.0 | -54.79 | [-63.02, -45.94] | 0 | 526 | 0.00 [0.00, 0.01] | 2.09e-116 | 9.10e-159 |
| B_noVolatile: F1 → F0 | 240 | 67.5 | 66.2 | -1.25 | [-4.58, +1.67] | 3 | 6 | 0.50 [0.08, 2.34] | 0.3173 | 0.5078 |
| B_noVolatile: F1 → F2 | 240 | 67.5 | 55.4 | -12.08 | [-18.75, -5.83] | 4 | 33 | 0.12 [0.03, 0.34] | 1.86e-06 | 1.08e-06 |
| B_noVolatile: F1 → F3 | 240 | 67.5 | 67.9 | +0.42 | [-1.67, +2.92] | 4 | 3 | 1.33 [0.23, 9.10] | 0.7055 | 1.0000 |

## Results — P_now (condition 1 ∧ 2)

| comparison (second − first) | n pairs | first % | second % | Δ pp | 95% CI (pp) | b (second-only) | c (first-only) | OR = b/c [exact 95% CI] | p χ² | p exact |
|---|---|---|---|---|---|---|---|---|---|---|
| B_full → B_noVolatile | 960 | 85.8 | 79.8 | -6.04 | [-9.90, -2.50] | 25 | 83 | 0.30 [0.18, 0.48] | 2.39e-08 | 1.88e-08 |
| B_full → B_noState | 960 | 85.8 | 86.9 | +1.04 | [-0.42, +2.81] | 23 | 13 | 1.77 [0.86, 3.80] | 0.0956 | 0.1325 |
| B_full → B_noSemantic | 960 | 85.8 | 74.3 | -11.56 | [-15.62, -7.92] | 32 | 143 | 0.22 [0.15, 0.33] | 4.83e-17 | 5.94e-18 |
| B_full → B_identityCore | 960 | 85.8 | 48.1 | -37.71 | [-45.73, -29.69] | 26 | 388 | 0.07 [0.04, 0.10] | 8.25e-71 | 6.21e-84 |
| B_full → B_minimalCore | 960 | 85.8 | 16.1 | -69.69 | [-74.79, -64.69] | 5 | 674 | 0.01 [0.00, 0.02] | 2.29e-145 | 9.52e-193 |
| B_noVolatile: F1 → F0 | 240 | 83.8 | 80.0 | -3.75 | [-7.50, +0.00] | 6 | 15 | 0.40 [0.13, 1.09] | 0.0495 | 0.0784 |
| B_noVolatile: F1 → F2 | 240 | 83.8 | 69.6 | -14.17 | [-21.67, -7.08] | 5 | 39 | 0.13 [0.04, 0.33] | 2.96e-07 | 1.41e-07 |
| B_noVolatile: F1 → F3 | 240 | 83.8 | 85.8 | +2.08 | [-0.42, +5.00] | 8 | 3 | 2.67 [0.64, 15.61] | 0.1317 | 0.2266 |

## Input SHA-256

| Input | SHA-256 |
|---|---|
| experiments/analysis/revision1_table_cis.py | dd2dcd8e2effc6b3e191a7e2e1a80c4d82aa2b658118fee236e3d12ce73e61d3 |
| experiments/analysis/revision1_diagnostics.py | 4698eabd141613224a67299bef3bfd84452320b170166f97fa393d6c9661e656 |
| experiments/analysis/load.py | 36f12007478e812378e353e29df88b0bef8bd44b3d3e070ea86990e9bf457af7 |
| experiments/analysis/stats.py | 3010ce153461c31cad6cf8d1c01c5e20d16abe01cf9ffa5c8b8d8cf731df8508 |
| experiments/analysis/bundle_ladder.py | 1c9b4b5b9e7a0dd1ba916e5a346593001c3fc61fa05a94bbed6fc16b7567454c |
| experiments/analysis/cross_model.py | 5e509ae19301f57cd195b012a622322164a99302e7488f0f848e40fad30ec9a0 |
| experiments/results/revision1/holm_bfull_family.md | 3e58a4101e83de241084cd4a10ca18aa0cbe9401bcdd7aeb216acb0bf8ce5ad5 |
| experiments/results/revision1/batch_analysis.md | 3f7c967c349849f2912cc9d8d9c1f2a66a857485131d928c7dc5068c64298f1f |
| experiments/results/revision1/diagnostics.json | 7d1ac8223e83d7846c6cadbb65bb1144d1f03a760239910302fbc85cf780b4ca |
| experiments/runs/matrix_page_01.jsonl | dd844783f07b722b1e97db8fe1a86c6bf161d805b810e483468e609b5bb22f0f |
| experiments/runs/matrix_page_02.jsonl | c5bc90fe1037e749f67623fd44c48d7ddff363438cc460f3c6215f2d2c0df68c |
| experiments/runs/matrix_page_03.jsonl | fdbb2aa8f8b3373951c40b8a602c93497727b394538da7f7572cd13c839a0802 |
| experiments/runs/matrix_page_04.jsonl | f350378f729742fcc4fe65d825d19185b185f6cacab65c7c267850acc06ab4f1 |
| experiments/runs/matrix_page_05.jsonl | 7e41442c079f72499bd04f20cd40bad4fed865cd285e43018ca42b9155f0fe0e |
| experiments/runs/matrix_page_06.jsonl | 1079c5782fca61ffd9a65e00c687e409dfafdac9ab458bd271eae9f4b077eb97 |
| experiments/runs/matrix_page_07.jsonl | 77329acb5ccd309f81d7bf1720a9f3f7c5885e8c5287aefcdfe6c66c47265613 |
| experiments/runs/matrix_page_08.jsonl | da02570ca76fd15c3c261598251554a42c1f46575d48c455780470d5bddb90db |
| experiments/runs/matrix_page_09.jsonl | 2c38d9ac1126cbe0769a59afd85149b8aebb73b0bd468b91aa58d5b5cf71b6bc |
| experiments/runs/matrix_page_10.jsonl | c7b75eb6f353f5da4b3ae00166178cc3bf265dfc5fbd95f8149e19bd37b2d762 |
| experiments/runs/matrix_page_11.jsonl | e9a80227c4c8b1c6902976632ac53e33ba3b684e345d10e2d57276d16660de6b |
| experiments/runs/matrix_page_12.jsonl | 2fab16bc4c57507c5df41e152278fcebc4af9d7214fa3d35ffbad55db2671e44 |
| experiments/runs/matrix_page_13.jsonl | 6e34d9107336c329e8f38d6cbd1af570e71555bfb1b100a67469aff522420af7 |
| experiments/runs/matrix_page_14.jsonl | bf55272988b458d87c237ec0ab81829aa7b074d77b20e6670e9dc7312cf0100e |
| experiments/runs/matrix_page_15.jsonl | f9b675ee7f361800b1d5ec659daca8df9a3eabdba02385898adc870bbcb75213 |
| experiments/runs/matrix_page_16.jsonl | ba14628953f4b05c5c7b685fc7100a6f9a201186e3f3497aab596c969575cffd |
| experiments/runs/matrix_page_17.jsonl | 69b2d93142e1b1923c790c26281be8fd9902155dc2718f90a5e5aab8624f08da |
| experiments/runs/matrix_page_18.jsonl | 2d6ba548dee1611dfa9fa5d580136fe534d7c43711d696f9b386716f4e59992f |
| experiments/runs/matrix_page_19.jsonl | 44644bdd30669eecb854e788d4de1eab0965bb03d8f7e6f0be1a152701a5f786 |
| experiments/runs/matrix_page_20.jsonl | 2fcc7b98833914dc547c8c061f46a28f8427f768287cf7d64bcd74a085a54da2 |
| experiments/runs/matrix_page_21.jsonl | 503f69938ea919c170ca318c4f6a0a75c4b3f785a2be1efcdcf51c6fbb423990 |
| experiments/runs/matrix_page_22.jsonl | 6e290435ef7abcd9d8118d9e7161d4561f1c4de6615d91a3154c722c699da36b |
| experiments/runs/matrix_page_23.jsonl | 6cf434a09195baac2fefd65b9d5cbc926a57b2383d6b30f40165d9173e7fc83c |
| experiments/runs/matrix_page_24.jsonl | 4faad883038e68cf209da3362589de3fd353ae5a8df92ac2d27be76803d0eba4 |
