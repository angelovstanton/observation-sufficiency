using System.Text.RegularExpressions;
using Microsoft.Playwright;

namespace BoundedAgents.Shared.Oracle;

// =============================================================================
// PREDICATE RE-FROZEN 2026-06-17T18:34:41Z — post-external-audit re-validation.
// Predicate re-validated after an independent second-family code audit. 16 controls
// added (29 total) covering: CSS exact/unquoted id+class attribute selectors,
// B_playwrightMCP ARIA-bundle signal availability, NONE-shadow-XPath failure-mode
// priority, and VolatileClassRe over-rejection — locked in both directions against
// real testbed volatile_classes and legitimate semantic classes. Two-layer volatile
// detection confirmed: structural regex backstop + per-page enumerated
// volatile_classes (authoritative). Re-replay of 2750 records under corrected
// predicate: +46 net success, thesis contrast (B_full vs B_noVolatile) intact.
// No modifications after this point without documented re-validation.
// See experiments/PREDICATE_MANIFEST.md for full validation evidence.
// =============================================================================
public static class Oracle
{
    // -----------------------------------------------------------------------
    // Volatile-signal detection
    // -----------------------------------------------------------------------

    // Framework-generated class hashes: React/css-modules, styled-components,
    // CSS Modules, Angular _ngcontent, Vue data-v-
    private static readonly Regex VolatileClassRe = new(
        @"[a-z]{1,3}-(?=[a-zA-Z0-9]*[A-Z0-9])[a-zA-Z0-9]{6,}" +  // css-xK2mPq (lookahead: ≥1 digit/uppercase in suffix)
        @"|[A-Za-z]+_[A-Za-z0-9]{5,}__" +         // Button_root__xK2mP
        @"|_ngcontent-[a-z]+-[a-z0-9]+" +          // Angular
        @"|data-v-[a-f0-9]+",                       // Vue
        RegexOptions.Compiled);

    // Auto-generated IDs: React internals (:r0:) or pattern item-1234
    private static readonly Regex VolatileIdRe = new(
        @"^:?[rR][a-zA-Z0-9]+$|^[a-z]+-[0-9]{4,}$",
        RegexOptions.Compiled);

    private static readonly Regex XpathPositionalRe = new(
        @"\[\s*\d+\s*\]|position\s*\(\s*\)|last\s*\(\s*\)",
        RegexOptions.Compiled);

    private static readonly Regex CssPositionalRe = new(
        @":nth-child\(|:nth-of-type\(|:first-child|:last-child|:first-of-type|:last-of-type",
        RegexOptions.Compiled);

    private static bool IsVolatileClass(string value) =>
        VolatileClassRe.IsMatch(value);

    private static bool IsVolatileId(string value) =>
        VolatileIdRe.IsMatch(value.Trim());

    // A class token is volatile if it is a direct BEM base of a volatile class:
    // e.g. "gallery__nav-btn--next" is a base of "gallery__nav-btn--next--b3c4d5".
    // Only checks one separator level (-- or __) to avoid over-reaching on short tokens.
    internal static bool IsBemBaseOfVolatile(string token, IReadOnlySet<string>? volatileClasses) =>
        volatileClasses?.Any(vc =>
            vc.StartsWith(token + "--", StringComparison.Ordinal) ||
            vc.StartsWith(token + "__", StringComparison.Ordinal)) == true;

    /// <summary>
    /// Returns true if the oracle element has at least one signal attribute with
    /// non-empty, non-volatile content after bundle filtering.
    /// Checks value-level filtering for class/id (the only attrs B_noVolatile filters
    /// by value); all other attrs are accepted if the attr name is in the bundle.
    /// signalAttrs=[] (NONE targets) → always false.
    /// </summary>
    public static bool ComputeStableSignalPresence(
        IReadOnlyList<string>? signalAttrs,
        Func<string, bool> bundleContains,
        ElementData? rawOracleEl,
        IReadOnlySet<string>? volatileIds,
        IReadOnlySet<string>? volatileClasses)
    {
        if (signalAttrs is not { Count: > 0 } || rawOracleEl is null)
        {
            return false;
        }

        foreach (var attr in signalAttrs)
        {
            if (!bundleContains(attr))
            {
                continue;
            }

            if (!rawOracleEl.Attrs.TryGetValue(attr, out var val) || string.IsNullOrEmpty(val))
            {
                continue;
            }

            if (attr.Equals("class", StringComparison.OrdinalIgnoreCase))
            {
                if (val.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                       .Any(c => volatileClasses?.Contains(c) != true
                              && !IsBemBaseOfVolatile(c, volatileClasses)))
                {
                    return true;
                }

                continue;
            }
            if (attr.Equals("id", StringComparison.OrdinalIgnoreCase))
            {
                if (volatileIds?.Contains(val) != true)
                {
                    return true;
                }

                continue;
            }
            return true;
        }
        return false;
    }

    /// <summary>
    /// Predicate 4. True when the locator uses no positional construct
    /// ([N], position(), last(), :nth-child). Matching is syntactic: a
    /// structurally-bounded position is not distinguished from an unbounded
    /// ordinal one, which is a deliberate conservative choice (see §39A).
    /// </summary>
    public static bool LocatorIsNonPositional(string locatorType, string locatorValue) =>
        locatorType switch
        {
            "xpath" => !XpathPositionalRe.IsMatch(locatorValue),
            "css"   => !CssPositionalRe.IsMatch(locatorValue),
            _       => true,
        };

    /// <summary>
    /// Returns true if the locator leans on a volatile signal — either one
    /// matched by the built-in regex patterns or one listed in the page-level
    /// volatile_ids / volatile_classes sets from truth.json.
    /// </summary>
    public static bool LocatorUsesVolatileSignal(
        string locatorType,
        string locatorValue,
        IReadOnlySet<string>? extraVolatileIds    = null,
        IReadOnlySet<string>? extraVolatileClasses = null)
    {
        if (locatorType == "xpath")
        {
            // @class='X' — exact match
            foreach (Match m in Regex.Matches(locatorValue, @"@class\s*=\s*[""']([^""']+)[""']"))
            {
                var cls = m.Groups[1].Value;
                if (IsVolatileClass(cls) || extraVolatileClasses?.Contains(cls) == true)
                {
                    return true;
                }
            }

            // contains(@class,'X') / starts-with(@class,'X')
            // Flag if X is volatile, or if X is a prefix of any volatile class value.
            // A model using a prefix of a volatile class name (e.g. 'gallery__nav-btn--next'
            // as a prefix of 'gallery__nav-btn--next--b3c4d5') is selecting by volatile signal.
            foreach (Match m in Regex.Matches(locatorValue,
                @"(?:contains|starts-with)\s*\(\s*@class\s*,\s*[""']([^""']+)[""']\s*\)"))
            {
                var cls = m.Groups[1].Value;
                if (IsVolatileClass(cls) || extraVolatileClasses?.Contains(cls) == true)
                {
                    return true;
                }

                if (extraVolatileClasses?.Any(vc =>
                        vc.StartsWith(cls, StringComparison.OrdinalIgnoreCase)) == true)
                {
                    return true;
                }
            }

            // @id='X' — exact match
            foreach (Match m in Regex.Matches(locatorValue, @"@id\s*=\s*[""']([^""']+)[""']"))
            {
                var id = m.Groups[1].Value;
                if (IsVolatileId(id) || extraVolatileIds?.Contains(id) == true)
                {
                    return true;
                }
            }

            // contains(@id,'X') / starts-with(@id,'X')
            foreach (Match m in Regex.Matches(locatorValue,
                @"(?:contains|starts-with)\s*\(\s*@id\s*,\s*[""']([^""']+)[""']\s*\)"))
            {
                var id = m.Groups[1].Value;
                if (IsVolatileId(id) || extraVolatileIds?.Contains(id) == true)
                {
                    return true;
                }

                if (extraVolatileIds?.Any(vi =>
                        vi.StartsWith(id, StringComparison.OrdinalIgnoreCase)) == true)
                {
                    return true;
                }
            }

            // State attributes are inherently unstable (TESTBED_SPEC §3)
            if (Regex.IsMatch(locatorValue, @"@(value|checked|selected|disabled)\b"))
            {
                return true;
            }
        }
        else if (locatorType == "css")
        {
            // #id — exact match
            foreach (Match m in Regex.Matches(locatorValue, @"#([a-zA-Z0-9_-]+)"))
            {
                var id = m.Groups[1].Value;
                if (IsVolatileId(id) || extraVolatileIds?.Contains(id) == true)
                {
                    return true;
                }
            }

            // [id*="X"] / [id^="X"] — CSS substring/prefix id selectors
            foreach (Match m in Regex.Matches(locatorValue, @"\[id[\*\^]=[""']([^""']+)[""']\]"))
            {
                var id = m.Groups[1].Value;
                if (IsVolatileId(id) || extraVolatileIds?.Contains(id) == true)
                {
                    return true;
                }

                if (extraVolatileIds?.Any(vi =>
                        vi.StartsWith(id, StringComparison.OrdinalIgnoreCase)) == true)
                {
                    return true;
                }
            }

            // [id="X"] / [id='X'] / [id=X] — exact-match CSS attribute id selector (plain = operator)
            foreach (Match m in Regex.Matches(locatorValue,
                @"\[id\s*=\s*(?:[""']([^""']+)[""']|([a-zA-Z0-9_-]+))\]"))
            {
                var id = (m.Groups[1].Success ? m.Groups[1] : m.Groups[2]).Value;
                if (IsVolatileId(id) || extraVolatileIds?.Contains(id) == true)
                {
                    return true;
                }
            }

            // .class — exact class token match; also flag BEM bases of volatile classes
            foreach (Match m in Regex.Matches(locatorValue, @"\.([a-zA-Z][a-zA-Z0-9_-]*)"))
            {
                var cls = m.Groups[1].Value;
                if (IsVolatileClass(cls) || extraVolatileClasses?.Contains(cls) == true)
                {
                    return true;
                }

                if (IsBemBaseOfVolatile(cls, extraVolatileClasses))
                {
                    return true;
                }
            }

            // [class*="X"] / [class^="X"] — CSS substring/prefix class selectors
            foreach (Match m in Regex.Matches(locatorValue, @"\[class[\*\^]=[""']([^""']+)[""']\]"))
            {
                var cls = m.Groups[1].Value;
                if (IsVolatileClass(cls) || extraVolatileClasses?.Contains(cls) == true)
                {
                    return true;
                }

                if (extraVolatileClasses?.Any(vc =>
                        vc.StartsWith(cls, StringComparison.OrdinalIgnoreCase)) == true)
                {
                    return true;
                }
            }

            // [class~="X"] — CSS word-match class selector (equivalent to .X); same BEM rule
            foreach (Match m in Regex.Matches(locatorValue, @"\[class~=[""']([^""']+)[""']\]"))
            {
                var cls = m.Groups[1].Value;
                if (IsVolatileClass(cls) || extraVolatileClasses?.Contains(cls) == true)
                {
                    return true;
                }

                if (IsBemBaseOfVolatile(cls, extraVolatileClasses))
                {
                    return true;
                }
            }

            // [class="X"] / [class='X'] — exact-match CSS attribute class selector (plain = operator)
            foreach (Match m in Regex.Matches(locatorValue,
                @"\[class\s*=\s*[""']([^""']+)[""']\]"))
            {
                var cls = m.Groups[1].Value;
                if (IsVolatileClass(cls) || extraVolatileClasses?.Contains(cls) == true)
                {
                    return true;
                }

                if (IsBemBaseOfVolatile(cls, extraVolatileClasses))
                {
                    return true;
                }
            }

            // [class*=X] / [class^=X] / [class~=X] / [class=X] — unquoted operator forms
            foreach (Match m in Regex.Matches(locatorValue,
                @"\[class[\*\^\~\$\|]?\s*=\s*([a-zA-Z0-9_-]+)\]"))
            {
                var cls = m.Groups[1].Value;
                if (IsVolatileClass(cls) || extraVolatileClasses?.Contains(cls) == true)
                {
                    return true;
                }

                if (extraVolatileClasses?.Any(vc =>
                        vc.StartsWith(cls, StringComparison.OrdinalIgnoreCase)) == true)
                {
                    return true;
                }

                if (IsBemBaseOfVolatile(cls, extraVolatileClasses))
                {
                    return true;
                }
            }

            // [volatile-attr-name] — attribute selector where the NAME itself is a volatile
            // scope marker (Vue data-v-*, Angular _ngcontent-*, etc.). Checks the page-level
            // volatile_classes list only — the built-in regex targets class token values and
            // would produce false positives on stable names like "data-testid" or "aria-label".
            // Skips class/id which are covered by dedicated checks above.
            foreach (Match m in Regex.Matches(locatorValue,
                @"\[([a-zA-Z_][a-zA-Z0-9_-]*)(?:\]|[~\*\^\$\|]?=)"))
            {
                var attrName = m.Groups[1].Value;
                if (attrName is "class" or "id")
                {
                    continue;
                }

                if (extraVolatileClasses?.Contains(attrName) == true)
                {
                    return true;
                }
            }

            // CSS pseudo-classes and attribute selectors for state
            if (Regex.IsMatch(locatorValue, @":checked|:disabled|\[(value|checked|selected|disabled)[=\]]"))
            {
                return true;
            }
        }
        return false;
    }

    // -----------------------------------------------------------------------
    // Oracle element lookup
    // -----------------------------------------------------------------------

    /// <summary>
    /// Resolves the ground-truth element by its data-oracle-id anchor.
    /// Throws if the anchor is absent — a missing oracle is a corpus defect, not
    /// a measurable failure, so it must not be silently scored.
    /// </summary>
    public static async Task<IElementHandle> FindOracleElementAsync(IPage page, OracleRef oracle)
    {
        var el = await page.QuerySelectorAsync($"[data-oracle-id=\"{oracle.OracleId}\"]");
        if (el is null)
        {
            throw new InvalidOperationException(
                $"Oracle element [data-oracle-id='{oracle.OracleId}'] not found on page.");
        }

        return el;
    }

    // -----------------------------------------------------------------------
    // Locator resolution
    // -----------------------------------------------------------------------

    private static async Task<IReadOnlyList<IElementHandle>> ResolveAsync(
        IPage page, string locatorType, string locatorValue)
    {
        try
        {
            return locatorType switch
            {
                "xpath" => await page.QuerySelectorAllAsync($"xpath={locatorValue}"),
                "css"   => await page.QuerySelectorAllAsync(locatorValue),
                _       => Array.Empty<IElementHandle>(),
            };
        }
        catch
        {
            return Array.Empty<IElementHandle>();
        }
    }

    // -----------------------------------------------------------------------
    // Main evaluation entry point
    // -----------------------------------------------------------------------

    /// <summary>
    /// Scores one grounding event: resolves the locator against the live DOM and
    /// returns an EvalResult carrying all five predicate booleans, the overall
    /// success flag (their conjunction), and the failure_mode classification.
    /// Resolution only — never clicks or navigates.
    /// </summary>
    public static async Task<EvalResult> EvaluateLocatorAsync(
        IPage page,
        string locatorType,
        string locatorValue,
        IElementHandle oracleEl,
        IReadOnlyList<ElementData> rawWithAnchors,
        string oracleId,
        Func<string, bool> bundleContains,
        string? expectedStableSignal          = null,
        IReadOnlySet<string>? volatileIds     = null,
        IReadOnlySet<string>? volatileClasses = null,
        IReadOnlyList<string>? signalAttrs    = null)
    {
        // Bundle-aware: check actual value presence for class/id (value-level filtering
        // in B_noVolatile), not just attribute name membership. signalAttrs=[] → false.
        ElementData? rawOracleEl = rawWithAnchors.FirstOrDefault(
            el => el.Attrs.TryGetValue("data-oracle-id", out var aid) && aid == oracleId);
        bool stableSignalPresentInBundle = ComputeStableSignalPresence(
            signalAttrs, bundleContains, rawOracleEl, volatileIds, volatileClasses);

        // Predicate 1: unique match
        var resolved = await ResolveAsync(page, locatorType, locatorValue);
        bool uniqueMatch = resolved.Count == 1;

        // Predicate 2: matches oracle — compare via data-oracle-id on the raw DOM
        bool matchesOracle = false;
        if (uniqueMatch)
        {
            var resolvedOid = await page.EvaluateAsync<string>(
                "(el) => el.getAttribute('data-oracle-id') ?? ''", resolved[0]);
            var oracleOid = await page.EvaluateAsync<string>(
                "(el) => el.getAttribute('data-oracle-id') ?? ''", oracleEl);
            matchesOracle = !string.IsNullOrEmpty(resolvedOid) && resolvedOid == oracleOid;
        }

        // Predicate 3: non-volatile (regex patterns + page-level volatile_labels from truth.json)
        bool nonVolatile = !LocatorUsesVolatileSignal(locatorType, locatorValue, volatileIds, volatileClasses);

        // Predicate 4: non-positional
        bool nonPositional = LocatorIsNonPositional(locatorType, locatorValue);

        // Predicate 5: stable signal present in this bundle's observation
        bool success = uniqueMatch && matchesOracle && nonVolatile && nonPositional
                       && stableSignalPresentInBundle;

        // output_format_unreachable: model emitted XPath despite CSS-only instruction,
        // and the oracle element is inside a shadow root (where XPath can't reach).
        // Expected to fire rarely now that the prompt enforces CSS; kept to detect non-compliance.
        bool oracleIsInShadow = !success && locatorType == "xpath"
            && await page.EvaluateAsync<bool>("(el) => el.getRootNode() instanceof ShadowRoot", oracleEl);

        // Classification per TESTBED_SPEC §4 (priority updated — defect fix D4):
        //   stableSignalPresentInBundle=false    → observation_lacked_stable_signal  (wins over all)
        //   locatorType=xpath + oracle in shadow → output_format_unreachable
        //   stableSignalPresentInBundle=true     → model_grabbed_brittle_signal
        // lacked wins over output_format_unreachable for the same reason lacked wins over grabbed:
        // the classification names the root cause (no stable signal), not the locator's secondary property.
        string? failureMode = success ? null
            : !stableSignalPresentInBundle  ? "observation_lacked_stable_signal"
            : oracleIsInShadow              ? "output_format_unreachable"
                                            : "model_grabbed_brittle_signal";

        return new EvalResult(
            Success: success,
            FailureMode: failureMode,
            PredicateUniqueMatch: uniqueMatch,
            PredicateMatchesOracle: matchesOracle,
            PredicateNonVolatile: nonVolatile,
            PredicateNonPositional: nonPositional,
            StableSignalPresentInBundle: stableSignalPresentInBundle
        );
    }
}
