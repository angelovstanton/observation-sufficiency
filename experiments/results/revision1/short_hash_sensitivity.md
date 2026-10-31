# Revision 1 — short-hash sensitivity (analysis only)

Facts only. The success predicate is not changed; this is a post-hoc re-scoring. `P5_sh` = P5 AND the generated locator contains none of the class tokens of the form `Name_x__hash` with a 1–4 character middle segment (`^[A-Za-z]+_[A-Za-z0-9]{1,4}__[A-Za-z0-9]+$`) that the predicate does not flag: 112 distinct (page, token) pairs on 6 pages (DOM census, `observations/token_census.json`; same set as `sensitivity_consistent.md` §7). A token counts when it appears in `locator_raw` bounded by characters outside `[A-Za-z0-9_-]`.

NVC = the 960-event B_noVolatileConsistent set of `sensitivity_consistent.md` (240 new_run + 720 original B_noVolatile records of byte-identical cells). Statistics: McNemar uncorrected χ² and exact p; OR = b/c with exact conditional 95% CI; page-clustered percentile bootstrap of Δ (10,000 replicates, seed 42).

Controls: plain-substring locator counts equal §7 of `sensitivity_consistent.md` (B_full 43, NV 48, NVC 53): yes; P5 rows below equal `sensitivity_consistent.json` (2×2 and bootstrap CI): yes.

## 1. Locators per bundle (F0–F3, 960 events each)

| bundle | locators with token (bounded) | locators with token (substring) | P5 successes | of which use a token | P5_sh successes |
|---|---|---|---|---|---|
| B_full | 43 | 43 | 526 | 24 | 502 |
| B_noVolatile | 48 | 48 | 617 | 26 | 591 |
| B_noVolatileConsistent | 53 | 53 | 683 | 20 | 663 |

## 2. B_full → B_noVolatile (960, F0–F3)

| stratum | predicate | B_full | B_noVolatile | Δ pp | both | B_noVolatile-only (b) | B_full-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all (n=960) | P5 | 526/960 (54.79%) | 617/960 (64.27%) | +9.48 | 515 | 102 | 11 | 332 | 73.28 | 1.12e-17 | 1.25e-19 | 9.27 | [4.97, 19.16] | [+4.90, +15.52] |
| all (n=960) | P5_sh | 502/960 (52.29%) | 591/960 (61.56%) | +9.27 | 492 | 99 | 10 | 359 | 72.67 | 1.53e-17 | 1.46e-19 | 9.90 | [5.16, 21.28] | [+4.69, +15.31] |
| has_attribute_signal (n=768) | P5 | 526/768 (68.49%) | 617/768 (80.34%) | +11.85 | 515 | 102 | 11 | 140 | 73.28 | 1.12e-17 | 1.25e-19 | 9.27 | [4.97, 19.16] | [+6.12, +19.60] |
| has_attribute_signal (n=768) | P5_sh | 502/768 (65.36%) | 591/768 (76.95%) | +11.59 | 492 | 99 | 10 | 167 | 72.67 | 1.53e-17 | 1.46e-19 | 9.90 | [5.16, 21.28] | [+5.86, +19.37] |
| no_attribute_signal (NONE + text-only) (n=192) | P5 | 0/192 (0.00%) | 0/192 (0.00%) | +0.00 | 0 | 0 | 0 | 192 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=192) | P5_sh | 0/192 (0.00%) | 0/192 (0.00%) | +0.00 | 0 | 0 | 0 | 192 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |

## 3. B_full → NVC (960, F0–F3)

| stratum | predicate | B_full | NVC | Δ pp | both | NVC-only (b) | B_full-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all (n=960) | P5 | 526/960 (54.79%) | 683/960 (71.15%) | +16.35 | 517 | 166 | 9 | 268 | 140.85 | 1.73e-32 | 1.52e-38 | 18.44 | [9.48, 41.05] | [+10.42, +23.12] |
| all (n=960) | P5_sh | 502/960 (52.29%) | 663/960 (69.06%) | +16.77 | 494 | 169 | 8 | 289 | 146.45 | 1.04e-33 | 2.23e-40 | 21.12 | [10.48, 49.73] | [+10.52, +23.96] |
| has_attribute_signal (n=768) | P5 | 526/768 (68.49%) | 683/768 (88.93%) | +20.44 | 517 | 166 | 9 | 76 | 140.85 | 1.73e-32 | 1.52e-38 | 18.44 | [9.48, 41.05] | [+12.88, +29.23] |
| has_attribute_signal (n=768) | P5_sh | 502/768 (65.36%) | 663/768 (86.33%) | +20.96 | 494 | 169 | 8 | 97 | 146.45 | 1.04e-33 | 2.23e-40 | 21.12 | [10.48, 49.73] | [+12.97, +30.19] |
| no_attribute_signal (NONE + text-only) (n=192) | P5 | 0/192 (0.00%) | 0/192 (0.00%) | +0.00 | 0 | 0 | 0 | 192 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=192) | P5_sh | 0/192 (0.00%) | 0/192 (0.00%) | +0.00 | 0 | 0 | 0 | 192 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |

## 4. B_full×F1 → B_noVolatile×F3 (240, published COP)

| stratum | predicate | B_full×F1 | B_noVolatile×F3 | Δ pp | both | B_noVolatile×F3-only (b) | B_full×F1-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all (n=240) | P5 | 139/240 (57.92%) | 163/240 (67.92%) | +10.00 | 135 | 28 | 4 | 73 | 18.00 | 2.21e-05 | 1.93e-05 | 7.00 | [2.45, 27.47] | [+4.17, +17.08] |
| all (n=240) | P5_sh | 136/240 (56.67%) | 157/240 (65.42%) | +8.75 | 131 | 26 | 5 | 78 | 14.23 | 1.62e-04 | 1.92e-04 | 5.20 | [1.96, 17.34] | [+3.33, +15.83] |
| has_attribute_signal (n=192) | P5 | 139/192 (72.40%) | 163/192 (84.90%) | +12.50 | 135 | 28 | 4 | 25 | 18.00 | 2.21e-05 | 1.93e-05 | 7.00 | [2.45, 27.47] | [+5.08, +21.93] |
| has_attribute_signal (n=192) | P5_sh | 136/192 (70.83%) | 157/192 (81.77%) | +10.94 | 131 | 26 | 5 | 30 | 14.23 | 1.62e-04 | 1.92e-04 | 5.20 | [1.96, 17.34] | [+4.04, +20.10] |
| no_attribute_signal (NONE + text-only) (n=48) | P5 | 0/48 (0.00%) | 0/48 (0.00%) | +0.00 | 0 | 0 | 0 | 48 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=48) | P5_sh | 0/48 (0.00%) | 0/48 (0.00%) | +0.00 | 0 | 0 | 0 | 48 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |

## 5. B_full×F1 → NVC×F3 (240)

| stratum | predicate | B_full×F1 | NVC×F3 | Δ pp | both | NVC×F3-only (b) | B_full×F1-only (c) | neither | χ² (uncorr.) | p | p exact | OR = b/c | OR 95% CI (exact cond.) | bootstrap 95% CI Δ pp |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all (n=240) | P5 | 139/240 (57.92%) | 184/240 (76.67%) | +18.75 | 138 | 46 | 1 | 55 | 43.09 | 5.24e-11 | 6.82e-13 | 46.00 | [7.85, 1855.90] | [+11.25, +27.50] |
| all (n=240) | P5_sh | 136/240 (56.67%) | 180/240 (75.00%) | +18.33 | 135 | 45 | 1 | 59 | 42.09 | 8.73e-11 | 1.34e-12 | 45.00 | [7.68, 1816.40] | [+11.25, +26.67] |
| has_attribute_signal (n=192) | P5 | 139/192 (72.40%) | 184/192 (95.83%) | +23.44 | 138 | 46 | 1 | 7 | 43.09 | 5.24e-11 | 6.82e-13 | 46.00 | [7.85, 1855.90] | [+13.76, +34.60] |
| has_attribute_signal (n=192) | P5_sh | 136/192 (70.83%) | 180/192 (93.75%) | +22.92 | 135 | 45 | 1 | 11 | 42.09 | 8.73e-11 | 1.34e-12 | 45.00 | [7.68, 1816.40] | [+13.64, +33.86] |
| no_attribute_signal (NONE + text-only) (n=48) | P5 | 0/48 (0.00%) | 0/48 (0.00%) | +0.00 | 0 | 0 | 0 | 48 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |
| no_attribute_signal (NONE + text-only) (n=48) | P5_sh | 0/48 (0.00%) | 0/48 (0.00%) | +0.00 | 0 | 0 | 0 | 48 | n/a | n/a | n/a | n/a | n/a | [+0.00, +0.00] |

## 6. Per page (pages with at least one such token)

| page | distinct tokens | B_full locators / P5 lost | B_noVolatile locators / P5 lost | B_noVolatileConsistent locators / P5 lost |
|---|---|---|---|---|
| page_17 | 24 | 6 / 0 | 4 / 0 | 6 / 1 |
| page_18 | 20 | 9 / 8 | 13 / 9 | 9 / 4 |
| page_21 | 18 | 2 / 0 | 4 / 0 | 4 / 0 |
| page_22 | 19 | 10 / 6 | 7 / 5 | 9 / 4 |
| page_23 | 18 | 16 / 10 | 16 / 12 | 17 / 11 |
| page_24 | 13 | 0 / 0 | 4 / 0 | 8 / 0 |

## 7. P5 successes that become failures under P5_sh (70)

| bundle | page | task | enc | token(s) | locator |
|---|---|---|---|---|---|
| B_full | page_18 | t_07 | F0 | `EditPanel_inp__y6z7a8` | `css:input.EditPanel_inp__y6z7a8#card-title` |
| B_full | page_18 | t_07 | F1 | `EditPanel_inp__y6z7a8` | `css:input#card-title.EditPanel_inp__y6z7a8` |
| B_full | page_18 | t_07 | F2 | `EditPanel_inp__y6z7a8` | `css:input#card-title.EditPanel_inp__y6z7a8` |
| B_full | page_18 | t_07 | F3 | `EditPanel_inp__y6z7a8` | `css:input#card-title.EditPanel_inp__y6z7a8` |
| B_full | page_18 | t_08 | F0 | `EditPanel_sel__b9c0d1` | `css:select.EditPanel_sel__b9c0d1#card-assignee` |
| B_full | page_18 | t_08 | F3 | `EditPanel_sel__b9c0d1` | `css:select.EditPanel_sel__b9c0d1#card-assignee` |
| B_full | page_18 | t_09 | F0 | `EditPanel_inp__y6z7a8` | `css:input.EditPanel_inp__y6z7a8[type="date"]` |
| B_full | page_18 | t_09 | F2 | `EditPanel_inp__y6z7a8` | `css:input.EditPanel_inp__y6z7a8[type="date"]` |
| B_full | page_22 | t_01 | F0 | `TfSearch_inp__i8j9k0` | `css:input.TfSearch_inp__i8j9k0#tracking-search` |
| B_full | page_22 | t_08 | F0 | `EditForm_ta__h5i6j7` | `css:textarea.EditForm_ta__h5i6j7#delivery-notes` |
| B_full | page_22 | t_08 | F2 | `EditForm_ta__h5i6j7` | `css:textarea.EditForm_ta__h5i6j7#delivery-notes` |
| B_full | page_22 | t_08 | F3 | `EditForm_ta__h5i6j7` | `css:textarea#delivery-notes.EditForm_ta__h5i6j7` |
| B_full | page_22 | t_09 | F1 | `EditForm_sel__e2f3g4` | `css:select.EditForm_sel__e2f3g4#shipment-priority` |
| B_full | page_22 | t_09 | F2 | `EditForm_sel__e2f3g4` | `css:select#shipment-priority.EditForm_sel__e2f3g4` |
| B_full | page_23 | t_02 | F0 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_full | page_23 | t_02 | F1 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_full | page_23 | t_02 | F2 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_full | page_23 | t_02 | F3 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_full | page_23 | t_04 | F0 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[aria-label="Pay by credit or debit card"]` |
| B_full | page_23 | t_04 | F2 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[role="tab"]` |
| B_full | page_23 | t_04 | F3 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[aria-label="Pay by credit or debit card"]` |
| B_full | page_23 | t_05 | F0 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[aria-label="Continue with PayPal"]` |
| B_full | page_23 | t_05 | F2 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[role="tab"]:not(.active)` |
| B_full | page_23 | t_05 | F3 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[aria-label="Continue with PayPal"]` |
| B_noVolatile | page_18 | t_07 | F1 | `EditPanel_inp__y6z7a8` | `css:input#card-title.EditPanel_inp__y6z7a8` |
| B_noVolatile | page_18 | t_07 | F2 | `EditPanel_inp__y6z7a8` | `css:input#card-title.EditPanel_inp__y6z7a8` |
| B_noVolatile | page_18 | t_07 | F3 | `EditPanel_inp__y6z7a8` | `css:.EditPanel_inp__y6z7a8#card-title` |
| B_noVolatile | page_18 | t_08 | F0 | `EditPanel_sel__b9c0d1` | `css:select#card-assignee.EditPanel_sel__b9c0d1` |
| B_noVolatile | page_18 | t_08 | F3 | `EditPanel_sel__b9c0d1` | `css:select.EditPanel_sel__b9c0d1#card-assignee[name="assignee"]` |
| B_noVolatile | page_18 | t_09 | F0 | `EditPanel_inp__y6z7a8` | `css:input[type="date"].EditPanel_inp__y6z7a8` |
| B_noVolatile | page_18 | t_09 | F1 | `EditPanel_inp__y6z7a8` | `css:input[type="date"].EditPanel_inp__y6z7a8` |
| B_noVolatile | page_18 | t_09 | F2 | `EditPanel_inp__y6z7a8` | `css:input[type="date"].EditPanel_inp__y6z7a8` |
| B_noVolatile | page_18 | t_09 | F3 | `EditPanel_inp__y6z7a8` | `css:.EditPanel_inp__y6z7a8[type="date"]` |
| B_noVolatile | page_22 | t_01 | F0 | `TfSearch_inp__i8j9k0` | `css:input.TfSearch_inp__i8j9k0#tracking-search` |
| B_noVolatile | page_22 | t_07 | F0 | `EditForm_inp__b9c0d1` | `css:.EditForm_inp__b9c0d1#shipment-ref` |
| B_noVolatile | page_22 | t_08 | F0 | `EditForm_ta__h5i6j7` | `css:textarea.EditForm_ta__h5i6j7#delivery-notes` |
| B_noVolatile | page_22 | t_08 | F2 | `EditForm_ta__h5i6j7` | `css:textarea.EditForm_ta__h5i6j7` |
| B_noVolatile | page_22 | t_09 | F0 | `EditForm_sel__e2f3g4` | `css:select.EditForm_sel__e2f3g4#shipment-priority[name="shipment_priority"]` |
| B_noVolatile | page_23 | t_02 | F0 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_noVolatile | page_23 | t_02 | F1 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_noVolatile | page_23 | t_02 | F2 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5` |
| B_noVolatile | page_23 | t_02 | F3 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_noVolatile | page_23 | t_04 | F0 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[aria-label="Pay by credit or debit card"]` |
| B_noVolatile | page_23 | t_04 | F1 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[aria-label="Pay by credit or debit card"]` |
| B_noVolatile | page_23 | t_04 | F2 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[role="tab"]` |
| B_noVolatile | page_23 | t_04 | F3 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[aria-label="Pay by credit or debit card"]` |
| B_noVolatile | page_23 | t_05 | F0 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[aria-label="Continue with PayPal"]` |
| B_noVolatile | page_23 | t_05 | F1 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[role="tab"][aria-label="Continue with PayPal"]` |
| B_noVolatile | page_23 | t_05 | F2 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[role="tab"]:not(.active)` |
| B_noVolatile | page_23 | t_05 | F3 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[aria-label="Continue with PayPal"]` |
| B_noVolatileConsistent | page_17 | t_09 | F3 | `EditPanel_root__a2b3c4` | `css:.EditPanel_root__a2b3c4 input[type="email"]` |
| B_noVolatileConsistent | page_18 | t_08 | F2 | `EditPanel_sel__b9c0d1` | `css:select.EditPanel_sel__b9c0d1[name="assignee"]` |
| B_noVolatileConsistent | page_18 | t_09 | F1 | `EditPanel_inp__y6z7a8` | `css:input[type="date"].EditPanel_inp__y6z7a8` |
| B_noVolatileConsistent | page_18 | t_09 | F2 | `EditPanel_inp__y6z7a8` | `css:.EditPanel_inp__y6z7a8[type="date"]` |
| B_noVolatileConsistent | page_18 | t_09 | F3 | `EditPanel_inp__y6z7a8` | `css:.EditPanel_inp__y6z7a8[type="date"]` |
| B_noVolatileConsistent | page_22 | t_01 | F0 | `TfSearch_inp__i8j9k0` | `css:input#tracking-search.TfSearch_inp__i8j9k0` |
| B_noVolatileConsistent | page_22 | t_08 | F0 | `EditForm_ta__h5i6j7` | `css:textarea.EditForm_ta__h5i6j7#delivery-notes[aria-label="Delivery instructions"]` |
| B_noVolatileConsistent | page_22 | t_08 | F1 | `EditForm_ta__h5i6j7` | `css:.EditForm_ta__h5i6j7` |
| B_noVolatileConsistent | page_22 | t_09 | F0 | `EditForm_sel__e2f3g4` | `css:select.EditForm_sel__e2f3g4#shipment-priority[name="shipment_priority"]` |
| B_noVolatileConsistent | page_23 | t_02 | F0 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_noVolatileConsistent | page_23 | t_02 | F1 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_noVolatileConsistent | page_23 | t_02 | F2 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5` |
| B_noVolatileConsistent | page_23 | t_02 | F3 | `PromoRow_btn__n3o4p5` | `css:button.PromoRow_btn__n3o4p5[aria-label="Apply discount code"]` |
| B_noVolatileConsistent | page_23 | t_04 | F0 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[aria-label="Pay by credit or debit card"]` |
| B_noVolatileConsistent | page_23 | t_04 | F1 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[aria-label="Pay by credit or debit card"]` |
| B_noVolatileConsistent | page_23 | t_04 | F2 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0.active[role="tab"]` |
| B_noVolatileConsistent | page_23 | t_04 | F3 | `PayShell_tab__n8o9p0` | `css:button[role="tab"].PayShell_tab__n8o9p0.active[aria-label="Pay by credit or debit card"]` |
| B_noVolatileConsistent | page_23 | t_05 | F0 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[aria-label="Continue with PayPal"]` |
| B_noVolatileConsistent | page_23 | t_05 | F1 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[aria-label="Continue with PayPal"]` |
| B_noVolatileConsistent | page_23 | t_05 | F2 | `PayShell_tab__n8o9p0` | `css:button.PayShell_tab__n8o9p0[role="tab"]:not(.active)` |

Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: 120 SHA-256 equal.
