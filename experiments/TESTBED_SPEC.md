# experiments/TESTBED_SPEC.md — testbed truth format & oracle contract

The contract for how every testbed page carries its ground truth and how the
harness uses it without leaking the answer into the model's observation. The 24
pages and the harness both depend on this. If you change anything here, change it
everywhere — this is load-bearing for the success predicate and the cost metric.

---

## 1. Two views of the DOM (the core idea — read first)

For every grounding event there are **two distinct views of the same page**:

- **Raw DOM** — the page as served, *with* oracle anchors present. The harness
  resolves the model's returned CSS selector against this view to decide which
  element was actually hit. The model never sees it.
- **Observation** — what is serialized into a bundle × encoding and sent to the
  model. Oracle anchors are **stripped** from this view, and token cost is
  measured on this view. The model only ever sees this.

The anchor exists so the harness knows which element is correct; it is removed
before the model sees anything. Resolution-on-raw-DOM is not cheating: the model
produced its CSS selector from the stripped observation and never saw the anchor.

## 2. The oracle anchor

- Attribute: **`data-oracle-id`** (reserved prefix `data-oracle-*` for any future
  bookkeeping attributes).
- Value: the target's stable id, identical to the target's key in `truth.json`
  (convention: `oracle == target id`). Exactly one oracle element per target.
- Anchors are bookkeeping only. They are **never** a grounding signal and are
  **never** visible to the model.

## 3. The stripping contract (harness invariant, fixed before any measurement run)

Three guarantees, non-negotiable:

1. **What:** strip every `data-oracle-*` attribute.
2. **Which channels:** strip on **every** path that produces an observation —
   both the JS DOM-walk bundles **and** the genuine Playwright ARIA snapshot
   (`F4` / `B_playwrightMCP`). Stripping happens at the "build observation" stage,
   not per-bundle. The ARIA snapshot does not normally serialize arbitrary
   `data-*` attributes, so the anchor *should* not appear in `F4` — but this is an
   assumption to **verify empirically on page 1**, never to assume.
3. **When:** strip **before** token counting. The anchor must add zero tokens to
   the observation cost, or it contaminates the cost axis.

**Leak detector (cheap, keep it):** if any returned locator ever references
`data-oracle-*`, stripping failed somewhere — assert/flag it. With correct
stripping this can never happen, so it is a free tripwire.

**Inherently-unstable signals (non-volatile check extension):** The following
signals are unstable by nature and are rejected by the non-volatile criterion
**independent of `volatility_labels`**:

- **State attributes** (`value`, `checked`, `selected`, `disabled`) — change at
  runtime as the user interacts; a locator keyed on them is brittle by definition.
- **Playwright `ref` handle** — ephemeral snapshot identifier, changes between
  Playwright invocations and browser state; a navigation handle, never a grounding
  signal.

A locator that resolves to the correct element via one of these signals is still
recorded as a **failure** (non-volatile criterion not met). The check is a static
parse: if the returned CSS selector references a State attribute or a Playwright
ref token, it fails regardless of resolution outcome.

## 4. `expected_stable_signal` discipline

This field is **analysis-only**. It records which non-volatile signal a correct
locator *could* key on, so the harness can classify a failure. It is **never** put
into the observation, **never** put into the prompt, and **never** influences what
the model sees. Same discipline as the oracle anchor: we know the truth; the model
does not.

### Failure-mode classification priority

There are **three** failure modes, applied in strict priority order. `Oracle.cs`
cites this section as the authority for that ordering:

1. `observation_lacked_stable_signal` — no stable unique signal existed in the
   observation. **Wins over all other modes.**
2. `output_format_unreachable` — the model emitted XPath despite the CSS-only
   instruction (§12) and the target sits inside a shadow root, where XPath cannot
   reach (§13).
3. `model_grabbed_brittle_signal` — a stable signal existed, and the model used the
   volatile one instead.

`lacked` takes precedence for the same reason it beats `grabbed`: the
classification names the **root cause**, not a secondary property of the locator.
A target with no stable signal is unsolvable regardless of what form the model's
answer took, so labelling it by its output format would misattribute the failure.

`model_grabbed_brittle_signal` is the **residual** class under this ordering: a
record lands there whenever a stable signal was present in the bundle and the
locator neither succeeded nor was output-format-unreachable. The dominant case is
a genuine volatile grab (`predicate_non_volatile` false — 601 of 912 grabbed
records), but the bucket also holds locators that used a stable signal yet failed
to resolve: wrong element, non-unique match, or invalid cross-shadow syntax (an
invented `[data-shadow="true"]` attribute, or a descendant selector crossing a
shadow boundary). The name describes the dominant mechanism, not every member.

## 5. `truth.json` format

One file per page: `pages/page_NN.html` + `pages/page_NN.truth.json`.

Page-level metadata + a `volatility_labels` block (so the non-volatile check is
deterministic) + a `targets` array.

```json
{
  "page_id": "page_01",
  "group": "G1",
  "shadow": "S0",
  "semantic_density": "high",
  "size_tier": "standard",
  "fingerprint_variant": "V",

  "volatility_labels": {
    "volatile_ids": ["price_a1b2c3", "stock_9f8e7d"],
    "volatile_classes": ["css-1x2y3z", "sc-bdfBwQ", "data-v-7ba5bd90"]
  },

  "targets": [
    {
      "id": "t_01",
      "intent": "Find the field where you enter the quantity to add to the cart",
      "oracle": "t_01",
      "is_ambiguous": false,
      "expected_stable_signal": "input with stable name=\"quantity\" (also aria-label \"Quantity\")",
      "signal_attrs": ["id", "name", "aria-label"]
    },
    {
      "id": "t_02",
      "intent": "Find the button that adds the product to the shopping cart",
      "oracle": "t_02",
      "is_ambiguous": true,
      "expected_stable_signal": "button with visible text \"Add to cart\"; a near-duplicate \"Add to wishlist\" button exists on the page",
      "signal_attrs": ["data-testid"]
    },
    {
      "id": "t_07",
      "intent": "Find the pack size selector",
      "oracle": "t_07",
      "is_ambiguous": false,
      "expected_stable_signal": "NONE — volatile Vue scope marker only; no aria-label, no data-testid, no stable id; failure classification: observation_lacked_stable_signal",
      "signal_attrs": []
    }
  ]
}
```

### Field reference

| Field | Level | Meaning | Seen by model? |
|-------|-------|---------|----------------|
| `page_id` | page | matches the HTML filename | no |
| `group` | page | G1–G6 (shadow × semantic density) | no |
| `shadow` | page | S0 / S1 / S2 | no |
| `semantic_density` | page | high / low | no |
| `size_tier` | page | standard / large / extreme | no |
| `fingerprint_variant` | page | R / A / V (volatility vehicle) | no |
| `volatility_labels.volatile_ids` | page | ids we generated as volatile | no (drives the non-volatile predicate) |
| `volatility_labels.volatile_classes` | page | classes/attrs we generated as volatile | no |
| `targets[].id` | target | stable target id (== oracle, == `data-oracle-id`) | no |
| `targets[].intent` | target | human goal, description not strategy, attribute-blind | **yes** (goes into the prompt) |
| `targets[].oracle` | target | the correct element's `data-oracle-id` | no |
| `targets[].is_ambiguous` | target | whether near-identical elements exist | no |
| `targets[].expected_stable_signal` | target | analysis-only failure-classification note | **no** |
| `targets[].signal_attrs` | target | attr names carrying a stable unique signal; `[]` = NONE (volatile-only) | no (drives `StableSignalPresentInBundle`) |

**Intent rule (restate, it governs validity):** intent is a description of the
goal — "find the field where you enter your email" — never a strategy or an
attribute name — never "find the input with aria-label='email'". Attribute-named
intent leaks signals a bundle may have removed and is a confound.

## 6. How the harness uses this (per grounding event)

1. Load `page_NN.html` in Playwright → **raw DOM** (anchors present).
2. Build the **observation**: select bundle → strip `data-oracle-*` → serialize in
   the encoding → **count tokens** (`SharpToken`, `o200k_base`).
3. Send canonical *simple* prompt + `targets[i].intent`. One shot, `temperature=0`,
   no tools, no retry. Parse the returned `css:<selector>`. (See §12.)
4. Resolve the CSS selector against the **raw DOM**. Record match count + resolved
   element(s).
5. **Success predicate (all five):** unique match ∧ resolved element's
   `data-oracle-id == targets[i].oracle` ∧ uses only non-volatile signals (static
   parse of the CSS selector against `volatility_labels` **and** the
   inherently-unstable list in §3) ∧ not pure positional/absolute ∧
   `stable_signal_present_in_bundle` — at least one of `signal_attrs` survived into
   the bundle actually shown to the model. The fifth is bundle-aware: for NONE
   targets (`signal_attrs: []`) it is always false, so a NONE target cannot succeed
   in any cell, by design (§16).
6. **Failure class:** one of three modes, in priority order —
   `observation_lacked_stable_signal` > `output_format_unreachable` >
   `model_grabbed_brittle_signal`. See **§4** for the definitions and the rationale
   for the ordering.
7. Write one JSONL record (schema in `experiments/docs/SCHEMA.md §1`).

## 7. Building a page so it carries its own truth

Generate the page and its truth **together**, never reconstruct truth afterwards
(you generate volatility/oracle/ambiguity, so you must record them at creation):

1. Build a realistic S0 page for the chosen domain (realistic chrome: nav, footer,
   decorative blocks → authentic distractor density).
2. As you place each of ~8–12 targets:
   - put a `data-oracle-id="t_NN"` on the correct element,
   - decide its intent (goal, attribute-blind) → write the target entry,
   - if you make it ambiguous (a near-duplicate), set `is_ambiguous: true` and note
     it in `expected_stable_signal`,
   - record which of its ids/classes are volatile → append to `volatility_labels`.
3. Balance intents across the corpus (click · input · toggle · select · submit ·
   navigate).

## 8. Page-1 verification gate (the reason we build ONE page first)

Before replicating to 24, on `page_01` confirm:

- [ ] Stripping removes `data-oracle-*` from **all five encodings** F0–F4 — inspect
      each serialized observation and grep for `oracle`. **Especially F4** (the
      real ARIA snapshot), since that path is not the DOM walk.
- [ ] Token count is computed on the stripped observation (anchor adds 0 tokens).
- [ ] Oracle resolution works against the raw DOM for every target.
- [ ] The 5-part predicate runs deterministically using `volatility_labels`.
- [ ] One full JSONL record is produced and matches the `experiments/docs/SCHEMA.md §1` schema.
- [ ] Leak detector: no returned locator references `data-oracle-*`.
- [ ] Shadow boundary (S1/S2 pages only): F1 observation contains a known signal from
      the deepest shadow target; F4 ARIA snapshot contains it too. (See §13.)
- [ ] NONE-target invariant: every target with `signal_attrs: []` fails with
      `observation_lacked_stable_signal` in every bundle × encoding cell. (See §16.)

Only after all checks pass do we replicate the template across the 24-page plan
(`docs/testbed_corpus_plan.md`).

## 9. Availability ≠ success for decoy-bearing bundles

A prediction table maps **signal availability**, not model behavior. These are
different things for any bundle that retains volatile signals.

- **B_noVolatile** strips volatile ids/classes from the observation. For this
  bundle, if a stable signal is available, the model cannot accidentally pick a
  volatile one — success is predictable from availability.
- **All other bundles** (B_full, B_noState, B_noSemantic, B_identityCore, and
  even B_playwrightMCP for computed-name targets) may retain some volatile
  signals in the observation. For these bundles, the model *sees* both the
  stable and the volatile signal. Whether it uses the stable one is an
  experimental question — **decoy-resistance**.

Consequence: for decoy-bearing bundles, a correct prediction-table cell is
`signal available` (✓) or `signal absent` (✗). A `✓` cell means success *could*
happen; it does not guarantee it. The actual outcome (stable-signal used vs
volatile-signal used) is recorded in the JSONL record's `failure_class` and
`out_of_bundle_usage_flag` fields. This is a valid and reportable dimension of
the frontier — not a defect in the experimental design.

## 10. Ambiguity is allowed and is a frontier axis

Near-identical elements are realistic (responsive duplication, repeated card
grids, sibling buttons) and must be represented in the corpus. Do not remove
near-duplicates to avoid ambiguity.

Rules for ambiguous targets (`is_ambiguous: true`):

1. **Intent must carry a natural-language descriptive disambiguator.** The
   disambiguator encodes region, neighbour, or ordinal in ordinary language —
   never an attribute name or value.
   - Allowed: "…in the breadcrumb", "…next to the Add to cart button",
     "the first one in the related products row"
   - Forbidden: "…with aria-label='Antibiotics'", "…whose data-testid is X"
2. **Success requires a unique resolve.** The 5-part success predicate's
   uniqueness check (`match count == 1`) catches any locator that resolves to
   multiple elements.
3. **A bundle that strips the disambiguating signal makes the target fail on
   uniqueness.** This is an `observation_lacked_stable_signal` failure and a valid
   result — it shows exactly which bundles lose the ability to ground under ambiguity.
   It is a deliberate axis of the frontier, not a corpus defect.
4. **The intent disambiguator is the only channel.** Do not add extra unique
   attributes to the oracle element just to make it resolvable under every
   bundle. The point is that some bundles cannot disambiguate; that variation is
   the measurement.

## 11. `truth.json` is the single authoritative source

Once a page's `truth.json` exists, there must be **exactly one copy** of the
ground-truth data. The in-HTML TARGET SUMMARY comment block is reduced to a
single pointer line and nothing else:

```html
<!-- targets: see pages/page_NN.truth.json -->
```

Rationale: a second copy (the comment block) diverges from `truth.json` any
time either is edited, and the validator checks `truth.json`, not the comment.
Keeping both in sync manually is error-prone at corpus scale (24 pages).

**Applies from page_02 onward.** page_01 predates this rule and retains its
full TARGET SUMMARY comment; treat it as a legacy exception. Do not retroactively
strip page_01's comment without also running the validator to confirm no drift.

## 12. CSS-only locator format (locked before the final corpus run)

The canonical prompt returns `css:<selector>` only. XPath output was removed during
predicate development.

**Rationale:**

- Playwright's CSS engine pierces open shadow DOM at all depths; XPath cannot — shadow
  roots are opaque to XPath axis traversal.
- XPath's main advantage over CSS is axis-based relational navigation
  (`preceding-sibling`, `ancestor`), but this is positional and is rejected by predicate
  4 (non-positional). Removing XPath eliminates an uncontrolled variable without blocking
  any predicate-valid success path.

**Rule for page authors:** every target's stable signal must be reachable by a CSS
attribute selector alone, without axis-based ancestor/sibling disambiguation.

- Allowed: `[attr="value"]`, `[attr^="prefix"]`, `#id`, `tag[type="..."]`,
  tag + attribute combinations.
- Not allowed as the *sole* discriminating signal: position relative to a labelling
  sibling (e.g. a `<label>` as the only way to distinguish two otherwise identical
  inputs). If the HTML has this problem, give the target element an `aria-label` or
  `data-testid`.

**Harness impact:** the non-volatile predicate (§3) and non-positional predicate (§6
step 5) operate as static parses of the CSS selector string. An `xpath:` response
from the model is classified `output_format_unreachable` when the oracle element is
inside a shadow root (CSS engine could reach it; XPath could not) — or evaluated
normally otherwise.

## 13. Shadow DOM: observation and locator rules

The observation builder (`Observation.BuildObservationAsync`) recurses into
`el.shadowRoot` at all depths. Shadow elements appear in the walk identical to
light-DOM elements. Bundles and encodings apply to shadow elements with no special
cases.

**Depth coverage:** both level-1 (S1 pages) and level-2 (S2 pages) shadow roots are
included. The §8 shadow boundary gate verifies this empirically: a known signal from
the deepest shadow target must appear in F1 and in the F4 ARIA snapshot before the
page is accepted.

**CSS resolution:** Playwright's CSS engine resolves selectors from the document root,
piercing open shadow roots natively. Shadow targets do NOT require explicit `>>>` syntax.
A selector like `[aria-label="Play video"]` resolves correctly even when the element is
two shadow levels deep.

**Custom element definition order:** when a shadow host injects a nested custom element
via `innerHTML`, the inner element's `customElements.define` must appear BEFORE the
outer element's. This ensures `connectedCallback` fires in the correct order and both
shadow roots are populated before Playwright navigates to the page.

**Rules for page authors (S1/S2 pages):**

1. Shadow targets must have CSS-reachable stable signals (`aria-label`, `data-testid`,
   `type`, or similar). Never rely on the shadow host element's id as the locator
   anchor — host ids are typically volatile (see §14).
2. The stable signal value must appear literally in the F1 observation. If it does not,
   the DOM walk did not recurse to that depth (§8 shadow boundary gate catches this).
3. Shadow host elements with volatile ids must be listed in `volatile_ids` even though
   the host is not itself a locator target. The model may use the host id as an anchor
   in compound selectors.

## 14. Volatile-labels completeness and BEM-base rule

### Completeness requirement

`volatility_labels.volatile_classes` must enumerate every framework fingerprint token
that appears on any element **visible in the observation**. Fingerprint families:

| Family | Pattern | Example |
|--------|---------|---------|
| Vue scoped | `data-v-[hex]` (attr name) | `data-v-7ba5bd90` |
| Angular | `_ngcontent-[x]-[n]`, `_nghost-[x]-[n]` | `_ngcontent-abc-c42` |
| React CSS Modules | `ComponentName_element__[hash]` | `VideoPlayer_overlay__a2b3c4` |
| BEM hashed suffix | `block__el--mod--[hash]` | `gallery__nav-btn--next--b3c4d5` |

The Oracle and Observation code uses `extraVolatileClasses` (from `truth.json`)
alongside the built-in regex. Where the regex catches a token automatically, explicit
listing is belt-and-suspenders — still required. An unlisted marker reopens the
volatile-leak gap for the BEM-base check (below) and for any locator that uses a CSS
attribute selector on the marker name.

**Practical scope:** enumerate at minimum all volatile tokens on or near TARGET elements.
Non-target elements are covered by the built-in regex but should be listed when they
share a class namespace with a target element.

### BEM-base-of-volatile is itself volatile

The predicate checks not only exact class token matches but also BEM base prefixes.
If `block__el--mod--HASH` is in `volatile_classes`, then any token `T` where a volatile
class starts with `T + "--"` or `T + "__"` is treated as volatile by the static CSS
parse (`.class` and `[class~=class]` checks in `LocatorUsesVolatileSignal`; token
stripping in `ApplyBundleNoVolatile`).

**Rule for page authors:** do NOT place a stable grounding signal on a class name that
is a BEM base prefix of a volatile class. If `volatile_classes` contains
`gallery__nav-btn--next--b3c4d5`, then `gallery__nav-btn--next` is volatile by
extension and cannot serve as a stable signal. Give the element a dedicated
`data-testid` or `aria-label` instead.

## 15. Signal-diversity rule

Stable signals across a page's targets must be spread across attribute categories. If
all stable targets rely solely on `data-testid`, the bundle ablation gradient collapses:
B_identityCore (id + data-testid) and B_noVolatile produce the same success profile, and
the B_noSemantic vs. B_noVolatile contrast vanishes — making the frontier uninformative
about the accessibility axis.

**Attribute categories (from `experiments/docs/SCHEMA.md §2`):**

| Category | Attributes |
|----------|-----------|
| Identity | `id`, `name`, `data-testid`, `data-label`, `href` (when unique) |
| Semantic-textual | visible text (when uniquely identifying), `title`, `alt`, `placeholder` |
| Accessibility | `aria-label`, `aria-describedby`, `role` (when unique) |

**Minimum distribution per page (8–12 targets, excluding NONE targets):**

- ≥2 targets where the **primary** stable signal is `aria-label` (no `data-testid`)
- ≥1 target where the **primary** stable signal is `id`, `name`, or `href`
- ≥1 target where only semantic-textual content or structural `type` discriminates

*"Primary" = the signal that would uniquely ground the element alone in B_noVolatile.*

**Recording:** each target's `signal_attrs` array in `truth.json` is the authoritative
record. Verify the distribution before finalising the page — if all non-NONE targets
list only `data-testid`, the diversity requirement is not met.

## 16. NONE (volatile-only) targets — required per page

Every page must include at least **one** target whose `signal_attrs` is `[]`.

**Definition:** a NONE target is an element whose only discriminating attributes are
volatile — no `aria-label`, no `data-testid`, no stable `id`, no uniquely identifying
text. The observation contains the element's volatile tokens only; no stable unique
signal exists in any bundle × encoding cell.

**Invariant:** NONE targets MUST fail with `observation_lacked_stable_signal` and
`stable_signal_present_in_bundle: false` in **every** bundle × encoding cell. This
invariant is verified by the §8 gate (NONE-target invariant). It is the per-run sanity
check that the `StableSignalPresentInBundle` predicate is functioning correctly.

**Annotation discipline:**

- `expected_stable_signal` for a NONE target must begin with `"NONE — "` followed by
  the reason and the expected failure class, e.g.:
  `"NONE — only volatile React CSS module class; no aria-label, no data-testid, no
  stable id; failure classification: observation_lacked_stable_signal"`.
- **Never "fix" a NONE annotation to make a target pass.** If a NONE target is
  succeeding, investigate the predicate — the annotation records deliberate design
  intent. A success means the predicate is broken, not that the annotation is wrong.
- If a target genuinely should have a stable signal, add one to the HTML (`data-testid`,
  `aria-label`) and update both the annotation and `signal_attrs` — but this is a page
  design change, not an annotation fix.

**Placement:** for S2 pages, distribute NONE targets to provide insufficiency anchors at
multiple shadow depths: ideally ≥1 NONE in light DOM, ≥1 in level-1 shadow, ≥1 in
level-2 shadow. This ensures the predicate fires at each depth across every run.
