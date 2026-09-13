# Data Schema — Records, Bundles, Encodings, Tokenizer

This is the data dictionary for the evidence corpus shipped under `experiments/runs/*.jsonl`
and for the two experimental axes the harness varies. It is a standalone reference —
it does not assume access to any internal working document.

## 1. JSONL record schema

One record is written per grounding event: `(task × bundle × encoding × regime ×
model × repetition)`. The field list below is taken directly from a real record
(`experiments/runs/matrix_page_01.jsonl`, first line) and reconciled against the harness that
produces it, not reconstructed from a design-time checklist — a few field names
changed between design and implementation, noted where relevant.

| Field | Type | Meaning |
|---|---|---|
| `run_id` | string (GUID) | Unique identifier for this grounding event. |
| `task_id` | string | The target/task identifier within the page (e.g. `t_01`). |
| `page` | string | Relative path to the testbed page (e.g. `pages/page_01.html`). |
| `bundle` | string | Attribute bundle applied — one of the seven in §2. |
| `encoding` | string | Serialization format applied — one of `F0`–`F4`, §3. |
| `regime` | string | Context regime for the observation (e.g. `full_page`). |
| `model` | string | Model deployment name requested (e.g. `gpt-4.1`). |
| `repetition` | integer | Repetition index within the cell (0-based). |
| `observation_tokens` | integer | Token count of the serialized observation alone, under the fixed tokenizer (§4). This is the primary cost metric. |
| `prompt_tokens_total` | integer | Token count of the full prompt sent to the model (observation + instructions). |
| `completion_tokens` | integer | Token count of the model's response. |
| `locator_raw` | string | The raw locator string returned by the model, prefixed by type (e.g. `css:input#qty-input...`). |
| `locator_type` | string | Parsed locator type. The canonical prompt is CSS-only. An XPath response is out of format; for a target inside an open shadow root it is classified as `output-format-unreachable`. |
| `locator_value` | string | The locator string with the type prefix stripped. |
| `success` | boolean | Result of the five-part success predicate (§5). |
| `failure_mode` | string \| null | One of three values when `success` is false (see below); `null` on success. |
| `predicate_unique_match` | boolean | Predicate condition 1: the locator resolves to exactly one element. |
| `predicate_matches_oracle` | boolean | Predicate condition 2: the resolved element is the ground-truth target. |
| `predicate_non_volatile` | boolean | Predicate condition 3: the locator uses no volatile signal (hashed/generated id or class). |
| `predicate_non_positional` | boolean | Predicate condition 4: the locator is not positional (`nth-child` etc.). |
| `stable_signal_present_in_bundle` | boolean | Predicate condition 5: at least one stable signal for this target existed in the bundle the model was given. Bundle-aware — always `false` for NONE targets. |
| `model_id_returned` | string | Model identifier as echoed back by the API response (confirms which model actually served the request). |
| `tokenizer_version` | string | Tokenizer encoding used to compute the token fields — pinned to `o200k_base` (§4) regardless of which model produced the record. |
| `schema_version` | string | Version tag for this record schema (`1.0` in the shipped corpus). |
| `testbed_page` | string | Duplicate of `page`, kept for join convenience in some analysis paths. |
| `timestamp_utc` | string (ISO-8601) | Wall-clock time the record was produced. |
| `seed` | integer | Recorded metadata value (`42` throughout the shipped corpus). It was not used as a model-generation seed. |

**`failure_mode` enum** (exactly one of three, in priority order — see §5):
`observation-lacked-a-stable-signal` · `output-format-unreachable` ·
`signal-was-present-but-model-grabbed-the-brittle-one`.

**Fields an earlier design-time checklist described that do not appear as such in
the shipped records** (documented here so nobody goes looking for them): a single
`token_count` field — the shipped schema instead splits this into
`observation_tokens` / `prompt_tokens_total` / `completion_tokens`; a "resolution:
match count, resolved element id(s)" pair — the shipped schema instead carries only
the boolean `predicate_unique_match` (no raw match count or element-id list is
recorded); an "out-of-bundle attribute usage flag" — no such field exists in the
shipped schema, that signal is captured indirectly through
`stable_signal_present_in_bundle` and `failure_mode` instead.

**Temperature is not a recorded field.** No per-record temperature value exists in
this schema — it must be read from the harness code, not from any record.
`shared/harness/LlmClient.cs` sends `temperature=0` only for `gpt-4.1` and
`gpt-4.1-nano`; omits the field for o-series models (`o4-mini`), which reject it;
and omits it entirely for the Anthropic path (`claude-sonnet-4-6`), which has no
`temperature` field in its request at all and so runs at the provider's own
default. See STACK.md §3.

## 2. Attribute bundles (Axis A — content)

Attribute categories (web-DOM instantiation):

| Category | Web attributes |
|---|---|
| Identity | `id`, `data-testid` |
| Semantic-textual | visible text, `aria-label`, `placeholder`, `name` |
| Accessibility | `role`; all other `aria-*` (e.g. `aria-expanded`, `aria-level`, `aria-hidden`, `aria-required`) |
| Structural | `depth`, `siblingIndex`, `parentTag`, `childCount` |
| State | `disabled`, `checked`, `selected`, `value` |

`tag` is always present in every bundle; `class`, `href`, `type`, and `for` are
treated as uncategorized context attributes present only in the richer bundles.

Seven bundles are implemented:

| Bundle | Definition |
|---|---|
| `B_full` | All categories — full-observation baseline. |
| `B_noVolatile` | `B_full` minus attribute *values* flagged volatile for this page (hashed/generated ids and class tokens) — a value-level ablation, not a category removal. |
| `B_noState` | `B_full` minus State (`disabled`, `checked`, `selected`, `value`). |
| `B_noSemantic` | `B_full` minus Semantic-textual (visible text, `aria-label`, `placeholder`, `name`). `role` and other `aria-*` are kept. |
| `B_identityCore` | `tag` + Identity (`id`, `data-testid`) only. |
| `B_minimalCore` | `tag` only. |
| `B_playwrightMCP` | Role + accessible name + Playwright `ref` + level + ARIA state, sourced from the genuine Playwright ARIA snapshot (§3, F4) — not reconstructed from the DOM walk. |

State attributes and Playwright `ref` are present in the observation for the
bundles that carry them, but the fixed predicate treats them as volatile because
state can change during interaction and `ref` changes between snapshots. A locator
keyed on them therefore fails predicate condition 3 even when resolution succeeds.

## 3. Encodings (Axis B — format)

Encoding changes how a fixed attribute set is serialised; it does not add or remove
attributes (that is Axis A's job). Both token cost and grounding success are measured
for each encoding. Five encodings are implemented, all applied to the same
bundle-filtered element list except F4, which uses Playwright's own accessibility-tree
snapshot instead of the DOM walk:

| Encoding | What it emits |
|---|---|
| `F0` | Raw HTML reconstruction — each element as an HTML tag with its filtered attributes and text. Verbose structural baseline. |
| `F1` | Flat JSON array, one object per element, full attribute key names, compact (no whitespace). |
| `F2` | The same JSON structure as F1 with a fixed, bijective key-abbreviation map (e.g. `tag`→`t`, `id`→`i`, `aria-label`→`al`) — a lossless minification, verified by expanding F2 keys back to F1 field names and comparing element-by-element. |
| `F3` | Linearised one-line-per-element DSL: `tag key=value ... {text}`, with values quoted only when they contain a space, `=`, quote, or brace; shadow-root elements are prefixed `[S]`. |
| `F4` | The genuine Playwright ARIA snapshot (`page.AriaSnapshotAsync()`), a YAML-like indented accessibility tree keyed by role and accessible name — never a DOM-walk reconstruction. |

**Worked example**, a button `<button id="qty-add" class="btn-primary" aria-label="Increase quantity">+</button>`, under each encoding (F0–F3 derived directly from the actual encoder implementation in `shared/harness/ObservationEncoders.cs`; F4 shown in the general syntax Playwright's own ARIA snapshot uses, since F4's content comes from Playwright itself rather than this repository's code):

```
F0:  <button id="qty-add" class="btn-primary" aria-label="Increase quantity">+</button>
F1:  {"tag":"button","text":"+","id":"qty-add","aria-label":"Increase quantity","class":"btn-primary"}
F2:  {"t":"button","tx":"+","i":"qty-add","al":"Increase quantity","cl":"btn-primary"}
F3:  button id=qty-add class=btn-primary aria-label="Increase quantity" {+}
F4:  - button "Increase quantity"
```

## 4. Tokenizer and cost convention

Token count is the sole cost unit in this dataset — never converted to dollars or
mixed with latency. The tokenizer is fixed at `o200k_base` (`shared/tokenizer`,
implemented via SharpToken, a tiktoken port) and applied uniformly regardless of
which model produced the record — every record's `tokenizer_version` field reads
`o200k_base` even when `model` is a different family, so that token counts remain
comparable across the cross-model check. Bumping the tokenizer would be a deliberate,
recorded decision; the `tokenizer_version` field exists specifically so that a future
change can be reconciled against historical records rather than silently mixing two
token-counting schemes.

## 5. Success predicate and failure decomposition

A grounding event succeeds only if all five hold: (1) the locator is a unique
match, (2) it matches the oracle element, (3) it uses only non-volatile signals,
(4) it is non-positional, and (5) at least one stable signal for the target was
actually present in the bundle given to the model. Condition 5 is bundle-aware: for
targets with no stable signal at all, it is always false, by design.

Every failure is classified into exactly one of three modes, in this priority
order — the order matters because it names the root cause, not a secondary
property of the locator:

1. `observation-lacked-a-stable-signal` — condition 5 was false.
2. `output-format-unreachable` — the model emitted an out-of-format locator (e.g.
   XPath under the CSS-only instruction) and the target sits where that format
   cannot reach (e.g. a shadow root).
3. `signal-was-present-but-model-grabbed-the-brittle-one` — everything else.