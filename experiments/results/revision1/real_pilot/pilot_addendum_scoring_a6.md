# Real-site pilot: addendum (е′) — the September reference: cell B_full × F1, stable in 3 cold loads

Author's decision (2026-10-15). Text only. Committed **before** the code for survival and
before any pilot record is opened. It amends addendum (е) (`pilot_addendum_scoring_a5.md`, commit `a74ace4`), point 1.
Everything else in (е), (д) and (а‴) is unchanged. The paid run, its scoring path, the observation path, the plan
(`pilot_plan.json`, sha256 `b79364225b5e…`) and the data sent to the model are unchanged.

## Decision

The September reference observation is the hash of the walk for cell B_full × F1 (the same walk as the May
observation of that cell), with the page clock paused right after the load. The reference is valid only if it is
identical in 3 cold loads on an unloaded machine. Otherwise all survival results of that site are "undetermined (no
stable reference)" and are reported separately; the site is not removed. The reference is generated and committed
after the pilot, on a quiet machine, and before the pilot records are opened.

## Rule (е′) — replaces the "what" of (е) point 1

1. **What is hashed.** The September reference of a site is the sha256 of the observation in cell **B_full × F1**.
   - It is produced by the same walk as the May observation of that cell (the registered observation walk, the one
     behind `observations_manifest.tsv`).
   - The load is the survival load of (д), and the page clock is paused (а‴) immediately after it, before the walk.
   - The code commit no longer chooses the cell or the walk; (е) point 1 "names the function and the cell" is
     replaced by this.
   - The survival pre-hash of (е) point 2 is the same B_full × F1 observation on the survival attempt's load,
     compared with this reference.
2. **Stable reference.** The reference is valid only if the sha256 is identical in **3 cold loads**.
   - A cold load is a new browser start: warm-up of (а″), then the reference load.
   - The loads run on an unloaded machine, under the load rule of (е) point 3: Firefox, OneDrive, builds, tests and
     any other browser closed, nothing in parallel.
   - `real_pilot/survival_reference.json` records the 3 hashes per site, the walk function and the cell.
3. **No stable reference.** If the 3 hashes of a site are not all identical, the site has no valid reference.
   - All its survival results are **"undetermined (no stable reference)"**. Its locators are not evaluated against an
     unstable reference.
   - They are reported separately, both from "undetermined (unstable DOM)" of (д) and from survived, broken and
     undefined.
   - The site is **not** removed: its targets, records and paired comparisons of the primary analysis are unchanged.
     It is excluded only from the share of survived locators, which (д) already takes over determined locators.
4. **Order.**
   - During the pilot, the machine stays quiet: no browsers, builds or tests.
   - After the pilot ends: the survival code ((е) points 1–3 with this amendment) and the n3 code are written and
     tested.
   - Then the references are generated (3 cold loads per site) and committed.
   - Only after that commit are the pilot records opened and survival computed.
