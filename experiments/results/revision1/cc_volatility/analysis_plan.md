# Analysis plan — Common Crawl Part A (pre-registered)

Written and committed before any WARC record was downloaded. Sample: the 100 domains fixed by `sampling_rule.md` (commit `4cb40ce`). The chosen index records (one per domain per crawl) are listed in `dry_run.json` → `qualified_domains`.

## Goal

Test whether the operational definition of volatility from §3.3 predicts which class/id values disappear between CC-MAIN-2026-21 (May 2026) and CC-MAIN-2026-39 (September 2026). The definition uses the same implementation as the Oracle.

## Unit

A unique value per domain, taken from the May snapshot:
- class tokens: the `class` attribute split on whitespace;
- id values: the `id` attribute.

Class and id are analysed separately.

## Outcome

A value **vanishes** if it is absent everywhere in the same domain's September snapshot, in the same attribute type.

## Predictor

The volatile flag from the Oracle, using the same logic. It is computed by a small C# CLI that calls the existing Oracle code without changing it. A Python port is used only as a cross-check.

The port is accepted only if it matches the C# classification 100% on all class/id values of the 24 corpus pages. Below 100%: **STOP**.

## Primary metric

The difference in the share of vanished values: flagged minus unflagged.
- Point estimate and 95% CI by bootstrap over domains (10,000 replicates, seed 42).
- Separately for class and for id.

## Secondary metrics

- **precision:** share of flagged values that vanish;
- **recall:** share of vanished values that are flagged;
- **prevalence:** number of domains with ≥ 1 flagged value;
- a list of the top flagged values that do **not** vanish (false-positive candidates).

## Pre-specified sensitivity analyses

- (a) without the 4 domains whose two snapshots have an identical digest;
- (b) without domains whose class-token Jaccard between the two snapshots is < 0.2 (a full redesign).

## Exclusion

A domain with no class/id values contributes nothing. It is reported as a count and is not removed by hand.

## Interpretation (fixed in advance)

**Support** if the lower bound of the 95% CI for the difference is > 0. Anything else is reported as it is.

## Limitation

Common Crawl stores the server HTML, not the rendered DOM. Classes generated in the browser are missing, so prevalence is underestimated.

---

## Operational definitions

**Snapshots**
- Per domain and crawl, the chosen record is the latest status-200 text/html homepage index line (`dry_run.json`).
- The snapshot is that record's HTTP payload from the WARC file on data.commoncrawl.org.
- A payload with gzip Content-Encoding is decompressed; the count is reported.
- Truncated payloads (`WARC-Truncated`) are kept; the count is reported.

**Integrity (required for every record)**
- `WARC-Payload-Digest` equals `sha1:` + the index digest.
- Also checked and reported:
  - the recomputed base32 SHA-1 of the payload;
  - `WARC-Target-URI` equal to the index URL;
  - WARC-Type `response`;
  - HTTP status 200.

**Extraction**
- Parser: Python `html.parser` with character references decoded. All start and self-closing tags are read.
- Class tokens: each element's `class` value is split on ASCII whitespace (space, `\t`, `\n`, `\f`, `\r`, as in the HTML spec). Empty tokens are dropped.
- id values: each element's `id` value as written. Empty values are dropped.
- Unit: a unique (domain, attribute type, value).

**Outcome**
- A value vanishes if it is not in the domain's September set of the same attribute type.
- Matching is exact and case-sensitive.

**Predictor**
- The C# CLI calls `Oracle.IsVolatileClass(value)` for class tokens and `Oracle.IsVolatileId(value)` for ids, through reflection. These are the private value predicates used by every branch of `LocatorUsesVolatileSignal`; no Oracle source is changed.
- No truth lists exist for external sites, so the list-based checks (`extraVolatile*`, BEM base of a listed class) do not apply.
- Cross-check: the Python port (`_is_vol_class` / `_is_vol_id` in `p1/analysis/revision1_volatile_nv.py`) must agree 100% with the CLI on:
  - all class/id values of the 24 corpus pages (the static `shared/testbed/pages/*.html` together with the runtime `observations/page_XX__B_full__F1.txt`);
  - all Common Crawl values.

  Any disagreement → STOP.

**Primary metric**
- Δ = P(vanish | flagged) − P(vanish | unflagged), with units pooled within type.
- The CI is the domain-clustered percentile bootstrap from `page_bootstrap` / `pct_ci` in `p1/analysis/revision1_diagnostics.py`: 10,000 replicates, seed 42, clusters = domains.
- Replicates in which Δ is undefined (no flagged or no unflagged unit) are excluded, and their number is reported.

**Secondary metrics**
- precision = |vanished ∩ flagged| / |flagged|;
- recall = |vanished ∩ flagged| / |vanished|;
- prevalence = number of domains with ≥ 1 flagged unit (per type);
- the flagged-but-not-vanishing list is ordered by number of domains holding the value (descending), then by number of occurrences in the May snapshots (descending). The top 50 are in the md and the full list is in the json.

**Sensitivity analyses**
- (a) Excludes the domains whose two chosen records have identical digests (4 domains per `dry_run.json`).
- (b) Uses J = |May ∩ Sept| / |May ∪ Sept| over unique class tokens. J = 0 if exactly one set is empty. Domains with both sets empty have no class units.
- Each sensitivity re-computes the primary metric and its CI, for class and for id.

**Nothing beyond this plan**
- No other metric, threshold or exclusion is added.
- If any part of the plan proves infeasible, the analysis stops and the author is asked.
