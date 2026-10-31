# Observation Design / Sufficiency Frontier

## What this measures

The cost/accuracy of the **D → O** transformation: which attribute subset + encoding
preserves grounding success at minimum token cost.

- **Axis A** (content): attribute bundles — `B_full`, `B_noVolatile`, `B_noState`,
  `B_noSemantic`, `B_identityCore`, `B_minimalCore`, `B_playwrightMCP`
  (`B_truncatedText` was planned but not implemented — not in the locked corpus)
- **Axis B** (format): encodings — F0 (HTML), F1 (flat JSON), F2 (compact JSON), F3
  (linearised DSL), F4 (real ARIA snapshot)

Full definitions of every bundle, encoding, and the JSONL record schema are in
[`docs/SCHEMA.md`](docs/SCHEMA.md).

**Implemented scope:** 7 bundles × 5 encodings (25 valid pairs, 10 skipped) × 10 targets
per page, across the 24-page corpus in `shared/testbed/pages/`. Empirics are **LOCKED**
(6000 records in `experiments/runs/matrix_page_*.jsonl`).

## Deliverable

The **Cost-Optimal Profile (COP)** is the measured bundle × encoding combination
identified from the Pareto frontier. The study does not use a fixed success threshold.

## Running

Measurement layer is C# (.NET); analysis is Python.

```
BAR_LEGACY_CONFIRM=paid dotnet run --project experiments/ -- --execute                    # page_01 only
BAR_LEGACY_CONFIRM=paid BAR_PAGE_IDS=page_05,page_08 dotnet run --project experiments/ -- --execute
```

A mode that calls a model runs only with `--execute` and `BAR_LEGACY_CONFIRM=paid` set in the
process for that run; without both it exits with code 2 before any client is created.
Requires `.env` with `BAR_AZURE_OPENAI_ENDPOINT`, `BAR_AZURE_OPENAI_KEY`, and
`BAR_MODEL_DEPLOYMENT_1`. Auth is key-based (`AzureKeyCredential`); there is no
`DefaultAzureCredential` / `az login` path. (The verification suite in `../TESTING.md`
is zero-LLM and needs no credentials at all.)
Output: `experiments/runs/matrix_{pageId}.jsonl`. The 24-page corpus already committed under
`experiments/runs/` (the `matrix_page_*.jsonl` / `axisc_*_page_*.jsonl` files) is the locked,
shipped evidence — a fresh local run writes new files alongside it rather than
overwriting the shipped corpus.

Run modes are selected by environment variable (`SMOKE_TEST`, `PREDICATE_CONTROLS`,
`LLM_SMOKE_TEST`, `VALIDATE_ENCODING`, `AXIS_C`, `DUMP_OBSERVATIONS`, `DUMP_BATCH_OBSERVATIONS`,
`SENSITIVITY_CONSISTENT`, `REAL_PILOT`) or the `--replay` argument. For the
subset that needs no model access, and how to verify the repo end to end, see
[`TESTING.md`](../TESTING.md).

## Revision 1

The revision adds `B_noVolatileConsistent` (volatile-value removal that follows the oracle's
volatility rules exactly), the single-attribute ablations `B_full_minus_volClass`,
`B_full_minus_volId`, `B_full_minus_aria` and `B_full_minus_state`, and the F2L encoding (F2 with a
one-line key dictionary in the prompt). The revision batch and the real-site pilot run through the
separate executable in `batch/`; its outputs, plans and analyses are under `results/revision1/`. See
the "Revision 1" section of the top-level README for the entry points.
