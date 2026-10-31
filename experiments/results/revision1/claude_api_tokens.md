# EXPLORATORY — not part of any registered plan

Tokenizer dependence of the COP saving (claude-sonnet-4-6).

Run: `python experiments/analysis/revision1_claude_api_tokens.py` (local dependencies only).

Reference: B_full×F1; COP: B_noVolatile×F3. Key = (page, task_id). Only the intersection is used: **210 events, 21 pages**, 10 events per page per cell. Records are included regardless of grounding success.

Reduction = 1 − mean(COP)/mean(reference). 95% page-clustered percentile bootstrap: 10,000 replicates, seed 42, sorted page order, fresh generator per measure. Uses `revision1_diagnostics.page_bootstrap` and `pct_ci` directly; each sampled page contributes all 10 paired events to both cells.

| Measure | Mean reference | Mean COP | Reduction % | 95% CI % |
|---|---:|---:|---:|---:|
| observation_tokens (o200k_base) | 17390.523810 | 10856.238095 | 37.5738 | [34.3986, 39.8355] |
| prompt_tokens_total (Anthropic API; whole prompt) | 20443.123810 | 13335.409524 | 34.7682 | [30.7755, 37.4881] |

## Coverage exclusions

- pages/page_08.html: No B_full×F1 reference events; 10 COP events cannot be paired (partial TPM skip). Available events: {'B_full×F1': 0, 'B_noVolatile×F1': 0, 'B_noVolatile×F2': 0, 'B_noVolatile×F3': 10}.
- pages/page_17.html: No Claude input file; no events in either cell (TPM skip). Available events: {'B_full×F1': 0, 'B_noVolatile×F1': 0, 'B_noVolatile×F2': 0, 'B_noVolatile×F3': 0}.
- pages/page_18.html: No B_full×F1 reference events; 10 COP events cannot be paired (partial TPM skip). Available events: {'B_full×F1': 0, 'B_noVolatile×F1': 10, 'B_noVolatile×F2': 10, 'B_noVolatile×F3': 10}.

The absent/partial-cell pattern is visible in the input records; TPM attribution is documented in existing experiments/FINDINGS.md (Axis C coverage). No missing events are imputed.

## API / observation ratios

sum(prompt_tokens_total) / sum(observation_tokens), using **all available events per cell**. These denominators differ from the paired reduction sample.

| Cell | Events | Pages | API token sum | Observation token sum | Ratio |
|---|---:|---:|---:|---:|---:|
| B_full×F1 | 210 | 21 | 4293056 | 3652010 | 1.175532 |
| B_noVolatile×F1 | 220 | 22 | 4718758 | 4010670 | 1.176551 |
| B_noVolatile×F2 | 220 | 22 | 4701218 | 4003080 | 1.174400 |
| B_noVolatile×F3 | 230 | 23 | 4293449 | 3474190 | 1.235813 |

## Independent cross-check

Separate raw-record aggregation and Python random.Random(42).choices page bootstrap, 10,000 replicates, independent percentile interpolation; no stats.py computation. Point estimates agree with the primary computation. Small CI differences reflect different draws.

- observation_tokens: 17390.523810 → 10856.238095; reduction 37.5738%; Python random 95% CI [34.4931, 39.8612]%.
- prompt_tokens_total: 20443.123810 → 13335.409524; reduction 34.7682%; Python random 95% CI [30.8265, 37.4581]%.

Supplied rounded point-estimate mismatches: none. The supplied API CI ≈ [30.7, 37.5]% is approximate; use the diagnostics-resampler CI above.

## Interpretation limits

- The Pareto frontier cannot be recomputed under Claude tokens because Claude covers only 4 cells.
- gpt-4.1 uses o200k_base, so the existing gpt-4.1 API-token check (diagnostics.md D3) tests the prompt overhead, not a different tokenizer.
- Claude prompt_tokens_total is Anthropic API-reported for the whole prompt (system + observation + task); no Claude observation-only token count is available. This comparison combines tokenizer dependence and prompt overhead; it does not isolate them.
- Coverage exclusions constrain generalization to the omitted large/extreme pages. No LLM calls, network access, or retokenization are used by this script.

## Input SHA-256

| Input | SHA-256 |
|---|---|
| experiments/runs/axisc_claude-sonnet-4-6_page_01.jsonl | 51a18b9eb9f2bb1b2c2c76e922a909a87f6bd26ed2afbb5847301f19f4ad2999 |
| experiments/runs/axisc_claude-sonnet-4-6_page_02.jsonl | 54173093f7cf325d39b6f111d836a359cf147fe45a88ba0fbf2f26eab727e43d |
| experiments/runs/axisc_claude-sonnet-4-6_page_03.jsonl | 544cb09577d725b7023d47c1dfa326ce6bf2ce5235214f2dfcc5b973d3842527 |
| experiments/runs/axisc_claude-sonnet-4-6_page_04.jsonl | fc899f534cb226bec7e97b0367d9b7377904fa387a8aa08e1150a99bec65077f |
| experiments/runs/axisc_claude-sonnet-4-6_page_05.jsonl | bfba7812a69478fae98a94bbb42c9d01ba6dbe9cfc7ea7268453abdd8fec1efa |
| experiments/runs/axisc_claude-sonnet-4-6_page_06.jsonl | 6b69766785642c52144a0179466786efd702f791311909d42dbb129d23f89c3e |
| experiments/runs/axisc_claude-sonnet-4-6_page_07.jsonl | 95aa6608953791ce2676f24aee914f6ebd71788ff6a3b1d0654c3e0659e73213 |
| experiments/runs/axisc_claude-sonnet-4-6_page_08.jsonl | e7252ca268480f0431ff72a011b003e9e693a45228cdc47181ed4a6494a2ad63 |
| experiments/runs/axisc_claude-sonnet-4-6_page_09.jsonl | f3e72b31d8e6c06be8720e3be6b0b73e8ed364ce1028c97d29bf75d8f8184bb4 |
| experiments/runs/axisc_claude-sonnet-4-6_page_10.jsonl | 03820873307d48707f5dea733da51bcfad1b01431bd9d035300da67105e14b3f |
| experiments/runs/axisc_claude-sonnet-4-6_page_11.jsonl | a9771c25a89ad60e5c773f38ca8ebfdc92bac8e54a9d0bf376c1ecb1b7f570a9 |
| experiments/runs/axisc_claude-sonnet-4-6_page_12.jsonl | 9fb4930ab67fa6e9b831eb5b3f1673f491dd6763ad3d54306a506d90018318d3 |
| experiments/runs/axisc_claude-sonnet-4-6_page_13.jsonl | af6cae00d96fddd0b375f3aa74304a6e0a2508251236ed6f08e9c628755f81cd |
| experiments/runs/axisc_claude-sonnet-4-6_page_14.jsonl | b1dc507c3f9f48397cfbbb143ba9122b9b50d650607df1fccef029d0212f6f53 |
| experiments/runs/axisc_claude-sonnet-4-6_page_15.jsonl | b675c32e931ac53a0241d970f1149dff141bd6da6f29089eb1b64c99e0e5b4fe |
| experiments/runs/axisc_claude-sonnet-4-6_page_16.jsonl | 4638eb694fd8fc26f8086163ca6d064c22faa022ee8e03fdef980431e280c9ee |
| experiments/runs/axisc_claude-sonnet-4-6_page_18.jsonl | 9451711da479c56dc2163d62a73662ffaf3218f044f4cc094e679e8606749a66 |
| experiments/runs/axisc_claude-sonnet-4-6_page_19.jsonl | 0cb4d9d14883e710433136029add8bc9b324cb4718263f2b954b7fd4b76c489b |
| experiments/runs/axisc_claude-sonnet-4-6_page_20.jsonl | 5ec8127faf4e26380c9602851f99b8e06f8480e33c274a010b34560a28660f43 |
| experiments/runs/axisc_claude-sonnet-4-6_page_21.jsonl | 9342d02fa2d818e76ee5d6a604354e225160db75039a23ec482f62dd44bbd037 |
| experiments/runs/axisc_claude-sonnet-4-6_page_22.jsonl | 6144daad88b69c8111a49c560a8273e9b0556d04b4b3bc0db0f79aab8177e097 |
| experiments/runs/axisc_claude-sonnet-4-6_page_23.jsonl | 3f26d073d68152fc99a13949ba8aaa0e08e68873fc518d89b39301991b83ed5b |
| experiments/runs/axisc_claude-sonnet-4-6_page_24.jsonl | fb9f244ee2ac9992dd4b9f63bf65f8bb05b4bab860c48621e3b5dbe97257fba4 |
