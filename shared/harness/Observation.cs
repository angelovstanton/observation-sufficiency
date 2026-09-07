using System.Text.Json;
using BoundedAgents.Shared.Oracle;
using Microsoft.Playwright;

namespace BoundedAgents.Shared.Harness;

/// <summary>
/// Observation builder: DOM walk → bundle filter (Axis A) → encoding (Axis B).
///
/// Axis A and Axis B are kept separable in code and in the results schema —
/// that separation makes the science/engineering distinction operational (§5).
///
/// DOM-walk bundles (F0–F3): JS browser-agnostic walk feeds all six bundles.
/// ARIA snapshot path (F4 / B_playwrightMCP): genuine page.AriaSnapshotAsync() —
/// not a reconstruction from the DOM walk (STACK.md §2, TESTBED_SPEC §3).
/// </summary>
public static class Observation
{
    // -----------------------------------------------------------------------
    // DOM walk — browser-agnostic JS (Playwright executes it)
    // -----------------------------------------------------------------------

    private const string DomWalkJs = """
        () => {
            const SKIP = new Set(['script','style','meta','head','link','noscript','title']);
            const INTERACTIVE = new Set(['a','button','input','select','textarea','label']);
            const results = [];
            function walk(el, inShadow) {
                const tag = el.tagName.toLowerCase();
                if (SKIP.has(tag)) return;
                const attrs = {};
                for (const a of el.attributes) attrs[a.name] = a.value;
                const rawText = (el.innerText || el.textContent || '').trim();
                const text = rawText.length > 300 ? rawText.slice(0, 300) + '…' : rawText;
                if (Object.keys(attrs).length > 0 || INTERACTIVE.has(tag))
                    results.push({ tag, text, attrs, isInShadow: inShadow });
                if (el.shadowRoot)
                    for (const child of el.shadowRoot.children) walk(child, true);
                for (const child of el.children) walk(child, inShadow);
            }
            walk(document.body, false);
            return results;
        }
        """;

    /// <summary>
    /// Runs the browser-agnostic DOM walk and returns one ElementData per visited
    /// element, shadow roots included. This is D — the unprojected state tree that
    /// every F0-F3 bundle is derived from (F4 uses the real ARIA snapshot instead).
    /// </summary>
    public static async Task<IReadOnlyList<ElementData>> WalkDomAsync(IPage page)
    {
        var json = await page.EvaluateAsync<JsonElement>(DomWalkJs);
        var results = new List<ElementData>();

        foreach (var el in json.EnumerateArray())
        {
            var tag = el.GetProperty("tag").GetString() ?? "";
            var text = el.GetProperty("text").GetString() ?? "";
            var attrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var prop in el.GetProperty("attrs").EnumerateObject())
            {
                attrs[prop.Name] = prop.Value.GetString() ?? "";
            }

            bool inShadow = el.TryGetProperty("isInShadow", out var shadowProp)
                         && shadowProp.ValueKind == JsonValueKind.True;
            results.Add(new ElementData(tag, text, attrs, inShadow));
        }
        return results;
    }


    // -----------------------------------------------------------------------
    // F4 / B_playwrightMCP — genuine Playwright ARIA snapshot path
    // -----------------------------------------------------------------------

    /// <summary>
    /// Builds the B_playwrightMCP observation using the genuine Playwright ARIA
    /// snapshot (page.AriaSnapshotAsync). NOT a reconstruction from the DOM walk.
    ///
    /// Returns:
    ///   AriaYaml          — the ARIA snapshot YAML sent to the model
    ///   RawWithAnchors    — raw DOM walk result (for oracle element resolution)
    ///   OracleLeakDetected — true if "oracle" appears in the ARIA YAML (FAIL)
    ///
    /// ARIA snapshots do not serialize data-* attributes, so oracle anchors
    /// (data-oracle-id) should not appear — but this is verified empirically
    /// per TESTBED_SPEC §3 and §8.
    /// </summary>
    public static async Task<(string AriaYaml,
                               IReadOnlyList<ElementData> RawWithAnchors,
                               bool OracleLeakDetected)>
        BuildAriaObservationAsync(IPage page)
    {
        var rawWithAnchors = await WalkDomAsync(page); // for oracle evaluation
        var ariaYaml = await page.AriaSnapshotAsync();
        var oracleLeakDetected = ariaYaml.Contains("oracle", StringComparison.OrdinalIgnoreCase);
        return (ariaYaml, rawWithAnchors, oracleLeakDetected);
    }

    // -----------------------------------------------------------------------
    // Full D→O pipeline — DOM-walk path (F0, F1, F2, F3)
    // -----------------------------------------------------------------------

    /// <summary>
    /// Returns:
    ///   ObsText        — encoded text sent to the model (oracle anchors stripped, bundle applied)
    ///   RawWithAnchors — raw DOM walk result including data-oracle-* (for oracle evaluation)
    ///   Filtered       — post-strip, post-bundle elements (for oracle stable-signal check)
    ///
    /// For B_noVolatile, pass the page's volatileIds and volatileClasses from truth.json.
    /// For B_playwrightMCP / F4 use BuildAriaObservationAsync instead.
    /// </summary>
    public static async Task<(string ObsText,
                               IReadOnlyList<ElementData> RawWithAnchors,
                               IReadOnlyList<ElementData> Filtered)>
        BuildObservationAsync(
            IPage page,
            string bundle,
            string encoding,
            IReadOnlySet<string>? volatileIds = null,
            IReadOnlySet<string>? volatileClasses = null)
    {
        var rawWithAnchors = await WalkDomAsync(page);               // keeps data-oracle-*
        var stripped = AttributeBundles.StripOracleAnchors(rawWithAnchors); // remove oracle anchors

        IReadOnlyList<ElementData> filtered;
        if (bundle.Equals("B_noVolatile", StringComparison.OrdinalIgnoreCase))
        {
            filtered = stripped
                .Select(el => AttributeBundles.ApplyBundleNoVolatile(el, volatileIds, volatileClasses))
                .Where(ObservationEncoders.HasContent)
                .ToList();
        }
        else
        {
            var bundleSet = AttributeBundles.GetBundle(bundle);
            filtered = stripped
                .Select(el => AttributeBundles.ApplyBundle(el, bundleSet))
                .Where(ObservationEncoders.HasContent)
                .ToList();
        }

        var obsText = encoding.ToUpperInvariant() switch
        {
            "F0" => ObservationEncoders.EncodeF0Html(filtered),
            "F1" => ObservationEncoders.EncodeF1Json(filtered),
            "F2" => ObservationEncoders.EncodeF2CompactJson(filtered),
            "F3" => ObservationEncoders.EncodeF3Linearized(filtered),
            "FLAT_KV" => ObservationEncoders.EncodeFlatKv(filtered),    // smoke-test only
            _ => throw new ArgumentException(
                             $"Unknown encoding '{encoding}'. Implemented: F0, F1, F2, F3, F4 (via BuildAriaObservationAsync)."),
        };
        return (obsText, rawWithAnchors, filtered);
    }
}
