# observation-sufficiency

Public artifact for a paper on cost-bounded LLM-driven UI element grounding. The
question: when a language model is asked to produce a locator for a UI element, how do
the tested attribute subsets and serialisation formats affect grounding success and
token cost? Cost is measured in tokens under a fixed tokenizer — never dollars,
never latency.

## What's in the box

- **The controlled testbed**: 24 static HTML pages (`shared/testbed/pages/`) varying
  shadow-DOM depth, framework-style DOM fingerprints (React/Angular/Vue-imitating
  hashed attributes), responsive-breakpoint duplication, and page size, each shipped
  with hand-authored ground truth (`*.truth.json`).
- **The locked evidence corpus**: 95 JSONL files under `experiments/runs/`, in two parts —
  6,000 grounding-event records across the 24 files in `experiments/runs/matrix_page_*.jsonl`
  (GPT-4.1, the full Axis A × Axis B bundle × encoding design), and 2,080
  grounding-event records across the 71 files in `experiments/runs/axisc_*.jsonl` (Axis C,
  the cross-model check: GPT-4.1-nano, o4-mini, and Claude Sonnet run alongside
  GPT-4.1 — four models total). Axis C coverage is limited by serverless TPM
  quota (Claude in particular could not process every page's observation size),
  so cross-model comparisons use a common-event subset, n=870 — see
  `experiments/FINDINGS.md` for the full accounting. See
  [`experiments/runs/README.md`](experiments/runs/README.md) for the exact file-by-file breakdown.
- **The measurement harness** (C#/.NET) that produced that corpus: the DOM-attribute
  walk, the seven attribute bundles, the five encodings, the fixed `o200k_base`
  tokenizer, and the five-part success predicate — see
  [`experiments/docs/SCHEMA.md`](experiments/docs/SCHEMA.md) for the full data dictionary.
  `B_playwrightMCP`/F4 use Playwright's own genuine ARIA snapshot, never a DOM-walk
  reconstruction.
- **The analysis code** (Python) that turns those 8,080 records into every number in
  [`experiments/FINDINGS.md`](experiments/FINDINGS.md), plus a 44-point reconciliation check against
  those numbers.

**Scope.** This artifact covers the observation layer only — *what* gets sent to the
model. It does not address element-resolution robustness under DOM drift or when the
model should be invoked at all.

## Model slate

GPT-4.1, GPT-4.1-nano, o4-mini, and Claude Sonnet are used in the cross-model
robustness check. The paired bundle comparison is available for GPT-4.1,
GPT-4.1-nano, and Claude. o4-mini was run only on the COP cell. The purpose is to
check whether the main observation result appears across the tested models, not
which model wins. See `experiments/FINDINGS.md` for the full accounting.

## Verifying the results

The full evidence-to-findings pipeline is verifiable **offline after dependencies are
installed, with no API key, no provider network calls, and no cost** — see [`TESTING.md`](TESTING.md) for the exact
commands. In outline: `dotnet build` → oracle unit tests → predicate controls
(29 hand-labeled locators) → a smoke test → an offline replay of the full 6,000-record
corpus against the frozen predicate → the Python analysis reconciliation (44/44 match
against `experiments/FINDINGS.md`) → the Python unit-test suite. The harness starts and stops
its own `http.server` instance per invocation — there is no separate server to start
by hand. Measured end-to-end on reference hardware: roughly **25 minutes**, almost
entirely the full-corpus replay step (~21 of those minutes) — every other step
finishes in seconds.

## Revision 1 (v1.1.0)

Version 1.1.0 adds the material for the revised paper under `experiments/results/revision1/`. The
original corpus, `experiments/FINDINGS.md` and `run_all.py` are unchanged; where `FINDINGS.md` differs
from the revised paper, the revision outputs are authoritative.

- `batch_runs/`: 4,500 grounding events of the additional batch (repeated generations, F2L,
  single-attribute ablations, o4-mini B_full × F1), with the pinned plan `batch_plan.json`, the
  analysis plan `batch_analysis_plan.md` and the observations sent in `batch_observations/`.
- `consistent_runs/`: 240 events of the B_noVolatileConsistent sensitivity run.
- `cc_volatility/`: the Common Crawl check of the volatility rule.
- `real_pilot/` and `batch_runs_pilot/`: the 33-site real-site pilot (1,956 events), its rule,
  analysis plan and addenda, and `pilot_survival.tsv` for the September pages.
- `experiments/batch/`: the runner used for the batch and the pilot; `experiments/tests/`: its tests.

`PROVENANCE.md` gives the commit and date of each plan and rule and the event it preceded. In the
frozen plan, rule and addendum documents, paths written as `p1/...` refer to `experiments/...`.

### Scripts

All scripts run from the repository root with no model calls and write their outputs into the
repository, so run them in a writable copy. They need `experiments/analysis/requirements-revision1.txt`
in addition to `requirements.txt`.

**Run from the shipped records and testbed.** These entry points reproduce the revision analyses
offline:

| Script (`experiments/analysis/`) | Output (`experiments/results/revision1/`) | Content |
|---|---|---|
| `revision1_batch_analysis.py` | `batch_analysis.*` | generation variability, F2L, ablations, o4-mini (Tables S3–S6) |
| `revision1_cop_vs_aria.py` | `cop_vs_aria.*` | COP vs B_playwrightMCP × F4 |
| `revision1_corpus_bundle_by_model.py` | `corpus_bundle_by_model.*` | Table 7 confidence intervals |
| `revision1_claude_api_tokens.py` | `claude_api_tokens.*` | Claude API-token check |
| `revision1_leak_scope.py` | `leak_scope.*`, `consistent_cells.json` | unlabelled hashed tokens kept by B_noVolatile |
| `revision1_sensitivity_consistent.py` | `sensitivity_consistent.*` | B_noVolatileConsistent (Table S7) |
| `revision1_short_hash_sensitivity.py` | `short_hash_sensitivity.*` | short-hash sensitivity |
| `revision1_ladder_composition.py` | `ladder_composition.*` | bundle definitions |
| `revision1_batch_nonadditivity.py` | `batch_exploratory_nonadditivity.md` | ablation non-additivity |
| `revision1_text_values.py` | `revision1_text_values.*` | values quoted in the text that no other script writes |
| `revision1_pilot_analysis.py` | `pilot_analysis.*` | real-site pilot (Table 9, Tables S9–S11) |
| `revision1_pilot_exploratory.py` | `pilot_exploratory.*` | exploratory pilot analyses |
| `revision1_diagnostics.py` | `diagnostics.*`, `replay/` | P_now, GEE, page-level tests, F2 mechanism (Table S2) |
| `revision1_holm_bfull_family.py` | `holm_bfull_family.*` | Holm families (Table S1) |
| `revision1_table_cis.py` | `table_cis.*` | confidence intervals in Tables 2 and 5 |
| `revision1_volatile_nv.py` | `volatile_in_noVolatile.*`, `replay/volatile_nv/` | volatile grabs under B_noVolatile |

`revision1_diagnostics.py` and `revision1_volatile_nv.py` also need .NET and Playwright; they replay
recorded locators against the testbed. Run order where outputs feed each other:
`revision1_diagnostics.py` → `revision1_holm_bfull_family.py` → `revision1_table_cis.py`, and
`revision1_leak_scope.py` → `revision1_sensitivity_consistent.py` → `revision1_short_hash_sensitivity.py`.
The shipped `batch_analysis.md` carries a short "Multiplicity note" added by hand, which the script
does not write. The breakdown of broken locators in `revision1_pilot_exploratory.py` needs the
archived pages and is skipped without them; no number in the paper depends on it.
`experiments/results/revision1/cc_volatility/cc_classifier_validation.py` also runs from the shipped
files (testbed pages and observation dumps; it needs .NET) and writes `cc_volatility/classifier_validation.*`.
`experiments/analysis/revision1_batch_dryrun.py` is the historical plan generator: it wrote the pinned
`batch_plan.json`, and running it again overwrites that file.

**Need the archived pages or the WARC cache.** The Common Crawl acquisition and analysis and the
real-site pilot preparation and survival scripts below (under `experiments/results/revision1/`) do not
run from the shipped files; they show how the shipped inputs were produced. They expect the cache in
`../_external/cc_cache/` next to the repository; `real_pilot/pilot_sites.json` records the absolute form
of that path used when it was written. `cc_common.py`, `rp_common.py`, `rp_*.js` and `oracle_cli/` are
helpers used by these scripts.

| Script | Needs | Writes |
|---|---|---|
| `cc_volatility/cc_index_scan.py` | network (Common Crawl index, Tranco list) | `cc_volatility/dry_run.*` (sample, WARC pointers) |
| `cc_volatility/cc_fetch_warc.py` | network | WARC records in the cache, `cc_volatility/fetch_integrity.*` |
| `cc_volatility/cc_volatility_analysis.py` | WARC cache, .NET | `cc_volatility/volatility_analysis.*` (Table S8) |
| `real_pilot/rp_sites.py` | WARC cache, pilot state and dumps | `real_pilot/pilot_sites.json` |
| `real_pilot/rp_eligibility.py` | archived pages, .NET, Playwright | `real_pilot/eligibility.*` |
| `real_pilot/rp_targets.py` | pilot state in the cache | `real_pilot/targets.json` |
| `real_pilot/rp_redump.py` | archived pages, .NET, Playwright | pilot observation dumps, `real_pilot/observations_manifest.tsv`, `real_pilot/dump_checks.json`, `real_pilot/eligibility.json` |
| `real_pilot/rp_measure_d.py` | archived pages, .NET, Playwright | `real_pilot/d_remeasure.json` |
| `real_pilot/rp_cost.py` | pilot observation dumps | `real_pilot/cost_estimate.json` |
| `real_pilot/rp_plan.py` | pilot observation dumps | `real_pilot/pilot_plan.json`, `real_pilot/pilot_reuse_map.json` |
| `real_pilot/rp_survival.py` | archived September pages, .NET, Playwright | `real_pilot/survival_targets.json`, `real_pilot/survival_reference.json`, `pilot_survival.tsv` |

Third-party pages are not redistributed. They can be re-fetched from the WARC pointers in
`cc_volatility/dry_run.json`, `real_pilot/pilot_sites.json` (May) and `real_pilot/survival_targets.json`
(September); `html_sha256` pins the decoded page bytes.

The batch and the pilot were run with `experiments/batch`, which starts a paid run only with
`--execute` and `BAR_BATCH_CONFIRM_PLAN` set to the plan's hash prefix. The original entrypoint
refuses every model-calling mode unless it gets `--execute` with `BAR_LEGACY_CONFIRM=paid`.

## License

Code (C#, Python) is MIT-licensed (`LICENSE`). The testbed pages and ground truth
(`shared/testbed/pages/`), the records and results (`experiments/runs/`, `experiments/results/`) and
the documentation are licensed CC BY 4.0. Neither licence covers third-party content: values derived
from public web pages in the pilot and Common Crawl files remain with their owners, and the pages
themselves are not redistributed.

## Citing this work

See [`CITATION.cff`](CITATION.cff).