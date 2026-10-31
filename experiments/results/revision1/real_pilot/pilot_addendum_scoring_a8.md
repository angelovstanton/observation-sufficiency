# Real-site pilot: addendum (е‴) — the reference is regenerated with Firefox open; a site still unstable after 3 generations is "undetermined (no stable reference)"

Author's decision (2026-10-15, afternoon). Text only. Committed **before** the references are
regenerated and before any pilot record is opened (records `fddfba3`, still unopened). It replaces (е″) point 3
(`pilot_addendum_scoring_a7.md`) for this regeneration. Everything else in (е), (е′) and (е″) is unchanged: the walk
(B_full × F1), the pause right after the load, the rule for a stable reference (3 identical cold loads), up to 3
generations, the survival checkpoint, the survival stop at > 5% undetermined and the analysis plan.

## Decision

Archive the current `survival_reference.json` unchanged and generate a new one per (е′)/(е″): 33 sites × 3
cold loads. Check the Firefox, Chrome, Edge and OneDrive processes by name only and record their counts in the file.
If all 33 sites are stable, the reference is committed. If drom.ru or another site is still unstable, it is marked
"undetermined (no stable reference)" per (е′) point 3 and the reference is committed; the site is not removed and is
reported separately.

## Rule (е‴)

1. **Archive.** The `survival_reference.json` of the first reference attempt (3 runs from 2026-10-15T12:20Z, code
   `c9da83a`, Firefox open; 32/33 stable, `0337_drom.ru` not stable in 3 generations; never committed) is kept
   unchanged as `survival_reference_archive/survival_reference_attempt1.json`. It is not used by survival or by the
   analysis. The new file starts from generation 1 for all 33 sites.
2. **Machine.** The regeneration runs with Firefox open. As in (е″) point 1, the file records the processes per image
   name (firefox, chrome, msedge, OneDrive) at the start and the end of each run; they are not touched.
3. **Unstable site.** A site with no stable generation after 3 generations of the new file is marked
   "undetermined (no stable reference)" per (е′) point 3, and the file is committed.
   - The site is not removed.
   - All its survival locators are "undetermined_no_reference" (not evaluated).
   - It is reported apart from survived / broken / undefined / undetermined.
4. **Order.** Reference commit → real-page tests against the committed reference → survival → the main analysis
   (records opened only after the reference commit).
