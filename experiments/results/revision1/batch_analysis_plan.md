# Revision 1 — batch analysis plan

Committed before any batch outcome record is opened.

Batch (plan 567c370855a2…, 4,500 events, gpt-4.1 / gpt-4.1-nano at temperature 0, o4-mini at service default). Outcome per event: P5 (five-condition predicate, primary) and P_now (conditions 1+2, secondary). Unit: grounding event; pairs are matched on (page, target, encoding, rep). Statistics reuse p1/analysis/revision1_diagnostics.py: McNemar (uncorrected χ², exact p), OR = b/c with exact conditional 95% CI, page-clustered percentile bootstrap (10,000, seed 42) for differences in success rate. Holm correction within each family below. Strata: has_attribute_signal / no_attribute_signal reported separately where applicable.

F1 Repetitions (block 3; rep 1 = original corpus run): cells gpt-4.1 {B_full×F1, B_noVolatile×F1/F2/F3}, nano {B_noVolatile×F1/F2}.
  (a) Stability: success rate per cell and rep; range across reps; per-event agreement across the 3 reps (share of events with identical P5; Fleiss' κ).
  (b) Headline replication: B_noVolatile×F1 vs B_full×F1 (gpt-4.1), separately for rep 2 and rep 3, and for the per-event majority (≥2 of 3). Replicates if Δ > 0 and the bootstrap CI lower bound > 0 in each rep.
  (c) COP: B_noVolatile×F3 vs B_full×F1 (gpt-4.1) per rep; token difference reported (deterministic).
  (d) F2 drop: B_noVolatile F1 vs F2 per rep, gpt-4.1 and nano.

F2 Single-attribute ablations (block 1, gpt-4.1, F1, rep 1): B_full_minus_{volClass, volId, state, aria} vs B_full×F1, paired. minus_state reuses B_noState×F1 (identical observation). For minus_aria also report the 45 targets whose condition 5 becomes false by construction, and the comparison on the remaining targets.

F3 Key-name legend (block 2): F2L vs F2 and F2L vs F1, same bundle and model: gpt-4.1 B_full, gpt-4.1 B_noVolatile, nano B_noVolatile. Interpretation fixed now: “legend restores” if F2L−F2 > 0 with CI lower bound > 0 AND the CI of F2L−F1 includes 0; “partial” if only the first holds; “no effect” otherwise.

F4 o4-mini (block 4): B_full×F1 vs the existing o4-mini B_noVolatile×F3 (COP) on the same events; direction compared with gpt-4.1. Note decoding at service default. Report the number of events re-issued after client timeout or provider error (batch_runs/released_keys.md) and the comparison with and without them.

Not done: no new model calls; no tuning; no change to the predicate or Oracle; anything else is labelled exploratory.

## Multiplicity

Specification of “Holm correction within each family”, fixed by the author on 2026-10-14 before any outcome record was opened:

- Holm is applied per **family × predicate**: within each family (F1–F4) there is one Holm set for P5 and a separate one for P_now. Each set holds every overall-event McNemar test reported in that family's table.
- Rows in which **both arms come from the original corpus run** (the rep-1 reference rows of F1 b/c/d) are reported with raw p only and are excluded from the Holm sets. The F1 per-event majority rows and every comparison with a newly called arm are included.
- Stratum rows (has_attribute_signal / no_attribute_signal) form their own Holm set per (family, predicate, stratum).
- A test with no discordant pairs (p undefined) is reported as n/a and is excluded from its set.
- F1(a) contains no hypothesis test.
