# Real-site pilot: addendum (е″) — reference and survival on a machine that is not quiet; regeneration; stop at > 5% undetermined

Author's decision (2026-10-15). Text only. Committed after the pilot records were committed unopened
(`fddfba3`), **before** the survival and n3 code, before the references are generated and before any pilot record is
opened. It amends (е) point 3 (`pilot_addendum_scoring_a5.md`) and (е′) point 2 (`pilot_addendum_scoring_a6.md`) for
the conditions of this run only. The rule for a stable reference (3 identical cold loads), the walk (B_full × F1), the
pause, the survival checkpoint and the analysis plan are unchanged.

## Decision

Generate the references (point 3) now with the browsers open, as a declared departure from "unloaded
machine", recording the number of Firefox, Chrome, Edge and OneDrive processes by name in the report and in
`survival_reference.json`; the processes are not touched. The deciding condition stays 3 identical cold loads per
site; a site may be generated up to 3 times while the records are unopened. If all 33 sites are stable, the reference
is committed and point 4 and the main analysis of point 5 follow. If a site is still unstable, it is not yet marked
"undetermined", the reference is not committed, and the site is regenerated on a quiet machine before the records are
opened. The survival run of point 5 also runs now; if more than 5% of its locators are "undetermined", it stops and is
rerun later. The main analysis does not wait for survival.

## Rule (е″)

1. **Machine.** The references (е′) and the survival run (е) may run with the author's browsers and OneDrive open. This
   is a departure from "unloaded machine". `survival_reference.json` and the survival output record the number of
   processes per image name (firefox, chrome, msedge, OneDrive) at the start of the run. Those processes are not
   touched.
2. **Generations.** A generation is 3 cold loads of a site (new browser start, warm-up (а″), reference load).
   - A site whose 3 hashes differ may be generated again, up to **3 generations** in total. This is allowed only while
     the pilot records are unopened.
   - Every generation and its hashes are kept in the file; the reference is the hash of the generation whose 3 loads
     are identical.
3. **No commit with an unstable site.** If any site has no stable generation after 3 generations, nothing is marked
   "undetermined (no stable reference)" yet and the reference file is not committed.
   - The sites are reported.
   - They are generated again on a quiet machine before the records are opened.
   - Only a run on a quiet machine may then apply (е′) point 3.
4. **Survival stop.** Besides the load rule of (е) point 3, the survival run stops as soon as more than 5% of its
   locators are "undetermined". Its output is not used, and survival is rerun on a quiet machine.
   - The primary and sensitivity analyses do not wait for survival. They run once the reference is committed, and
     report survival as "not computed" until a valid survival run exists.
