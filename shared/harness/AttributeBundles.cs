using BoundedAgents.Shared.Oracle;

namespace BoundedAgents.Shared.Harness;

/// <summary>
/// Attribute bundles (Axis A): the named projection sets (B_full … B_minimalCore) and the
/// per-element filters that turn a raw DOM element into a bundle-projected observation element.
/// </summary>
public static class AttributeBundles
{
    // -----------------------------------------------------------------------
    // Attribute categories — per experiments/docs/SCHEMA.md §2 (authoritative)
    // -----------------------------------------------------------------------

    // Identity: id, data-testid
    private static readonly IReadOnlySet<string> _identity = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "id", "data-testid" };

    // Semantic-textual: visible text (handled via bundle.Contains("text")),
    // aria-label, placeholder, name
    // Note: "text" is a virtual key — not in element.Attrs; controls text inclusion
    private static readonly IReadOnlySet<string> _semanticTextual = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "text", "aria-label", "placeholder", "name" };

    // Accessibility: role + all other aria-* (NOT aria-label — that is semantic-textual)
    private static readonly IReadOnlySet<string> _accessibility = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "role", "aria-expanded", "aria-selected", "aria-checked", "aria-disabled",
          "aria-required", "aria-controls", "aria-haspopup", "aria-level", "tabindex",
          "aria-hidden", "aria-live", "aria-labelledby", "aria-describedby" };

    // Structural (HTML attrs, not computed metadata)
    private static readonly IReadOnlySet<string> _structural = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "class", "src" };

    // State: inherently unstable at runtime — present in B_full as available-decoy
    // signals. A locator keying on these fails the non-volatile predicate (§3).
    private static readonly IReadOnlySet<string> _state = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "disabled", "checked", "selected", "value" };

    // Uncategorised but present in B_full: href, type, for, alt, title
    private static readonly IReadOnlySet<string> _uncategorised = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "href", "type", "for", "alt", "title" };

    // -----------------------------------------------------------------------
    // Bundle definitions — Axis A (§2.2)
    // -----------------------------------------------------------------------

    // B_full: all categories + uncategorised
    public static readonly IReadOnlySet<string> BundleFull =
        new HashSet<string>(
            _identity.Concat(_semanticTextual).Concat(_accessibility)
                     .Concat(_structural).Concat(_state).Concat(_uncategorised),
            StringComparer.OrdinalIgnoreCase);

    // B_noVolatile: B_full minus volatile ids/classes from volatility_labels.
    // Cannot be a static set — requires runtime volatile label filtering.
    // Handled in ApplyBundleNoVolatile.

    // B_noState: B_full minus state attrs {disabled, checked, selected, value}
    public static readonly IReadOnlySet<string> BundleNoState =
        new HashSet<string>(
            BundleFull.Except(_state, StringComparer.OrdinalIgnoreCase),
            StringComparer.OrdinalIgnoreCase);

    // B_noSemantic: B_full minus semantic-textual {text, aria-label, placeholder, name}
    public static readonly IReadOnlySet<string> BundleNoSemantic =
        new HashSet<string>(
            BundleFull.Except(_semanticTextual, StringComparer.OrdinalIgnoreCase),
            StringComparer.OrdinalIgnoreCase);

    // B_identityCore: tag + id + data-testid only (experiments/docs/SCHEMA.md §2)
    // tag is always added by encoders; this set controls attr filtering only
    public static readonly IReadOnlySet<string> BundleIdentityCore =
        new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            { "id", "data-testid" };

    // B_minimalCore: tag only — empty attr set (no text, no attrs)
    public static readonly IReadOnlySet<string> BundleMinimalCore =
        new HashSet<string>(StringComparer.OrdinalIgnoreCase);

    // B_full_minus_aria (single ablation): B_full minus every attribute whose name
    // starts with "aria-" (the aria-* of the Accessibility category and aria-label from
    // Semantic-textual); role and tabindex stay. Derived from BundleFull, not a hand list.
    public static readonly IReadOnlySet<string> BundleFullMinusAria =
        new HashSet<string>(
            BundleFull.Where(a => !a.StartsWith("aria-", StringComparison.OrdinalIgnoreCase)),
            StringComparer.OrdinalIgnoreCase);

    /// <summary>
    /// The attribute categories behind the bundle definitions (read-only view of the private
    /// sets above), for composition reports. "uncategorised" = present in B_full only.
    /// </summary>
    public static readonly IReadOnlyDictionary<string, IReadOnlySet<string>> AttributeCategories =
        new Dictionary<string, IReadOnlySet<string>>
        {
            ["identity"] = _identity,
            ["semantic_textual"] = _semanticTextual,
            ["accessibility"] = _accessibility,
            ["structural"] = _structural,
            ["state"] = _state,
            ["uncategorised"] = _uncategorised,
        };

    private static readonly IReadOnlyDictionary<string, IReadOnlySet<string>> _bundles =
        new Dictionary<string, IReadOnlySet<string>>(StringComparer.OrdinalIgnoreCase)
        {
            ["B_full"] = BundleFull,
            ["B_noState"] = BundleNoState,
            ["B_noSemantic"] = BundleNoSemantic,
            ["B_identityCore"] = BundleIdentityCore,
            ["B_minimalCore"] = BundleMinimalCore,
            // B_noVolatileConsistent: listed here only so ResolveBundleSetForSignalCheck returns
            // BundleFull for condition 5 (value-level filtering, like B_noVolatile); its
            // observations are built by ApplyBundleNoVolatileConsistent (Observation.cs).
            ["B_noVolatileConsistent"] = BundleFull,
            // Single ablations (B_full minus ONE class). The two value-level ones
            // (volatile class tokens / volatile ids, predicate-consistent rule) map to BundleFull
            // only for condition 5, like B_noVolatileConsistent; their observations are built by
            // ApplyBundleMinusVolatileClass / ApplyBundleMinusVolatileId (Observation.cs).
            ["B_full_minus_volClass"] = BundleFull,
            ["B_full_minus_volId"] = BundleFull,
            // Same attribute set as B_noState (identical observations by construction).
            ["B_full_minus_state"] = BundleNoState,
            ["B_full_minus_aria"] = BundleFullMinusAria,
            // B_noVolatile and B_playwrightMCP are not in this dict:
            // B_noVolatile uses ApplyBundleNoVolatile (dynamic),
            // B_playwrightMCP uses BuildAriaObservationAsync (separate ARIA path).
        };

    /// <summary>
    /// Returns the static attribute set for a named bundle.
    /// Throws for B_noVolatile and B_playwrightMCP, which are computed per page
    /// rather than fixed — reaching here with those names is a caller bug.
    /// </summary>
    public static IReadOnlySet<string> GetBundle(string name)
    {
        if (_bundles.TryGetValue(name, out var b))
        {
            return b;
        }
        // B_noVolatile and B_playwrightMCP are handled specially — callers must not
        // reach GetBundle for them; throw to surface the mistake clearly.
        throw new ArgumentException(
            $"Unknown or special bundle '{name}'. " +
            $"Static bundles: {string.Join(", ", _bundles.Keys)}. " +
            $"B_noVolatile and B_playwrightMCP require their own code paths.");
    }

    /// <summary>
    /// Resolves the attribute-set used for the out-of-bundle / stable-signal audit.
    /// B_noVolatile and B_playwrightMCP have no static bundle entry (they use dynamic
    /// code paths), yet the audit needs the FULL attribute surface to judge whether the
    /// model reached for a signal outside the intended bundle — so both map to BundleFull.
    /// </summary>
    public static IReadOnlySet<string> ResolveBundleSetForSignalCheck(string bundle) =>
        bundle.Equals("B_noVolatile", StringComparison.OrdinalIgnoreCase) ||
        bundle.Equals("B_playwrightMCP", StringComparison.OrdinalIgnoreCase)
            ? BundleFull
            : GetBundle(bundle);

    // -----------------------------------------------------------------------
    // Bundle application — Axis A
    // -----------------------------------------------------------------------

    /// <summary>
    /// Projects one element onto a bundle, keeping only attributes the bundle admits.
    /// Returns a new ElementData; the input is not mutated. This is the D → O step
    /// for the static bundles (Axis A).
    /// </summary>
    public static ElementData ApplyBundle(ElementData element, IReadOnlySet<string> bundle)
    {
        var filteredAttrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var (k, v) in element.Attrs)
        {
            if (bundle.Contains(k) && !string.IsNullOrEmpty(v))
            {
                filteredAttrs[k] = v;
            }
        }

        var text = bundle.Contains("text") ? element.Text : string.Empty;
        return new ElementData(element.Tag, text, filteredAttrs, element.IsInShadowRoot);
    }

    /// <summary>
    /// B_noVolatile variant: applies B_full membership but strips id values that
    /// appear in volatile_ids and filters out volatile class tokens.
    /// </summary>
    public static ElementData ApplyBundleNoVolatile(
        ElementData element,
        IReadOnlySet<string>? volatileIds,
        IReadOnlySet<string>? volatileClasses)
    {
        var filteredAttrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var (k, v) in element.Attrs)
        {
            if (!BundleFull.Contains(k) || string.IsNullOrEmpty(v))
            {
                continue;
            }

            if (k.Equals("id", StringComparison.OrdinalIgnoreCase))
            {
                if (volatileIds?.Contains(v) == true)
                {
                    continue; // strip volatile id
                }

                filteredAttrs[k] = v;
                continue;
            }

            if (k.Equals("class", StringComparison.OrdinalIgnoreCase))
            {
                var stable = v.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                              .Where(c => volatileClasses?.Contains(c) != true
                                       && !Oracle.Oracle.IsBemBaseOfVolatile(c, volatileClasses))
                              .ToArray();
                if (stable.Length > 0)
                {
                    filteredAttrs[k] = string.Join(" ", stable);
                }
                // else all tokens are volatile or BEM bases of volatile — drop the attribute
                continue;
            }

            filteredAttrs[k] = v;
        }

        var text = element.Text; // B_noVolatile retains semantic-textual
        return new ElementData(element.Tag, text, filteredAttrs, element.IsInShadowRoot);
    }

    /// <summary>
    /// B_noVolatileConsistent (sensitivity bundle): B_full membership, but strips
    /// every id value and class token that the predicate's own volatile check
    /// (Oracle.LocatorUsesVolatileSignal) would flag — the truth.json-labelled values, BEM
    /// bases of labelled classes, and values matching the predicate's structural regexes.
    /// The predicate function itself is called (no copy of its regexes) on the valid-CSS
    /// exact-token locator forms `[class~="tok"]` and `[id="id"]` (see PredicateFlags*).
    /// B_noVolatile (ApplyBundleNoVolatile) is a separate bundle with its own label-based rule.
    /// </summary>
    public static ElementData ApplyBundleNoVolatileConsistent(
        ElementData element,
        IReadOnlySet<string>? volatileIds,
        IReadOnlySet<string>? volatileClasses)
    {
        var filteredAttrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var (k, v) in element.Attrs)
        {
            if (!BundleFull.Contains(k) || string.IsNullOrEmpty(v))
            {
                continue;
            }

            if (k.Equals("id", StringComparison.OrdinalIgnoreCase))
            {
                if (PredicateFlagsId(v, volatileIds, volatileClasses))
                {
                    continue; // strip id the predicate treats as volatile
                }

                filteredAttrs[k] = v;
                continue;
            }

            if (k.Equals("class", StringComparison.OrdinalIgnoreCase))
            {
                var stable = v.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                              .Where(c => !PredicateFlagsClassToken(c, volatileIds, volatileClasses))
                              .ToArray();
                if (stable.Length > 0)
                {
                    filteredAttrs[k] = string.Join(" ", stable);
                }
                // else every token is one the predicate treats as volatile — drop the attribute
                continue;
            }

            filteredAttrs[k] = v;
        }

        var text = element.Text; // retains semantic-textual, as B_noVolatile
        return new ElementData(element.Tag, text, filteredAttrs, element.IsInShadowRoot);
    }

    /// <summary>
    /// B_full_minus_volClass (single ablation): B_full, minus only the class tokens
    /// the predicate flags (PredicateFlagsClassToken — the rule of B_noVolatileConsistent);
    /// id values are kept.
    /// </summary>
    public static ElementData ApplyBundleMinusVolatileClass(
        ElementData element,
        IReadOnlySet<string>? volatileIds,
        IReadOnlySet<string>? volatileClasses) =>
        ApplyPredicateConsistentStrip(element, volatileIds, volatileClasses, stripIds: false, stripClasses: true);

    /// <summary>
    /// B_full_minus_volId (single ablation): B_full, minus only the id values the
    /// predicate flags (PredicateFlagsId — the rule of B_noVolatileConsistent); class tokens
    /// are kept.
    /// </summary>
    public static ElementData ApplyBundleMinusVolatileId(
        ElementData element,
        IReadOnlySet<string>? volatileIds,
        IReadOnlySet<string>? volatileClasses) =>
        ApplyPredicateConsistentStrip(element, volatileIds, volatileClasses, stripIds: true, stripClasses: false);

    private static ElementData ApplyPredicateConsistentStrip(
        ElementData element,
        IReadOnlySet<string>? volatileIds,
        IReadOnlySet<string>? volatileClasses,
        bool stripIds,
        bool stripClasses)
    {
        var filteredAttrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        foreach (var (k, v) in element.Attrs)
        {
            if (!BundleFull.Contains(k) || string.IsNullOrEmpty(v))
            {
                continue;
            }

            if (stripIds && k.Equals("id", StringComparison.OrdinalIgnoreCase))
            {
                if (!PredicateFlagsId(v, volatileIds, volatileClasses))
                {
                    filteredAttrs[k] = v;
                }
                continue;
            }

            if (stripClasses && k.Equals("class", StringComparison.OrdinalIgnoreCase))
            {
                var stable = v.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                              .Where(c => !PredicateFlagsClassToken(c, volatileIds, volatileClasses))
                              .ToArray();
                if (stable.Length > 0)
                {
                    filteredAttrs[k] = string.Join(" ", stable);
                }
                continue;
            }

            filteredAttrs[k] = v;
        }

        return new ElementData(element.Tag, element.Text, filteredAttrs, element.IsInShadowRoot);
    }

    /// <summary>
    /// True when the predicate (Oracle.LocatorUsesVolatileSignal) flags the locator
    /// `[class~="tok"]` — the valid-CSS exact-token selector for this class token. The
    /// attribute form is used instead of `.tok` because `.tok` is not valid CSS for tokens
    /// with CSS-special characters (`:`, `/`, `.`, `[`, `]`, …) and the predicate's `.class`
    /// regex would capture only a fragment of such a token. For plain identifier tokens the
    /// predicate applies the same three checks to `.tok` and `[class~="tok"]` (structural
    /// regex, truth.json list, BEM base), so the verdict is identical.
    /// </summary>
    public static bool PredicateFlagsClassToken(
        string token, IReadOnlySet<string>? volatileIds, IReadOnlySet<string>? volatileClasses) =>
        Oracle.Oracle.LocatorUsesVolatileSignal("css", QuotedAttrSelector("class~", token), volatileIds, volatileClasses);

    /// <summary>
    /// True when the predicate (Oracle.LocatorUsesVolatileSignal) flags the locator
    /// `[id="id"]` — the valid-CSS exact selector for this id (for plain identifiers the
    /// predicate applies the same checks to `#id`: structural regex + truth.json list).
    /// </summary>
    public static bool PredicateFlagsId(
        string id, IReadOnlySet<string>? volatileIds, IReadOnlySet<string>? volatileClasses) =>
        Oracle.Oracle.LocatorUsesVolatileSignal("css", QuotedAttrSelector("id", id), volatileIds, volatileClasses);

    // `[name<op>="value"]`, or single quotes when the value contains a double quote.
    private static string QuotedAttrSelector(string nameAndOp, string value) =>
        value.Contains('"') ? $"[{nameAndOp}='{value}']" : $"[{nameAndOp}=\"{value}\"]";

    // -----------------------------------------------------------------------
    // Oracle-anchor stripping (TESTBED_SPEC §3)
    // -----------------------------------------------------------------------

    /// <summary>
    /// Remove every data-oracle-* attribute from all elements before encoding.
    /// Must run on every DOM-walk path. Oracle anchors must add zero tokens.
    /// The ARIA snapshot path (F4) is verified separately in BuildAriaObservationAsync.
    /// </summary>
    public static IReadOnlyList<ElementData> StripOracleAnchors(IReadOnlyList<ElementData> elements)
    {
        var result = new List<ElementData>(elements.Count);
        foreach (var el in elements)
        {
            var cleanAttrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var (k, v) in el.Attrs)
            {
                if (!k.StartsWith("data-oracle-", StringComparison.OrdinalIgnoreCase))
                {
                    cleanAttrs[k] = v;
                }
            }

            result.Add(new ElementData(el.Tag, el.Text, cleanAttrs, el.IsInShadowRoot));
        }
        return result;
    }

}
