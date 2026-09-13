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
dotnet run --project experiments/                                  # page_01 only
BAR_PAGE_IDS=page_05,page_08,page_10 dotnet run --project experiments/
```

Requires `.env` with `BAR_AZURE_OPENAI_ENDPOINT`, `BAR_AZURE_OPENAI_KEY`, and
`BAR_MODEL_DEPLOYMENT_1`. Auth is key-based (`AzureKeyCredential`); there is no
`DefaultAzureCredential` / `az login` path. (The verification suite in `../TESTING.md`
is zero-LLM and needs no credentials at all.)
Output: `experiments/runs/matrix_{pageId}.jsonl`. The 24-page corpus already committed under
`experiments/runs/` (the `matrix_page_*.jsonl` / `axisc_*_page_*.jsonl` files) is the locked,
shipped evidence — a fresh local run writes new files alongside it rather than
overwriting the shipped corpus.

Run modes are selected by environment variable (`SMOKE_TEST`, `PREDICATE_CONTROLS`,
`LLM_SMOKE_TEST`, `VALIDATE_ENCODING`, `AXIS_C`) or the `--replay` argument. For the
subset that needs no model access, and how to verify the repo end to end, see
[`TESTING.md`](../TESTING.md).