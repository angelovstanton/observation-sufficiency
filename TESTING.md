# TESTING.md — verifying this repository

Every command here runs **without any model access**. No API key, no Azure login, no
network calls to a provider, no cost. The model outputs of the measurement runs are
committed as JSONL.

Several commands write files: the replay, `run_all.py` and the revision scripts write their
outputs into the repository. Run them in a writable copy (a clone or an extracted archive).

**Do not run** `LLM_SMOKE_TEST`, `AXIS_C`, `VALIDATE_ENCODING`, `SENSITIVITY_CONSISTENT` or the
matrix with `--execute`, and never `experiments/batch` with `--execute`. Those call the model and
spend tokens. Without `--execute` (and its confirmation variable) both entrypoints refuse a paid
mode with exit code 2.

## Prerequisites

- **.NET SDK 10** — every project targets `net10.0` (`Directory.Build.props` aligned).
- **Python 3.12**, then install the analysis deps:
  `pip install -r experiments/analysis/requirements.txt` (pandas, numpy, scipy, tabulate, pytest),
  and for the revision-1 scripts `pip install -r experiments/analysis/requirements-revision1.txt` (statsmodels).
- **Playwright chromium** — `pwsh shared/harness/bin/Debug/net10.0/playwright.ps1 install chromium`,
  or `dotnet tool install --global Microsoft.Playwright.CLI` then `playwright install chromium`.
- **`python` on PATH** — the harness serves the testbed over `http.server`.

**Windows note.** Some analysis output contains characters the legacy `cp1252` console
codec cannot encode. Every Python script here reconfigures `stdout`/`stderr` to UTF-8 at
startup, so no environment setup is needed — the steps below run as-is on a plain console.
(If you run some other, older script that lacks that guard, set `PYTHONIOENCODING=utf-8`
first; this is a console-encoding issue, not a data problem.)

Env-var syntax below is PowerShell: `$env:NAME=1; dotnet run ...`.

---

## 1. Build

```
dotnet build
```

**Proves:** the whole solution compiles. **Expect:** `Build succeeded. 0 Warning(s)
0 Error(s)`. Treat any warning as a regression — the tree is currently warning-clean.

## 2. Oracle unit tests

```
dotnet test shared/oracle.tests
```

**Proves:** the volatility regexes and the success predicate behave as frozen, plus one
BEM-rule parity check that `Oracle.IsBemBaseOfVolatile` and `AttributeBundles.ApplyBundleNoVolatile`
agree. Pure unit facts — no browser, no pages.
**Expect:** `Passed! - Failed: 0, Passed: 69, Skipped: 0, Total: 69`.

## 3. Predicate controls

```
$env:PREDICATE_CONTROLS=1; dotnet run --project experiments/
```

**Proves:** the frozen predicate still returns the hand-labeled verdict for 29 curated
locators spanning all three control dimensions, resolved against real testbed pages.
**Expect:** `── Controls: 29/29 passed ──` and `All controls green`.

## 4. Smoke test

```
$env:SMOKE_TEST=1; dotnet run --project experiments/
```

**Proves:** DOM walk, tokenizer, oracle resolution, encoders, and the oracle-anchor strip
all work end to end on `page_01`. Zero LLM.
**Expect:** `DOM walk: 661 elements`, `Oracle resolution: 10/10 OK`, `strip: OK` on every
encoding, `oracle-leak: none` for the ARIA snapshot, and `F2 round-trip: PASS`.

## 5. Offline replay

Re-classifies previously recorded locators through the current predicate. Zero LLM, zero
cost — it reads model outputs that were recorded months ago and only re-runs the
resolution and classification.

```
dotnet run --project experiments/ -- --replay <dir>        # replay matrix_page_*.jsonl files in <dir>
```

**Scope.** `--replay` needs a directory of `matrix_page_*.jsonl` files to replay; pass
one explicitly. (Without an argument it looks for the newest `experiments/runs/archive_*`
directory — this repo ships none, so the bare form has nothing to resolve.) To replay
all **6000** records across all 24 pages, stage the tracked matrix files in a scratch
directory and point at it (`Directory.GetFiles` is non-recursive, so aiming at
`experiments/runs` directly would also sweep in the `axisc_*` cross-model files):

**Run it in two batches.** A single run over all 24 pages stalls partway through `page_21`
with a Playwright navigation timeout (the pages are served by Python's single-threaded
`http.server`). Split the corpus into two runs, each on its own fresh server (the harness
starts and kills a server per invocation): pages 01–20 (5000 records) then 21–24 (1000).

```powershell
# batch 1 — pages 01–20
$rs1 = "$env:TEMP\rs1"; New-Item -ItemType Directory -Force $rs1 | Out-Null
01..20 | ForEach-Object { Copy-Item ("experiments\runs\matrix_page_{0:D2}.jsonl" -f $_) $rs1 }
dotnet run --project experiments/ -- --replay $rs1
# batch 2 — pages 21–24 (fresh server; the batch-1 process has already exited)
$rs2 = "$env:TEMP\rs2"; New-Item -ItemType Directory -Force $rs2 | Out-Null
21..24 | ForEach-Object { Copy-Item ("experiments\runs\matrix_page_{0:D2}.jsonl" -f $_) $rs2 }
dotnet run --project experiments/ -- --replay $rs2
```

Both batches append to the same `experiments/runs/replay_YYYYMMDD.jsonl`, giving 6000
records. Delete a stale file from the same day first, or the counts will be wrong.

**Proves:** predicate and DOM stability. `ReplayMode` prints the record total and the
NONE-target invariant. It does not compare against the source, so that line is not the
delta verdict. The delta script produces it — it joins the replay output to the source
`matrix_page_*.jsonl` on `page / bundle / encoding / task_id / repetition` and checks
`success`, `failure_mode`, `stable_signal_present_in_bundle`, and `observation_tokens`:

```
python experiments/analysis/replay_delta.py     # defaults: newest replay_*.jsonl vs experiments/runs/matrix_page_*.jsonl
```

**Expect:** `ZERO DELTA` and exit code 0. The script prints `NON-ZERO DELTA` with per-field
counts and exits non-zero on any difference — meaning the predicate or the corpus HTML
changed. This is the guard to run after **any** edit to `shared/testbed/pages/`.

Output goes to `experiments/runs/replay_YYYYMMDD.jsonl` (gitignored — it is a check, not
a result).
Full-corpus replay drives a real browser over 6000 records; measured on reference
hardware: ~16 minutes for the 5000-record batch, ~5 minutes for the 1000-record batch
(~21 minutes total).

## 6. Analysis reconciliation

```
cd experiments/analysis; python run_all.py
```

**Proves:** the 44 reconciled values from the original corpus still recompute from the raw JSONL. Runs
six analysis modules, then reconciles them against values hardcoded from the
prior analyses — success rates, token means, the Pareto frontier, failure decomposition,
McNemar, and the bootstrap CI.
**Expect:** `44/44 MATCH` and `All values consistent with prior analyses.`

It also writes `experiments/computed_findings.md` and verifies by SHA-256 that `experiments/FINDINGS.md`
was **not** modified, printing `(experiments/FINDINGS.md was NOT modified — verified by SHA-256
hash)`. An import-time assertion guarantees the two paths can never collide.

## 7. Python unit tests (pytest)

```
cd experiments/analysis; python -m pytest
```

**Proves:** the analysis-layer tripwires hold — the three-mode failure taxonomy
(`test_failure_modes.py`, incl. the residual-table denominator), the truth.json
`signal_attrs` completeness guard (`test_signal_completeness.py`), and the cross-model
guard (`test_cross_model.py`), and the real-site pilot analysis joins and pins
(`test_revision1_pilot_analysis.py`). Dependency: `pytest>=8.0`, listed in
`experiments/analysis/requirements.txt`.
**Expect:** `61 passed` in `experiments/analysis`.

## 8. Revision-1 tests and outputs

```
dotnet test experiments/tests
```

**Proves:** the revision code paths — the B_noVolatileConsistent bundle on the 24 testbed pages, the
batch runner's journal, lock, resume and preflight against the pinned plan (with a fake model client),
the pilot pins, scoring window and survival reference, and that both entrypoints refuse paid modes
without the explicit opt-in. No model calls. Run it after step 1: five tests start the built
`experiments/bin/Debug/net10.0/Experiments.dll`.
Eight test methods in `PilotScoringTimingTests`, `PilotMutationWindowTests` and
`PilotSurvivalReferenceTests` load the archived real-site pages, which are not redistributed; they look
in `../_external/cc_cache/real_pilot/html/` next to the repository and are skipped when the pages are
absent. These tests, and `Clock_pause_at_the_current_time_fires_nothing_and_stops_every_timer`, which uses
synthetic HTML and always runs, depend on page timers and can fail intermittently, especially on a busy
machine. In our full runs one or two of the 390 tests failed, and not always the same ones (for example
the clock-pause test,
`Execute_and_rescore_give_the_same_score_whatever_the_model_latency(delayMs: 30000, repeat: 1)` and
`Survival_on_a_timer_site_gives_the_same_result_as_is_reversed_and_with_a_5s_wait(domain: "wikipedia.org")`).
Isolated reruns have both passed and failed; rerun the affected methods with the following command:
`dotnet test experiments/tests --filter "FullyQualifiedName~Execute_and_rescore_give_the_same_score_whatever_the_model_latency|FullyQualifiedName~Survival_on_a_timer_site_gives_the_same_result_as_is_reversed_and_with_a_5s_wait|FullyQualifiedName~Clock_pause_at_the_current_time_fires_nothing_and_stops_every_timer"`.
**Expect:** without the archived pages, `Passed: 371, Skipped: 8` (about 2 minutes); with them, all 390
test cases run (about 10 minutes).

`python -B experiments/analysis/revision1_text_values.py` recomputes the values quoted in the paper
that no other script writes, checks each one and writes `revision1_text_values.*`; it exits with code 1
if a value differs. **Expect:** `All 27 values match`.

The other revision scripts rewrite their outputs under `experiments/results/revision1/`. Run them from
the repository root in the order given in the README, then compare with `git diff`. Expected
differences:
- `replay/*out*.jsonl` get a new `run_id` and `timestamp_utc` on every run.
- `batch_analysis.md` loses its four-line "Multiplicity note", which was added by hand. `table_cis.*`
  records the SHA-256 of `batch_analysis.md`, so run `revision1_table_cis.py` before
  `revision1_batch_analysis.py`, or restore `batch_analysis.md` with `git checkout` first.
- `pilot_exploratory.*` lacks the broken-locator breakdown when the archived pages are absent.
- On Windows some scripts write CRLF line endings; `git diff` normalises them.

`revision1_claude_api_tokens.py` and `revision1_holm_bfull_family.py` refuse to overwrite an output
that differs; delete the output first to regenerate it.

---

## What a full pass looks like

| Step | Expected |
|---|---|
| `dotnet build` | 0 warnings, 0 errors |
| `dotnet test shared/oracle.tests` | 69/69 passed |
| `PREDICATE_CONTROLS=1` | 29/29 passed |
| `SMOKE_TEST=1` | 10/10 oracle, strip OK, round-trip PASS |
| `--replay` (staged, 6000, batched 01–20 + 21–24) + `replay_delta.py` | `ZERO DELTA` (exit 0) |
| `run_all.py` | 44/44 MATCH, FINDINGS.md unmodified |
| `pytest` (experiments/analysis) | 61 passed |
| `dotnet test experiments/tests` | 371 passed, 8 skipped (390 run with the archived real-site pages) |
| `revision1_text_values.py` | All 27 values match |

If any step fails, stop and diagnose before changing anything else. Steps 3, 5, and 6 are
the ones that would catch a silent corruption of the locked results.
