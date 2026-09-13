# TESTING.md — verifying this repository

Every command here runs **without any model access**. No API key, no Azure login, no
network calls to a provider, no cost. That is deliberate: the entire correctness story
of this study — the predicate, the DOM walk, the tokenizer, the oracle, and the statistics —
is verifiable offline. The only things that need an LLM are the measurement runs
themselves, and their outputs are already committed as JSONL.

**Do not run** `LLM_SMOKE_TEST`, `AXIS_C`, `VALIDATE_ENCODING`, or a bare
`dotnet run --project experiments/` while verifying. Those call the model and spend tokens.

## Prerequisites

- **.NET SDK 10** — every project targets `net10.0` (`Directory.Build.props` aligned).
- **Python 3.12**, then install the analysis deps:
  `pip install -r experiments/analysis/requirements.txt` (pandas, numpy, scipy, tabulate, pytest).
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
This is the strongest single guard on the locked empirics: if the predicate drifts, the
6000 records stop meaning what they meant.
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

**Batch it — a single run over all 24 pages times out.** Python's `http.server` is
single-threaded and degrades after ~5000 requests; a full-corpus run stalls partway through
`page_21` with a Playwright navigation timeout. This is the request ceiling, **not** a bug —
but a reviewer who runs all 24 at once will hit the timeout and assume something is broken.
Split the corpus into two runs, each on its own fresh server (the harness starts and kills a
server per invocation): pages 01–20 (5000 records) then 21–24 (1000).

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
a result). Delete a stale same-day file before a fresh run, since batches append.
Full-corpus replay drives a real browser over 6000 records; measured on reference
hardware: ~16 minutes for the 5000-record batch, ~5 minutes for the 1000-record batch
(~21 minutes total).

## 6. Analysis reconciliation

```
cd experiments/analysis; python run_all.py
```

**Proves:** every headline number in the paper still recomputes from the raw JSONL. Runs
six analysis modules, then reconciles 44 key figures against values hardcoded from the
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
guard (`test_cross_model.py`). Dependency: `pytest>=8.0`, listed in
`experiments/analysis/requirements.txt`.
**Expect:** `18 passed` in `experiments/analysis`.

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
| `pytest` (experiments/analysis) | 18 passed |

If any step fails, stop and diagnose before changing anything else. Steps 3, 5, and 6 are
the ones that would catch a silent corruption of the locked results.
