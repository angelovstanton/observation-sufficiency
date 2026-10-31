# Real-site pilot: addendum (е) — survival checkpoint against a pinned September reference; cost with release liability

Author's decision (2026-10-15). Text only. Committed **before** the paid pilot run, before any
pilot record exists (`batch_runs_pilot/` does not exist), and before the code that implements it. Amends addendum
(д) (`pilot_addendum_scoring_a3.md`) and (а‴) (`pilot_addendum_scoring_a4.md`) for survival, and the run summary of
the analysis (`p1/analysis/revision1_pilot_analysis.py`). The paid run, its scoring path, the observation path, the
plan (`pilot_plan.json`, sha256 `b79364225b5e…`) and the data sent to the model are unchanged.

## Motive

Each site gets a pinned September reference observation: the hash of the first walk with the page clock paused right
after the load, produced on an unloaded machine and committed before the pilot records are opened. Survival uses the
same checkpoint as scoring: pre-hash == pinned → window → evaluation; otherwise a new load, up to 5, then
"undetermined". Survival runs under the same load rule. Separately (n3), the cost in the analysis is the called
records plus the summed liability of the released keys.

Evidence (an independent pre-run review, not shipped; items M2 and n3):
- Survival under (д)+(а‴) has no check of the state **before** the clock pause (`RealPilotOffline.cs:183-217`).
- Without load: as-is, reversed and +5 s orders give 0 differences.
- Under CPU load (16 threads): 3 wikipedia locators (`body:not(.jsl10n-visible) …`, t_06–t_08) flip from survived to
  not survived. Their status stays "determined": window `1/0/1`, 1 attempt. The `jsl10n-visible` timer fired before
  the pause.
- Under the same load, the scoring path's pre-hash caught the change (observation ≠ pinned, window 0) and refused.
- The analysis reports `list_price_usd` from called records only (`revision1_pilot_analysis.py:365`). Released keys
  are only counted, while the runner keeps their bound as a liability under the cap (`RevisionBatchRunner.cs:26`).

## Rule (е)

### 1. September reference observation (one per site)

- **What.** For each of the 33 sites: the sha256 of the **first walk** of its September page (CC-MAIN-2026-39, the
  HTML pinned in `survival_targets.json`).
- **Load.** The load is the survival load of (д): the same loader, shims, September record clock and network
  blocking, without preparation markers.
- **Pause.** The page clock is paused (а‴) **immediately after the load**, before the walk.
- **Walk.** The walk and its serialization are those of the scoring pre-hash, i.e. the registered observation walk.
  The code commit names the function and the cell (bundle × encoding) whose observation is hashed. The reference
  file records both.
- **Unloaded machine.** The reference is produced under the load rule of the paid run: Firefox, OneDrive, builds,
  tests and any other browser closed. Nothing else runs in parallel.
- **When.** After the paid pilot has ended (no browser runs on this machine during the pilot), and **committed
  before any pilot record is opened**.
- **File.** `real_pilot/survival_reference.json`, one entry per site. Each entry holds the site key, the September
  HTML sha256, the reference sha256, the walk function and cell, the commit of the code, and the UTC time.

### 2. Survival checkpoint (same as scoring)

Per locator, per attempt, on a new fresh load of the September page (д):

1. Pause the page clock immediately after the load (а‴).
2. Open the mutation window (а′).
3. First walk; its sha256 must equal the site's pinned reference (**pre-hash == pinned**). Otherwise the attempt
   fails.
4. Inside the window, as in (д): target by role + accessible name (exactly one candidate), `data-oracle-id` on it,
   the frozen Oracle evaluation (resolution only).
5. Close the window. Exactly one excluded record (the marker on that element) and 0 others; otherwise the attempt
   fails.

A failed attempt means a new fresh load, at most 5 attempts per locator, then **"survival undetermined (unstable
DOM)"**, as in (д). The warm-up load after every browser start stays. Each survival result records its attempts, the
observation sha of each attempt and the window counts.

### 3. Load rule for survival

- **Conditions.** Survival runs under the same load rule as the paid run: Firefox, OneDrive, builds and tests
  closed, and no other browser on the machine.
- **Stop.** If more than 10% of the first 100 survival evaluations need more than one load (attempts > 1), the run
  is stopped by its own PID and the load is removed.
- **Rerun.** Survival is then rerun from the start. It is offline and costs nothing. The output of the stopped run
  is not used.

### 4. Cost in the analysis (n3)

- **Called records.** The run summary of the analysis reports the list-price cost of the called records: Σ
  prompt tokens × $2.00 / 1M + Σ completion tokens × $8.00 / 1M.
- **Released keys.** It adds, for every key with a `released` line in the journal, the runner's liability for it:
  Bound(reservation) = reservation × 2 + 256 × 8 µUSD. These are the same numbers as `BudgetModel.Liability`. An
  overrun release adds nothing, because its usage is known and already counted with its response.
- **Report.** Both components and their sum are reported, with the number of released keys. If a released key was
  called again, its response is counted with the called records and its liability stays; nothing is netted.

## Order and constraints

- **Now:** this text only; committed before the paid run.
- **During the pilot:** no browsers, builds or tests on this machine.
- **After the pilot ends:**
  1. The code for (е) points 1–3 and for point 4 is written and tested.
  2. The reference observations are produced (point 1) and committed.
  3. Then the pilot records are opened and survival is computed.
- **Tests required before the code is committed:**
  - pre-hash == reference on all 33 sites on an unloaded machine;
  - the review's survival check (as-is / +5 s / reversed) → 0 differences;
  - the same check under parallel CPU load → 0 differences between determined results. A locator whose pre-hash
    keeps failing becomes "undetermined", never a different "determined" value;
  - a unit test of point 4 on a journal with one released key and one overrun release.
