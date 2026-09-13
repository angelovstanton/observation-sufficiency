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
model should be invoked at all; those are separate, unpublished lines of work.

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

## License

Code (C#, Python) is MIT-licensed (`LICENSE`). The testbed pages and their ground-truth
JSON (`shared/testbed/pages/`) are data, not code, and are licensed CC BY 4.0.

## Citing this work

See [`CITATION.cff`](CITATION.cff).