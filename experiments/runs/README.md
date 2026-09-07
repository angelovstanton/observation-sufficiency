# `experiments/runs/` — the shipped evidence corpus

This directory holds the locked, evidence-of-record JSONL corpus. Every number in
`experiments/FINDINGS.md` and `experiments/results/computed/` is regenerable from exactly these files —
see `experiments/analysis/run_all.py` and `TESTING.md` §6.

## Files

- **`matrix_page_01.jsonl` … `matrix_page_24.jsonl`** (24 files) — the primary corpus:
  GPT-4.1 over the full 25-pair bundle×encoding matrix × 10 targets × 24 pages =
  **6,000 records**. This is the source of every headline number in `experiments/FINDINGS.md`.
  Consumed by `experiments/analysis/load.py` (and everything built on it: `thesis.py`,
  `bundle_ladder.py`, `encoding.py`, `pareto.py`, `failure_decomp.py`, `stats.py`,
  `axis_c_feasibility.py`).
- **`axisc_gpt-4-1-nano_page_01.jsonl` … `_page_24.jsonl`** (24 files) and
  **`axisc_o4-mini_page_01.jsonl` … `_page_24.jsonl`** (24 files) — Axis C cross-model
  runs on the COP + neighbouring cells, one model per file set. See
  `experiments/FINDINGS.md` (Axis C / cross-model form-invariance).
- **`axisc_claude-sonnet-4-6_page_01.jsonl` … `_page_24.jsonl`** (23 files — `page_17`
  is absent: Claude's serverless TPM quota could not process that page's 110K-token
  observation) — the fourth Axis C model. Cross-model comparisons therefore use the
  common-event subset across all four models where every model has a record; see
  `experiments/analysis/cross_model.py`.

That is 24 + 24 + 24 + 23 = 95 data files, all consumed by
`experiments/analysis/cross_model.py`'s three `axisc_*` glob patterns plus the primary corpus.

## Record schema

See [`../docs/SCHEMA.md`](../docs/SCHEMA.md) §1 for the full field-by-field schema,
derived directly from a real record in this corpus.

## Regenerating a fresh run (optional — not required to verify the shipped numbers)

A fresh local run needs a model API key and writes new `matrix_{pageId}.jsonl` files
alongside this corpus rather than overwriting it — see `../README.md` and
`../../TESTING.md`. Verifying the numbers already in `experiments/FINDINGS.md` requires no
model access at all; see `../../TESTING.md` §6.
