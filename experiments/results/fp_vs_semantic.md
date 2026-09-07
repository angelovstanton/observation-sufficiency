# Fingerprint vs Semantic Density — confound check

> ⚠️ **SUPERSEDED 2026-07-20** — numbers below reflect the pre-reclassification
> predicate and are retained for provenance only. Canonical results:
> `experiments/FINDINGS.md` / `experiments/computed_findings.md`.

**Date:** 2026-06-19  
**Corpus:** All 24 testbed pages  
**Encoding basis:** F0+F1+F2+F3 aggregated (40 records per bundle per page). F4 excluded.  
**Source:** `experiments/runs/matrix_page_NN.jsonl`, JSONL replay — zero LLM calls.  
**Context:** The marginal FP analysis showed R=+16.9pp, A=+5pp, V=+4.7pp. This analysis tests whether that R advantage is real or confounded by semantic density.

---

## 1. Cross-tab: FP × Semantic density

| FP | LOW | HIGH | Pages |
|---|---|---|---|
| R | **6** | 2 | 05, 08, 11, 14, 16, 18, 21, 23 |
| A | 3 | 5 | 02, 03, 06, 09, 15, 17, 20, 24 |
| V | 3 | 5 | 01, 04, 07, 10, 12, 13, 19, 22 |

R has 6/8 LOW-semantic pages; A and V each have 3/8. The corpus design did not balance fingerprint against semantic density.

---

## 2. Page_21 exclusion effect on marginal FP means

| FP | Mean (all 24) | Mean (excl. page_21) | Change |
|---|---|---|---|
| R | +16.9 pp | +10.0 pp | −6.9 pp |
| A | +5.0 pp | +5.0 pp | 0 pp |
| V | +4.7 pp | +4.7 pp | 0 pp |

Page_21 alone shifts the R marginal mean by 6.9 pp.

---

## 3. Within-semantic breakdown (the key test)

### LOW semantic (12 pages)

| FP | n | Mean delta (all) | Mean delta (excl. p21) | Individual pages |
|---|---|---|---|---|
| R | 6 | +20.0 pp | +11.0 pp | p05=+10%, p08=+15%, p14=+5%, p16=+17.5%, p21=+65%, p23=+7.5% |
| A | 3 | +8.3 pp | +8.3 pp | p06=+15%, p15=+12.5%, p24=−2.5% |
| V | 3 | +10.8 pp | +10.8 pp | p07=+12.5%, p13=+17.5%, p22=+2.5% |

With page_21 excluded: **R=11.0, V=10.8, A=8.3** — gap between R and V is 0.2 pp.

### HIGH semantic (12 pages)

| FP | n | Mean delta | Individual pages |
|---|---|---|---|
| R | 2 | +7.5 pp | p11=+12.5%, p18=+2.5% |
| A | 5 | +3.0 pp | p02=0%, p03=+10%, p09=+10%, p17=−5%, p20=0% |
| V | 5 | +1.0 pp | p01=−5%, p04=+5%, p10=+2.5%, p12=0%, p19=+2.5% |

R appears higher but n=2 — uninterpretable as a fingerprint effect.

---

## 4. Summary table

| FP | LOW# | Mean-all | Mean excl-p21 | LOW-only mean | HIGH-only mean |
|---|---|---|---|---|---|
| R | 6/8 | +16.9 pp | +10.0 pp | +20.0 pp (+11.0 excl. p21) | +7.5 pp (n=2) |
| A | 3/8 | +5.0 pp | +5.0 pp | +8.3 pp | +3.0 pp |
| V | 3/8 | +4.7 pp | +4.7 pp | +10.8 pp | +1.0 pp |

---

## Verdict: fingerprint collapses into semantic density

The R marginal advantage (+16.9 pp) is mostly an artifact of confounding:

1. **Structural imbalance:** R has 6/8 LOW-semantic pages vs 3/8 for A and V. The marginal R mean is inflated by overrepresentation in the high-delta stratum.

2. **Page_21 is the residual driver:** After removing it, within-LOW means are R=11.0, V=10.8, A=8.3 — essentially flat across fingerprint types.

3. **Within-LOW ordering (V ≈ R > A) does not match marginal ordering (R >> A ≈ V).** If fingerprint were independent, within-stratum ordering should resemble marginal ordering. It does not — confirming the marginal pattern is driven by stratum imbalance.

4. **HIGH-semantic within-stratum** (R=+7.5, A=+3.0, V=+1.0) could hint at an R effect, but n=2 for R makes this uninterpretable.

**For the paper:** Report semantic density as the primary moderator. Do not claim fingerprint type as an independent factor — the evidence is confounded and the confound fully explains the marginal gap once page_21 is accounted for. A corpus balanced on FP × semantic (equal cells) would be needed to test the fingerprint claim independently.
