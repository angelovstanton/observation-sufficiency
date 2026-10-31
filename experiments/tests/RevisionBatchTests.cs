using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using Xunit;
using Xunit.Abstractions;

namespace Experiments.Tests;

/// <summary>
/// Unit tests (no browser) for the Block 1 single-ablation bundles and the Block 2 F2L legend.
/// </summary>
public class RevisionBatchUnitTests
{
    private static readonly HashSet<string> NoIds = new(StringComparer.Ordinal);
    private static readonly HashSet<string> VolCls = new(StringComparer.Ordinal) { "css-xK2mPq9" };

    private static ElementData El(string? id, string? cls, params (string K, string V)[] more)
    {
        var attrs = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (id is not null) attrs["id"] = id;
        if (cls is not null) attrs["class"] = cls;
        foreach (var (k, v) in more) attrs[k] = v;
        return new ElementData("button", "Save", attrs, false);
    }

    [Fact]
    public void MinusAria_removes_every_aria_attribute_and_keeps_role_and_tabindex()
    {
        var removed = AttributeBundles.BundleFull.Except(AttributeBundles.BundleFullMinusAria).ToHashSet();
        Assert.Equal(13, removed.Count);
        Assert.All(removed, a => Assert.StartsWith("aria-", a));
        Assert.Contains("aria-label", removed);
        Assert.Contains("role", AttributeBundles.BundleFullMinusAria);
        Assert.Contains("tabindex", AttributeBundles.BundleFullMinusAria);
        Assert.DoesNotContain(AttributeBundles.BundleFullMinusAria, a => a.StartsWith("aria-", StringComparison.OrdinalIgnoreCase));
        Assert.Same(AttributeBundles.BundleFullMinusAria, AttributeBundles.GetBundle("B_full_minus_aria"));
    }

    [Fact]
    public void MinusState_is_the_B_noState_set()
    {
        Assert.Same(AttributeBundles.BundleNoState, AttributeBundles.GetBundle("B_full_minus_state"));
        Assert.True(AttributeBundles.BundleFull.Except(AttributeBundles.BundleNoState)
            .ToHashSet(StringComparer.OrdinalIgnoreCase).SetEquals(AttributeBundles.AttributeCategories["state"]));
    }

    [Theory]
    [InlineData("B_full_minus_volClass")]
    [InlineData("B_full_minus_volId")]
    public void Value_level_ablations_use_BundleFull_for_condition5(string bundle) =>
        Assert.Same(AttributeBundles.BundleFull, AttributeBundles.ResolveBundleSetForSignalCheck(bundle));

    [Fact]
    public void MinusVolClass_strips_flagged_class_tokens_only()
    {
        var el = El(":r1a", "btn css-xK2mPq9 Toolbar_roleFilter__b1c2d3", ("aria-label", "Save"));
        var r = AttributeBundles.ApplyBundleMinusVolatileClass(el, NoIds, VolCls);
        Assert.Equal("btn", r.Attrs["class"]);
        Assert.Equal(":r1a", r.Attrs["id"]);                 // id untouched
        Assert.Equal("Save", r.Attrs["aria-label"]);
        Assert.Equal("Save", r.Text);
    }

    [Fact]
    public void MinusVolId_strips_flagged_id_only()
    {
        var el = El(":r1a", "btn css-xK2mPq9");
        var r = AttributeBundles.ApplyBundleMinusVolatileId(el, NoIds, VolCls);
        Assert.False(r.Attrs.ContainsKey("id"));
        Assert.Equal("btn css-xK2mPq9", r.Attrs["class"]);    // class untouched
        var stable = AttributeBundles.ApplyBundleMinusVolatileId(El("save-btn", null), NoIds, VolCls);
        Assert.Equal("save-btn", stable.Attrs["id"]);
    }

    [Fact]
    public void All_class_tokens_flagged_drops_the_class_attribute()
    {
        var r = AttributeBundles.ApplyBundleMinusVolatileClass(El(null, "css-xK2mPq9"), NoIds, VolCls);
        Assert.False(r.Attrs.ContainsKey("class"));
    }

    [Fact]
    public void Synthetic_union_of_class_and_id_ablations_equals_NVC()
    {
        var el = El(":r1a", "btn css-xK2mPq9 Toolbar_roleFilter__b1c2d3", ("value", "x"), ("aria-label", "Save"));
        RevisionBatchIntegrationTests.AssertUnionEqualsNvc(el, NoIds, VolCls, "synthetic");
    }

    [Fact]
    public void F2Legend_has_33_pairs_that_expand_through_the_F2_key_map()
    {
        Assert.StartsWith("legend: ", ObservationEncoders.F2Legend);
        Assert.DoesNotContain("\n", ObservationEncoders.F2Legend);
        var pairs = ObservationEncoders.F2Legend["legend: ".Length..].Split(", ")
            .Select(p => p.Split('=')).ToList();
        Assert.Equal(33, pairs.Count);
        Assert.All(pairs, p => Assert.Equal(2, p.Length));
        Assert.Equal(33, pairs.Select(p => p[0]).Distinct().Count());
        Assert.Equal(("t", "tag"), (pairs[0][0], pairs[0][1]));          // declaration order
        Assert.Equal(("sh", "is_shadow"), (pairs[^1][0], pairs[^1][1]));
        foreach (var p in pairs)
        {
            var expanded = ObservationEncoders.ExpandF2Keys($"[{{\"{p[0]}\":\"v\"}}]");
            Assert.Equal($"[{{\"{p[1]}\":\"v\"}}]", expanded);
        }
    }

    [Fact]
    public void F2L_is_legend_line_plus_F2()
    {
        var els = new List<ElementData> { El("save-btn", "btn", ("aria-label", "Save")) };
        Assert.Equal(ObservationEncoders.F2Legend + "\n" + ObservationEncoders.EncodeF2CompactJson(els),
                     ObservationEncoders.EncodeF2LLegend(els));
    }
}

/// <summary>Shared Playwright walk of the 24 pages (one browser session for the class).</summary>
public sealed class TestbedPagesFixture : IAsyncLifetime
{
    public sealed record Target(string Id, string Oracle, string[] SignalAttrs);

    public sealed record PageData(
        string PageId, HashSet<string> Ids, HashSet<string> Classes, IReadOnlyList<ElementData> Raw,
        IReadOnlyList<Target> Targets, Dictionary<(string Bundle, string Enc), string> Obs);

    public List<PageData> Pages { get; } = new();

    private static readonly (string Bundle, string Enc)[] ObsCells =
    {
        ("B_full", "F1"), ("B_full", "F2"), ("B_full", "F2L"),
        ("B_noVolatile", "F1"), ("B_noVolatile", "F2"), ("B_noVolatile", "F2L"),
    };

    public async Task InitializeAsync()
    {
        var l = new TcpListener(IPAddress.Loopback, 0);
        l.Start();
        var port = ((IPEndPoint)l.LocalEndpoint).Port;
        l.Stop();
        var server = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --bind 127.0.0.1 --directory \"{Path.Combine(Testbed.RepoRoot, "shared", "testbed")}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        server.BeginOutputReadLine();
        server.BeginErrorReadLine();
        await Task.Delay(1200);
        try
        {
            using var playwright = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await playwright.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                foreach (var pageId in Testbed.Pages)
                {
                    var (ids, classes) = Testbed.VolatilityLabels(pageId);
                    using var doc = JsonDocument.Parse(File.ReadAllText(
                        Path.Combine(Testbed.RepoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json")));
                    var targets = doc.RootElement.GetProperty("targets").EnumerateArray()
                        .Select(t => new Target(t.GetProperty("id").GetString()!, t.GetProperty("oracle").GetString()!,
                                                t.GetProperty("signal_attrs").EnumerateArray().Select(a => a.GetString()!).ToArray()))
                        .ToList();
                    var page = await browser.NewPageAsync();
                    await page.GotoAsync($"http://127.0.0.1:{port}/pages/{pageId}.html", new() { Timeout = 90_000 });
                    await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle, new() { Timeout = 90_000 });
                    var raw = await Observation.WalkDomAsync(page);
                    var obs = new Dictionary<(string, string), string>();
                    foreach (var (b, e) in ObsCells)
                    {
                        obs[(b, e)] = (await Observation.BuildObservationAsync(page, b, e, ids, classes)).ObsText;
                    }
                    Pages.Add(new PageData(pageId, ids, classes, raw, targets, obs));
                    await page.CloseAsync();
                }
            }
            finally { await browser.CloseAsync(); }
        }
        finally
        {
            try { server.Kill(entireProcessTree: true); } catch { }
        }
    }

    public Task DisposeAsync() => Task.CompletedTask;
}

/// <summary>
/// Integration tests (Playwright + python http.server) over the 24 testbed pages:
/// (a) −volClass ∪ −volId removes exactly what B_noVolatileConsistent removes;
/// (b) condition 5 per target is what each ablation bundle implies;
/// F2L = legend + F2 and its F2 part round-trips to F1.
/// </summary>
[Trait("Category", "Integration")]
public class RevisionBatchIntegrationTests : IClassFixture<TestbedPagesFixture>
{
    private readonly TestbedPagesFixture _fx;
    private readonly ITestOutputHelper _out;

    public RevisionBatchIntegrationTests(TestbedPagesFixture fx, ITestOutputHelper output)
    {
        _fx = fx;
        _out = output;
    }

    /// <summary>(attr, value-or-class-token) pairs of a projected element.</summary>
    private static HashSet<(string, string)> Units(ElementData e)
    {
        var s = new HashSet<(string, string)>();
        foreach (var (k, v) in e.Attrs)
        {
            if (k.Equals("class", StringComparison.OrdinalIgnoreCase))
            {
                foreach (var tok in v.Split(' ', StringSplitOptions.RemoveEmptyEntries)) s.Add(("class", tok));
            }
            else
            {
                s.Add((k.ToLowerInvariant(), v));
            }
        }
        s.Add(("#text", e.Text));
        return s;
    }

    internal static void AssertUnionEqualsNvc(ElementData el, IReadOnlySet<string> ids, IReadOnlySet<string> cls, string where)
    {
        var full = Units(AttributeBundles.ApplyBundle(el, AttributeBundles.BundleFull));
        var rc = full.Except(Units(AttributeBundles.ApplyBundleMinusVolatileClass(el, ids, cls))).ToHashSet();
        var ri = full.Except(Units(AttributeBundles.ApplyBundleMinusVolatileId(el, ids, cls))).ToHashSet();
        var rn = full.Except(Units(AttributeBundles.ApplyBundleNoVolatileConsistent(el, ids, cls))).ToHashSet();
        Assert.All(rc, u => Assert.Equal("class", u.Item1));
        Assert.All(ri, u => Assert.Equal("id", u.Item1));
        Assert.True(rn.SetEquals(rc.Union(ri)),
            $"{where}: NVC removes {{{string.Join(", ", rn)}}}, −volClass ∪ −volId removes {{{string.Join(", ", rc.Union(ri))}}}");
    }

    [Fact]
    public void Union_of_class_and_id_ablations_removes_exactly_what_NVC_removes_on_all_pages()
    {
        int elements = 0, removedClass = 0, removedId = 0;
        foreach (var p in _fx.Pages)
        {
            foreach (var el in AttributeBundles.StripOracleAnchors(p.Raw))
            {
                AssertUnionEqualsNvc(el, p.Ids, p.Classes, $"{p.PageId} <{el.Tag}>");
                elements++;
                var full = AttributeBundles.ApplyBundle(el, AttributeBundles.BundleFull);
                removedClass += Units(full).Except(Units(AttributeBundles.ApplyBundleMinusVolatileClass(el, p.Ids, p.Classes))).Count();
                removedId += Units(full).Except(Units(AttributeBundles.ApplyBundleMinusVolatileId(el, p.Ids, p.Classes))).Count();
            }
        }
        Assert.Equal(24, _fx.Pages.Count);
        Assert.True(removedClass > 0 && removedId > 0);
        _out.WriteLine($"{elements} elements; removed class-token instances {removedClass}, id instances {removedId}");
    }

    private static bool Cond5(TestbedPagesFixture.PageData p, TestbedPagesFixture.Target t, IReadOnlySet<string> set,
                              IReadOnlyList<string>? attrs = null)
    {
        var oracleEl = p.Raw.FirstOrDefault(e => e.Attrs.TryGetValue("data-oracle-id", out var oid) && oid == t.Oracle);
        return Oracle.ComputeStableSignalPresence(attrs ?? t.SignalAttrs, a => set.Contains(a), oracleEl, p.Ids, p.Classes);
    }

    [Fact]
    public void Condition5_per_ablation_bundle_is_as_expected()
    {
        var full = AttributeBundles.ResolveBundleSetForSignalCheck("B_full");
        var dropped = new List<string>();
        int n = 0;
        foreach (var p in _fx.Pages)
        {
            foreach (var t in p.Targets)
            {
                n++;
                bool cFull = Cond5(p, t, full);
                Assert.Equal(cFull, Cond5(p, t, AttributeBundles.ResolveBundleSetForSignalCheck("B_full_minus_volClass")));
                Assert.Equal(cFull, Cond5(p, t, AttributeBundles.ResolveBundleSetForSignalCheck("B_full_minus_volId")));
                Assert.Equal(Cond5(p, t, AttributeBundles.ResolveBundleSetForSignalCheck("B_noState")),
                             Cond5(p, t, AttributeBundles.ResolveBundleSetForSignalCheck("B_full_minus_state")));

                // −aria: condition 5 = B_full's condition 5 over the non-aria signal attributes; it can
                // only fall where every stable signal present under B_full is an aria-* attribute.
                bool cAria = Cond5(p, t, AttributeBundles.ResolveBundleSetForSignalCheck("B_full_minus_aria"));
                var nonAria = t.SignalAttrs.Where(a => !a.StartsWith("aria-", StringComparison.OrdinalIgnoreCase)).ToArray();
                Assert.Equal(Cond5(p, t, full, nonAria), cAria);
                Assert.True(!cAria || cFull, $"{p.PageId} {t.Id}: −aria has a stable signal B_full lacks");
                if (cFull && !cAria)
                {
                    dropped.Add($"{p.PageId} {t.Id} [{string.Join(",", t.SignalAttrs)}]");
                }
            }
        }
        Assert.Equal(240, n);
        _out.WriteLine($"B_full_minus_aria: condition 5 true→false on {dropped.Count} target(s): {string.Join("; ", dropped)}");
    }

    [Theory]
    [InlineData("B_full")]
    [InlineData("B_noVolatile")]
    public void F2L_is_legend_plus_F2_and_the_F2_part_round_trips_to_F1(string bundle)
    {
        foreach (var p in _fx.Pages)
        {
            var f2 = p.Obs[(bundle, "F2")];
            var f2l = p.Obs[(bundle, "F2L")];
            Assert.Equal(ObservationEncoders.F2Legend + "\n" + f2, f2l);
            var f2Part = f2l[(ObservationEncoders.F2Legend.Length + 1)..];
            Assert.True(ObservationEncoders.VerifyF2RoundTrip(p.Obs[(bundle, "F1")], f2Part),
                        $"{p.PageId} {bundle}: F2 part of F2L does not round-trip to F1");
        }
    }
}
