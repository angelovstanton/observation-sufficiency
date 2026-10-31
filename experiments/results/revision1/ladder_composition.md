# Revision 1 — bundle ladder composition

Facts only. Attribute sets are read from the running harness code (`bundle_composition.json`, written by `DUMP_BATCH_OBSERVATIONS=1` from `AttributeBundles.GetBundle`, `ResolveBundleSetForSignalCheck` and `AttributeBundles.AttributeCategories`); initializer expressions and line numbers are parsed from `shared/harness/AttributeBundles.cs`. "text" is the virtual key for the visible text (Semantic-textual).

B_full = 31 keys: alt, aria-checked, aria-controls, aria-describedby, aria-disabled, aria-expanded, aria-haspopup, aria-hidden, aria-label, aria-labelledby, aria-level, aria-live, aria-required, aria-selected, checked, class, data-testid, disabled, for, href, id, name, placeholder, role, selected, src, tabindex, text, title, type, value.

Categories: **identity** = data-testid, id; **semantic_textual** = aria-label, name, placeholder, text; **accessibility** = aria-checked, aria-controls, aria-describedby, aria-disabled, aria-expanded, aria-haspopup, aria-hidden, aria-labelledby, aria-level, aria-live, aria-required, aria-selected, role, tabindex; **structural** = class, src; **state** = checked, disabled, selected, value; **uncategorised** = alt, for, href, title, type.

## 1. Composition

| bundle | defined as (code) | defined relative to | attribute keys | removed vs B_full, by category | value-level stripping |
|---|---|---|---|---|---|
| B_full | `BundleFull` = `new HashSet<string>( _identity.Concat(_semanticTextual).Concat(_accessibility) .Concat(_structural).Concat(_state).Concat(_uncategorised), StringComparer.OrdinalIgnoreCase)` (AttributeBundles.cs:49) | union of the six category sets | 31 | none | no (every value of an admitted attribute is kept) |
| B_noVolatile | `ApplyBundleNoVolatile` (AttributeBundles.cs:190): B_full membership + value filter | B_full | 31 | none | id ∈ truth.json volatile_ids; class token ∈ volatile_classes or a BEM base of one (Oracle.IsBemBaseOfVolatile) |
| B_noState | `BundleNoState` = `new HashSet<string>( BundleFull.Except(_state, StringComparer.OrdinalIgnoreCase), StringComparer.OrdinalIgnoreCase)` (AttributeBundles.cs:60) | B_full | 27 | state (all: checked, disabled, selected, value) | no (every value of an admitted attribute is kept) |
| B_noSemantic | `BundleNoSemantic` = `new HashSet<string>( BundleFull.Except(_semanticTextual, StringComparer.OrdinalIgnoreCase), StringComparer.OrdinalIgnoreCase)` (AttributeBundles.cs:66) | B_full | 27 | semantic_textual (all: aria-label, name, placeholder, text) | no (every value of an admitted attribute is kept) |
| B_identityCore | `BundleIdentityCore` = `new HashSet<string>(StringComparer.OrdinalIgnoreCase) { "id", "data-testid" }` (AttributeBundles.cs:73) | literal set | 2 | semantic_textual (all: aria-label, name, placeholder, text); accessibility (all: aria-checked, aria-controls, aria-describedby, aria-disabled, aria-expanded, aria-haspopup, aria-hidden, aria-labelledby, aria-level, aria-live, aria-required, aria-selected, role, tabindex); structural (all: class, src); state (all: checked, disabled, selected, value); uncategorised (all: alt, for, href, title, type) | no (every value of an admitted attribute is kept) |
| B_minimalCore | `BundleMinimalCore` = `new HashSet<string>(StringComparer.OrdinalIgnoreCase)` (AttributeBundles.cs:78) | literal set | 0 | identity (all: data-testid, id); semantic_textual (all: aria-label, name, placeholder, text); accessibility (all: aria-checked, aria-controls, aria-describedby, aria-disabled, aria-expanded, aria-haspopup, aria-hidden, aria-labelledby, aria-level, aria-live, aria-required, aria-selected, role, tabindex); structural (all: class, src); state (all: checked, disabled, selected, value); uncategorised (all: alt, for, href, title, type) | no (every value of an admitted attribute is kept) |
| B_playwrightMCP | `Observation.BuildAriaObservationAsync` (Observation.cs:94): `page.AriaSnapshotAsync()`, no DOM-walk bundle | separate extraction path | n/a | n/a (ARIA snapshot, not an attribute projection) | n/a |
| B_noVolatileConsistent | `ApplyBundleNoVolatileConsistent` (AttributeBundles.cs:245): B_full membership + value filter | B_full | 31 | none | id / class token flagged by the predicate (Oracle.LocatorUsesVolatileSignal on `[id="…"]` / `[class~="…"]`: labels + BEM base + structural regexes) |
| B_full_minus_volClass | `ApplyBundleMinusVolatileClass` (AttributeBundles.cs:295): B_full membership + value filter | B_full | 31 | none | class tokens flagged by the predicate (as B_noVolatileConsistent); id kept |
| B_full_minus_volId | `ApplyBundleMinusVolatileId` (AttributeBundles.cs:306): B_full membership + value filter | B_full | 31 | none | id flagged by the predicate (as B_noVolatileConsistent); class kept |
| B_full_minus_state | `_bundles["B_full_minus_state"] = BundleNoState` (same set object as B_noState) | B_noState set | 27 | state (all: checked, disabled, selected, value) | no (every value of an admitted attribute is kept) |
| B_full_minus_aria | `BundleFullMinusAria` = `new HashSet<string>( BundleFull.Where(a => !a.StartsWith("aria-", StringComparison.OrdinalIgnoreCase)), StringComparer.OrdinalIgnoreCase)` (AttributeBundles.cs:84) | B_full | 18 | semantic_textual (part: aria-label); accessibility (part: aria-checked, aria-controls, aria-describedby, aria-disabled, aria-expanded, aria-haspopup, aria-hidden, aria-labelledby, aria-level, aria-live, aria-required, aria-selected) | no (every value of an admitted attribute is kept) |

Static bundles apply `AttributeBundles.ApplyBundle` (keep an attribute iff its key is in the set; keep its full value). Value-level bundles keep B_full membership and filter id / class values in the function named above. Condition 5 (`ResolveBundleSetForSignalCheck`) uses B_full for B_noVolatile, B_playwrightMCP, B_noVolatileConsistent, B_full_minus_volClass and B_full_minus_volId.

## 2. Byte comparison of F1 observations (24 pages)

Identical = same sha256 of the observation text. Tokens = mean o200k_base observation tokens per page.

| step | identical pages | mean tokens (from) | mean tokens (to) | Δ tokens | identical on |
|---|---|---|---|---|---|
| B_full → B_noVolatile | 0/24 | 27,096.7 | 25,238.1 | -1,858.6 | none |
| B_noVolatile → B_noState | 0/24 | 25,238.1 | 27,066.3 | +1,828.2 | none |
| B_noState → B_noSemantic | 0/24 | 27,066.3 | 11,909.8 | -15,156.5 | none |
| B_noSemantic → B_identityCore | 0/24 | 11,909.8 | 249.9 | -11,659.9 | none |
| B_identityCore → B_minimalCore | 0/24 | 249.9 | 1.0 | -248.9 | none |
| B_full → B_noState | 4/24 | 27,096.7 | 27,066.3 | -30.4 | page_06, page_07, page_11, page_16 |
| B_full_minus_state → B_noState | 24/24 | 27,066.3 | 27,066.3 | +0.0 | all |
| B_full → B_full_minus_volClass | 4/24 | 27,096.7 | 23,632.5 | -3,464.2 | page_02, page_04, page_12, page_19 |
| B_full → B_full_minus_volId | 2/24 | 27,096.7 | 27,079.5 | -17.2 | page_03, page_07 |
| B_full → B_full_minus_aria | 0/24 | 27,096.7 | 26,851.8 | -244.9 | none |
| B_noVolatile → B_noVolatileConsistent | 18/24 | 25,238.1 | 23,615.1 | -1,623.0 | page_01, page_02, page_03, page_04, page_05, page_06, page_07, page_08, page_09, page_10, page_11, page_12, page_13, page_14, page_15, page_16, page_19, page_20 |

Per page, adjacent ladder steps (= identical, ≠ differs) and F1 tokens per ladder bundle:

| page | B_full→B_noVolatile | B_noVolatile→B_noState | B_noState→B_noSemantic | B_noSemantic→B_identityCore | B_identityCore→B_minimalCore | B_full | B_noVolatile | B_noState | B_noSemantic | B_identityCore | B_minimalCore |
|---|---|---|---|---|---|---|---|---|---|---|---|
| page_01 | ≠ | ≠ | ≠ | ≠ | ≠ | 18,961 | 18,868 | 18,929 | 6,435 | 326 | 1 |
| page_02 | ≠ | ≠ | ≠ | ≠ | ≠ | 3,190 | 3,179 | 3,169 | 1,043 | 184 | 1 |
| page_03 | ≠ | ≠ | ≠ | ≠ | ≠ | 44,544 | 40,766 | 44,514 | 5,519 | 54 | 1 |
| page_04 | ≠ | ≠ | ≠ | ≠ | ≠ | 3,265 | 3,243 | 3,224 | 1,231 | 126 | 1 |
| page_05 | ≠ | ≠ | ≠ | ≠ | ≠ | 10,426 | 9,718 | 10,381 | 4,049 | 259 | 1 |
| page_06 | ≠ | ≠ | ≠ | ≠ | ≠ | 74,790 | 63,793 | 74,790 | 27,987 | 57 | 1 |
| page_07 | ≠ | ≠ | ≠ | ≠ | ≠ | 15,454 | 14,205 | 15,454 | 3,719 | 42 | 1 |
| page_08 | ≠ | ≠ | ≠ | ≠ | ≠ | 99,161 | 96,860 | 99,116 | 43,911 | 3,178 | 1 |
| page_09 | ≠ | ≠ | ≠ | ≠ | ≠ | 48,105 | 44,165 | 48,006 | 10,263 | 85 | 1 |
| page_10 | ≠ | ≠ | ≠ | ≠ | ≠ | 4,045 | 3,958 | 3,995 | 1,483 | 71 | 1 |
| page_11 | ≠ | ≠ | ≠ | ≠ | ≠ | 2,430 | 1,822 | 2,430 | 1,467 | 182 | 1 |
| page_12 | ≠ | ≠ | ≠ | ≠ | ≠ | 2,323 | 2,295 | 2,295 | 837 | 134 | 1 |
| page_13 | ≠ | ≠ | ≠ | ≠ | ≠ | 37,878 | 35,090 | 37,860 | 6,303 | 110 | 1 |
| page_14 | ≠ | ≠ | ≠ | ≠ | ≠ | 3,101 | 2,940 | 3,086 | 1,360 | 101 | 1 |
| page_15 | ≠ | ≠ | ≠ | ≠ | ≠ | 6,614 | 6,272 | 6,594 | 2,666 | 57 | 1 |
| page_16 | ≠ | ≠ | ≠ | ≠ | ≠ | 5,092 | 4,871 | 5,092 | 1,887 | 55 | 1 |
| page_17 | ≠ | ≠ | ≠ | ≠ | ≠ | 110,620 | 107,788 | 110,557 | 75,963 | 113 | 1 |
| page_18 | ≠ | ≠ | ≠ | ≠ | ≠ | 75,339 | 67,506 | 75,278 | 50,410 | 116 | 1 |
| page_19 | ≠ | ≠ | ≠ | ≠ | ≠ | 2,415 | 2,397 | 2,391 | 1,025 | 157 | 1 |
| page_20 | ≠ | ≠ | ≠ | ≠ | ≠ | 4,262 | 4,028 | 4,254 | 1,665 | 63 | 1 |
| page_21 | ≠ | ≠ | ≠ | ≠ | ≠ | 5,807 | 5,655 | 5,803 | 2,787 | 70 | 1 |
| page_22 | ≠ | ≠ | ≠ | ≠ | ≠ | 41,890 | 36,973 | 41,841 | 12,684 | 117 | 1 |
| page_23 | ≠ | ≠ | ≠ | ≠ | ≠ | 16,295 | 15,065 | 16,279 | 11,005 | 223 | 1 |
| page_24 | ≠ | ≠ | ≠ | ≠ | ≠ | 14,314 | 14,258 | 14,253 | 10,136 | 118 | 1 |

B_playwrightMCP has F4 only (ARIA snapshot); an F1 byte comparison is not applicable.

Control — dumped F1 tokens equal the stored corpus `observation_tokens` for the 6 ladder bundles × 24 pages: yes.

Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: 120 SHA-256 equal.
