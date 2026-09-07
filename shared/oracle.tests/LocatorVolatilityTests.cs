using BoundedAgents.Shared.Oracle;
using BoundedAgents.Shared.Harness;
using Xunit;
using static BoundedAgents.Shared.Oracle.Oracle;

namespace BoundedAgents.Shared.Oracle.Tests;

/// <summary>
/// Unit tests for Oracle.LocatorUsesVolatileSignal.
///
/// Volatility labels are taken verbatim from shared/testbed/pages/page_01.truth.json
/// so regressions surface immediately as models are added.
///
/// expectedVolatile = true  → locator IS volatile → PredicateNonVolatile = false → grounding FAIL
/// expectedVolatile = false → locator is non-volatile → PredicateNonVolatile = true
/// </summary>
public class LocatorVolatilityTests
{
    // page_01 volatility_labels (shared/testbed/pages/page_01.truth.json)
    private static readonly IReadOnlySet<string> VolatileIds =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "price-badge-a1b2c3", "stock-indicator-9f8e7d", "gallery-next-f7a9e1"
        };

    private static readonly IReadOnlySet<string> VolatileClasses =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "data-v-7ba5bd90", "data-v-2c3d4e5f", "data-v-a1b2c3d4", "data-v-f5e4d3c2",
            "data-v-9b8a7c6d", "data-v-c1d2e3f4", "data-v-8b7c6d5e", "data-v-1a2b3c4d",
            "pkg-select--a9b8c7", "gallery__nav-btn--next--b3c4d5", "price-tag--vue-d4e5f6"
        };

    private static bool IsVolatile(string locatorType, string locatorValue) =>
        LocatorUsesVolatileSignal(locatorType, locatorValue, VolatileIds, VolatileClasses);

    // ───────────────────────────────────────────────────────────────────────
    // XPath — @class exact
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void XPath_ClassExact_Stable_Pass() =>
        Assert.False(IsVolatile("xpath", "//button[@class='add-to-cart-btn']"));

    [Fact] public void XPath_ClassExact_PageLabelVolatile_Fail() =>
        Assert.True(IsVolatile("xpath", "//button[@class='pkg-select--a9b8c7']"));

    [Fact] public void XPath_ClassExact_RegexReactHash_Fail() =>
        Assert.True(IsVolatile("xpath", "//div[@class='css-1x2y3z']"));

    [Fact] public void XPath_ClassExact_RegexVueScopeAndPageLabel_Fail() =>
        Assert.True(IsVolatile("xpath", "//div[@class='data-v-7ba5bd90']"));

    [Fact] public void XPath_ClassExact_Stable_Breadcrumb_Pass() =>
        Assert.False(IsVolatile("xpath", "//nav[@class='breadcrumb']"));

    // ───────────────────────────────────────────────────────────────────────
    // XPath — contains(@class,...)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void XPath_ContainsClass_PrefixOfVolatilePageLabel_Fail() =>
        Assert.True(IsVolatile("xpath", "//button[contains(@class,'gallery__nav-btn--next')]"));

    [Fact] public void XPath_ContainsClass_ExactVolatilePageLabel_Fail() =>
        Assert.True(IsVolatile("xpath", "//button[contains(@class,'gallery__nav-btn--next--b3c4d5')]"));

    [Fact] public void XPath_ContainsClass_PrefixOfVolatile_pkg_Fail() =>
        Assert.True(IsVolatile("xpath", "//div[contains(@class,'pkg-select')]"));

    [Fact] public void XPath_ContainsClass_Stable_Pass() =>
        Assert.False(IsVolatile("xpath", "//nav[contains(@class,'breadcrumb')]"));

    // ───────────────────────────────────────────────────────────────────────
    // XPath — starts-with(@class,...)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void XPath_StartsWithClass_PrefixOfVolatile_Fail() =>
        Assert.True(IsVolatile("xpath", "//button[starts-with(@class,'gallery__nav-btn--next')]"));

    [Fact] public void XPath_StartsWithClass_Stable_Pass() =>
        Assert.False(IsVolatile("xpath", "//input[starts-with(@class,'qty-input')]"));

    // ───────────────────────────────────────────────────────────────────────
    // XPath — @id exact
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void XPath_IdExact_PageLabelVolatile_Fail() =>
        Assert.True(IsVolatile("xpath", "//button[@id='gallery-next-f7a9e1']"));

    [Fact] public void XPath_IdExact_PageLabelVolatile2_Fail() =>
        Assert.True(IsVolatile("xpath", "//span[@id='price-badge-a1b2c3']"));

    // React internal ID pattern: ^:?[rR][a-zA-Z0-9]+$
    [Fact] public void XPath_IdExact_RegexReactInternal_Fail() =>
        Assert.True(IsVolatile("xpath", "//span[@id='rABCDE']"));

    // Auto-generated ID pattern: ^[a-z]+-[0-9]{4,}$
    [Fact] public void XPath_IdExact_RegexAutoPattern_Fail() =>
        Assert.True(IsVolatile("xpath", "//li[@id='item-12345']"));

    [Fact] public void XPath_IdExact_Stable_Pass() =>
        Assert.False(IsVolatile("xpath", "//button[@id='write-review-btn']"));

    // ───────────────────────────────────────────────────────────────────────
    // XPath — contains(@id,...) / starts-with(@id,...)
    // ───────────────────────────────────────────────────────────────────────

    // "gallery-next" is a prefix of volatile id "gallery-next-f7a9e1"
    [Fact] public void XPath_ContainsId_PrefixOfVolatile_Fail() =>
        Assert.True(IsVolatile("xpath", "//button[contains(@id,'gallery-next')]"));

    [Fact] public void XPath_ContainsId_Stable_Pass() =>
        Assert.False(IsVolatile("xpath", "//input[contains(@id,'qty')]"));

    // ───────────────────────────────────────────────────────────────────────
    // XPath — state attributes (always volatile per TESTBED_SPEC §3)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void XPath_StateAttr_Value_Fail() =>
        Assert.True(IsVolatile("xpath", "//input[@value='5']"));

    [Fact] public void XPath_StateAttr_Checked_Fail() =>
        Assert.True(IsVolatile("xpath", "//input[@checked='true']"));

    [Fact] public void XPath_StateAttr_Selected_Fail() =>
        Assert.True(IsVolatile("xpath", "//option[@selected='selected']"));

    [Fact] public void XPath_StateAttr_Disabled_Fail() =>
        Assert.True(IsVolatile("xpath", "//button[@disabled='disabled']"));

    // ───────────────────────────────────────────────────────────────────────
    // XPath — compound selectors (stable + volatile must still fail)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void XPath_Compound_StableAndVolatileClass_Fail() =>
        Assert.True(IsVolatile("xpath",
            "//button[@data-testid='add-to-cart-btn' and @class='pkg-select--a9b8c7']"));

    [Fact] public void XPath_Compound_StableAndContainsVolatileClass_Fail() =>
        Assert.True(IsVolatile("xpath",
            "//button[@aria-label='Add to cart'][contains(@class,'gallery__nav-btn--next')]"));

    [Fact] public void XPath_Compound_AllStable_Pass() =>
        Assert.False(IsVolatile("xpath",
            "//button[@data-testid='add-to-cart-btn'][@aria-label='Add to cart']"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — #id
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void Css_IdHash_Stable_Pass() =>
        Assert.False(IsVolatile("css", "#write-review-btn"));

    [Fact] public void Css_IdHash_PageLabelVolatile_Fail() =>
        Assert.True(IsVolatile("css", "#gallery-next-f7a9e1"));

    [Fact] public void Css_IdHash_PageLabelVolatile2_Fail() =>
        Assert.True(IsVolatile("css", "#price-badge-a1b2c3"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — .class
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void Css_ClassDot_Stable_Pass() =>
        Assert.False(IsVolatile("css", ".breadcrumb"));

    [Fact] public void Css_ClassDot_PageLabelVolatile_Fail() =>
        Assert.True(IsVolatile("css", ".pkg-select--a9b8c7"));

    [Fact] public void Css_ClassDot_RegexReactHash_Fail() =>
        Assert.True(IsVolatile("css", ".css-1x2y3z"));

    [Fact] public void Css_ClassDot_PageLabelVolatile2_Fail() =>
        Assert.True(IsVolatile("css", ".gallery__nav-btn--next--b3c4d5"));

    [Fact] public void Css_ClassDot_RegexVueScope_Fail() =>
        Assert.True(IsVolatile("css", ".data-v-7ba5bd90"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — [class*=] / [class^=] (substring and prefix selectors)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void Css_ClassSubstring_PrefixOfVolatile_Fail() =>
        Assert.True(IsVolatile("css", "[class*=\"gallery__nav-btn--next\"]"));

    [Fact] public void Css_ClassPrefix_PrefixOfVolatile_Fail() =>
        Assert.True(IsVolatile("css", "[class^=\"gallery__nav-btn--next\"]"));

    [Fact] public void Css_ClassPrefix_PkgSelectPrefix_Fail() =>
        Assert.True(IsVolatile("css", "[class^=\"pkg-select\"]"));

    [Fact] public void Css_ClassPrefix_Stable_Pass() =>
        Assert.False(IsVolatile("css", "[class^=\"btn\"]"));

    [Fact] public void Css_ClassSubstring_Stable_Pass() =>
        Assert.False(IsVolatile("css", "[class*=\"breadcrumb\"]"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — [class~=] (word-match class selector, equivalent to .X)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void Css_ClassWordMatch_VolatileVueScope_Fail() =>
        Assert.True(IsVolatile("css", "[class~=\"data-v-7ba5bd90\"]"));

    [Fact] public void Css_ClassWordMatch_PageLabelVolatile_Fail() =>
        Assert.True(IsVolatile("css", "[class~=\"pkg-select--a9b8c7\"]"));

    [Fact] public void Css_ClassWordMatch_Stable_Pass() =>
        Assert.False(IsVolatile("css", "[class~=\"breadcrumb\"]"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — BEM-base-of-volatile (.class and [class~=])
    // A class token that is a direct BEM prefix (via -- or __) of a volatile class
    // must be treated as volatile — locating by the base grabs the volatile element.
    // ───────────────────────────────────────────────────────────────────────

    // "gallery__nav-btn--next" is a direct BEM modifier base of "gallery__nav-btn--next--b3c4d5"
    [Fact] public void Css_ClassDot_BemModifierBaseOfVolatile_Fail() =>
        Assert.True(IsVolatile("css", ".gallery__nav-btn--next"));

    // "gallery__nav-btn" is the BEM block base — also a prefix of the volatile class via --
    [Fact] public void Css_ClassDot_BemBlockBaseOfVolatile_Fail() =>
        Assert.True(IsVolatile("css", ".gallery__nav-btn"));

    // [class~=] word-match is equivalent to .class — same BEM base rule applies
    [Fact] public void Css_ClassWordMatch_BemBaseOfVolatile_Fail() =>
        Assert.True(IsVolatile("css", "[class~=\"gallery__nav-btn--next\"]"));

    // A stable class that shares no BEM-prefix relationship with any volatile class must pass
    [Fact] public void Css_ClassDot_StableNotABemBase_Pass() =>
        Assert.False(IsVolatile("css", ".add-to-cart-btn"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — [id*=] / [id^=]
    // ───────────────────────────────────────────────────────────────────────

    // "gallery-next" is a prefix of volatile id "gallery-next-f7a9e1"
    [Fact] public void Css_IdSubstring_PrefixOfVolatile_Fail() =>
        Assert.True(IsVolatile("css", "[id*=\"gallery-next\"]"));

    [Fact] public void Css_IdPrefix_PrefixOfVolatile_Fail() =>
        Assert.True(IsVolatile("css", "[id^=\"gallery-next\"]"));

    [Fact] public void Css_IdSubstring_Stable_Pass() =>
        Assert.False(IsVolatile("css", "[id*=\"qty\"]"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — [volatile-attr-name] bare attribute presence selector
    // The attribute NAME itself is a volatile scope marker (e.g. Vue data-v-*).
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void Css_VolatileAttrName_BarePresence_Fail() =>
        Assert.True(IsVolatile("css", "[data-v-7ba5bd90]"));

    [Fact] public void Css_VolatileAttrName_WithTagPrefix_Fail() =>
        Assert.True(IsVolatile("css", "button[data-v-7ba5bd90]"));

    [Fact] public void Css_StableAttrName_DataTestid_Pass() =>
        Assert.False(IsVolatile("css", "[data-testid=\"add-to-cart-btn\"]"));

    [Fact] public void Css_StableAttrName_AriaLabel_Pass() =>
        Assert.False(IsVolatile("css", "[aria-label=\"Submit\"]"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — state (always volatile per TESTBED_SPEC §3)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void Css_StateChecked_Fail() =>
        Assert.True(IsVolatile("css", "input:checked"));

    [Fact] public void Css_StateDisabled_Fail() =>
        Assert.True(IsVolatile("css", "button:disabled"));

    [Fact] public void Css_StateValueAttr_Fail() =>
        Assert.True(IsVolatile("css", "[value=\"5\"]"));

    [Fact] public void Css_StateSelectedAttr_Fail() =>
        Assert.True(IsVolatile("css", "[selected]"));

    // type is structural, not state — must not be flagged
    [Fact] public void Css_TypeAttr_NotState_Pass() =>
        Assert.False(IsVolatile("css", "button[type=\"submit\"]"));

    // ───────────────────────────────────────────────────────────────────────
    // CSS — compound (stable + volatile must still fail)
    // ───────────────────────────────────────────────────────────────────────

    [Fact] public void Css_Compound_StableAndVolatileClass_Fail() =>
        Assert.True(IsVolatile("css",
            "button[data-testid=\"add-to-cart-btn\"].pkg-select--a9b8c7"));

    [Fact] public void Css_Compound_AllStable_Pass() =>
        Assert.False(IsVolatile("css",
            "button[data-testid=\"add-to-cart-btn\"][aria-label=\"Add to cart\"]"));
}

/// <summary>
/// Unit tests for Oracle.ComputeStableSignalPresence — the bundle-aware signal check.
/// All tests are deterministic and require no Playwright.
///
/// Covers the invariants:
///   - NONE targets (signal_attrs=[]) → always false
///   - class signal, all volatile tokens → false
///   - class signal, all BEM-base-of-volatile tokens → false (new BEM fix)
///   - class signal, at least one stable token → true
///   - aria-label signal, B_noSemantic (bundleContains=false) → false
///   - aria-label signal, B_noVolatile (bundleContains=true) → true
///   - id signal, volatile id → false
///   - id signal, stable id → true
/// </summary>
public class SignalPresenceTests
{
    private static readonly IReadOnlySet<string> VolatileIds =
        new HashSet<string>(StringComparer.Ordinal) { "price-badge-a1b2c3", "gallery-next-f7a9e1" };

    private static readonly IReadOnlySet<string> VolatileClasses =
        new HashSet<string>(StringComparer.Ordinal)
        { "pkg-select--a9b8c7", "gallery__nav-btn--next--b3c4d5" };

    private static ElementData El(string tag, Dictionary<string, string> attrs) =>
        new(tag, "", attrs);

    private static bool Compute(
        IReadOnlyList<string> signalAttrs,
        Func<string, bool> bundleContains,
        ElementData? oracleEl) =>
        ComputeStableSignalPresence(signalAttrs, bundleContains, oracleEl, VolatileIds, VolatileClasses);

    // NONE target: signal_attrs=[] → always false
    [Fact] public void NoneTarget_AlwaysFalse() =>
        Assert.False(Compute([], _ => true,
            El("button", new() { ["data-oracle-id"] = "t10", ["class"] = "gallery__nav-btn--next--b3c4d5" })));

    // class signal, all tokens are volatile → false
    [Fact] public void ClassSignal_AllVolatile_False() =>
        Assert.False(Compute(["class"], _ => true,
            El("button", new() { ["data-oracle-id"] = "t10", ["class"] = "gallery__nav-btn--next--b3c4d5" })));

    // class signal, all tokens are BEM bases of volatile → false
    [Fact] public void ClassSignal_AllBemBaseOfVolatile_False() =>
        Assert.False(Compute(["class"], _ => true,
            El("button", new() { ["data-oracle-id"] = "t10", ["class"] = "gallery__nav-btn--next gallery__nav-btn" })));

    // class signal, one stable token alongside volatile → true
    [Fact] public void ClassSignal_OneStableToken_True() =>
        Assert.True(Compute(["class"], _ => true,
            El("button", new() { ["data-oracle-id"] = "t01", ["class"] = "add-to-cart-btn pkg-select--a9b8c7" })));

    // aria-label signal, B_noSemantic excludes it → false
    [Fact] public void AriaLabel_BundleExcludes_False() =>
        Assert.False(Compute(["aria-label"], _ => false,
            El("button", new() { ["data-oracle-id"] = "t03", ["aria-label"] = "Add to cart" })));

    // aria-label signal, B_noVolatile includes it (no value-level filter) → true
    [Fact] public void AriaLabel_BundleIncludes_True() =>
        Assert.True(Compute(["aria-label"], _ => true,
            El("button", new() { ["data-oracle-id"] = "t03", ["aria-label"] = "Add to cart" })));

    // id signal, volatile id value → false
    [Fact] public void IdSignal_VolatileId_False() =>
        Assert.False(Compute(["id"], _ => true,
            El("span", new() { ["data-oracle-id"] = "t05", ["id"] = "price-badge-a1b2c3" })));

    // id signal, stable id value → true
    [Fact] public void IdSignal_StableId_True() =>
        Assert.True(Compute(["id"], _ => true,
            El("button", new() { ["data-oracle-id"] = "t01", ["id"] = "write-review-btn" })));

    // oracle element not found (null) → false regardless of signal_attrs
    [Fact] public void NullOracleEl_AlwaysFalse() =>
        Assert.False(Compute(["aria-label"], _ => true, null));
}

/// <summary>
/// §5c BEM dedup parity: Oracle.IsBemBaseOfVolatile (the method Observation delegates
/// to after the dedup) must agree EXACTLY with AttributeBundles.ApplyBundleNoVolatile's
/// inline BEM-base rule over real testbed class names. Impl-A = the Oracle method;
/// Impl-B = the real Observation strip path (a token NOT in volatile_classes survives
/// iff it is NOT a BEM base of one). Any divergence is a finding — do not dedup.
/// </summary>
public class BemDedupParityTests
{
    private static readonly IReadOnlySet<string> VolatileClasses =
        new HashSet<string>(StringComparer.Ordinal)
        {
            "gallery__nav-btn--next--b3c4d5",
            "pkg-select--a9b8c7",
            "price-tag--vue-d4e5f6",
            "data-v-7ba5bd90",
        };

    private static readonly string[] ClassNames =
    {
        // BEM bases of a volatile class → must be flagged
        "gallery__nav-btn--next", "gallery__nav-btn", "pkg-select", "price-tag",
        // legitimate semantic classes → must NOT be flagged
        "btn", "btn-primary", "btn-search", "form-select", "nav-search",
        "add-to-cart-btn", "qty-input", "write-review-btn", "breadcrumb",
        "notice-bar", "notice-bar__inner", "header-search", "header-search__btn",
        "header-utils__btn", "mm-panel", "nav-bar", "list-item", "tab-content",
    };

    [Fact]
    public void OracleBemRule_matches_ObservationStrip_overRealClassNames()
    {
        var noVolIds = new HashSet<string>(StringComparer.Ordinal);
        var disagreements = new List<string>();
        foreach (var name in ClassNames)
        {
            // isolation invariant: not a literal volatile class, so the strip
            // decision reflects ONLY the BEM rule (not the Contains branch).
            Assert.DoesNotContain(name, VolatileClasses);

            bool oracleBem = IsBemBaseOfVolatile(name, VolatileClasses);

            var el = new ElementData("div", "",
                new Dictionary<string, string> { ["class"] = name + " keep-me-stable" });
            var filtered = AttributeBundles.ApplyBundleNoVolatile(el, noVolIds, VolatileClasses);
            bool survived = filtered.Attrs.TryGetValue("class", out var cls)
                            && cls!.Split(' ').Contains(name);

            if (oracleBem != !survived)
            {
                disagreements.Add($"{name}: oracle={oracleBem} observationStripped={!survived}");
            }
        }

        Assert.True(disagreements.Count == 0,
            "BEM-base rule divergence between Oracle and Observation: " +
            string.Join("; ", disagreements));
    }
}
