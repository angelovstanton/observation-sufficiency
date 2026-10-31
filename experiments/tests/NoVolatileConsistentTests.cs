using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using System.Text.Json;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using Xunit;

namespace Experiments.Tests;

/// <summary>Repo-root and truth.json helpers shared by the tests in this project.</summary>
internal static class Testbed
{
    public static string RepoRoot { get; } = FindRepoRoot();

    private static string FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "ObservationSufficiency.slnx")))
        {
            dir = dir.Parent;
        }
        return dir?.FullName ?? throw new InvalidOperationException("ObservationSufficiency.slnx not found above test output");
    }

    public static (HashSet<string> Ids, HashSet<string> Classes) VolatilityLabels(string pageId)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(
            Path.Combine(RepoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json")));
        var labels = doc.RootElement.GetProperty("volatility_labels");
        return (labels.GetProperty("volatile_ids").EnumerateArray().Select(e => e.GetString()!).ToHashSet(StringComparer.Ordinal),
                labels.GetProperty("volatile_classes").EnumerateArray().Select(e => e.GetString()!).ToHashSet(StringComparer.Ordinal));
    }

    public static IEnumerable<string> Pages => Enumerable.Range(1, 24).Select(n => $"page_{n:D2}");
}

/// <summary>
/// Unit tests for AttributeBundles.ApplyBundleNoVolatileConsistent. No browser.
/// </summary>
public class NoVolatileConsistentBundleTests
{
    /// <summary>
    /// The 20 distinct class tokens that leaked into B_noVolatile observations and that the
    /// predicate flags (experiments/results/revision1/volatile_in_noVolatile.json, class (i)).
    /// </summary>
    public static TheoryData<string, string> LeakedTokens => new()
    {
        { "page_17", "ConsolePanel_toggleInput__w6x7y8" }, { "page_17", "EditPanel_input__m4n5o6" },
        { "page_17", "EditPanel_saveBtn__x6y7z8" },        { "page_17", "EditPanel_select__p7q8r9" },
        { "page_17", "Toolbar_newUserBtn__e4f5g6" },       { "page_17", "Toolbar_roleFilter__b1c2d3" },
        { "page_17", "UserCell_username__e5f6g7" },        { "page_18", "BoardToolbar_filterInput__l1m2n3" },
        { "page_18", "BoardToolbar_newBtn__o4p5q6" },      { "page_18", "EditPanel_saveBtn__k8l9m0" },
        { "page_18", "KanbanPanel_addBtn__w9x0y1" },       { "page_18", "KanbanPanel_sortSel__d7e8f9" },
        { "page_22", "EditForm_saveBtn__q4r5s6" },         { "page_22", "TfAction_refreshBtn__a1b2c3" },
        { "page_22", "TrackPanel_carrierSel__c6d7e8" },    { "page_22", "TrackPanel_exportBtn__f9g0h1" },
        { "page_23", "PayWidget_submitBtn__k2l3m4" },      { "page_24", "AccountSection_btnOutline__k7l8m9" },
        { "page_24", "PrefPanel_saveBtn__y2z3a4" },        { "page_24", "SettingsPanel_check__f8g9h0" },
    };

    private static ElementData El(string cls, string? id = null)
    {
        var attrs = new Dictionary<string, string> { ["class"] = cls };
        if (id is not null)
        {
            attrs["id"] = id;
        }
        return new ElementData("button", "", attrs, false);
    }

    private static string[] Classes(ElementData e) =>
        e.Attrs.TryGetValue("class", out var c) ? c.Split(' ', StringSplitOptions.RemoveEmptyEntries) : [];

    [Theory]
    [MemberData(nameof(LeakedTokens))]
    public void LeakedToken_is_removed_by_consistent_and_kept_by_noVolatile(string pageId, string token)
    {
        var (ids, classes) = Testbed.VolatilityLabels(pageId);
        Assert.DoesNotContain(token, classes);                     // it is not labelled …
        Assert.True(Oracle.LocatorUsesVolatileSignal("css", "." + token, ids, classes)); // … but the predicate flags it

        var el = El(token + " keep-me-stable");
        Assert.Contains(token, Classes(AttributeBundles.ApplyBundleNoVolatile(el, ids, classes)));
        var consistent = AttributeBundles.ApplyBundleNoVolatileConsistent(el, ids, classes);
        Assert.DoesNotContain(token, Classes(consistent));
        Assert.Contains("keep-me-stable", Classes(consistent));
    }

    // Same fixture as BemDedupParityTests in shared/oracle.tests.
    private static readonly HashSet<string> BemVolatileClasses = new(StringComparer.Ordinal)
    {
        "gallery__nav-btn--next--b3c4d5", "pkg-select--a9b8c7", "price-tag--vue-d4e5f6", "data-v-7ba5bd90",
    };

    [Theory]
    [InlineData("gallery__nav-btn--next")]
    [InlineData("gallery__nav-btn")]
    [InlineData("pkg-select")]
    [InlineData("price-tag")]
    public void BemBase_is_removed_like_noVolatile(string token)
    {
        var el = El(token + " keep-me-stable");
        var noIds = new HashSet<string>(StringComparer.Ordinal);
        Assert.DoesNotContain(token, Classes(AttributeBundles.ApplyBundleNoVolatile(el, noIds, BemVolatileClasses)));
        Assert.DoesNotContain(token, Classes(AttributeBundles.ApplyBundleNoVolatileConsistent(el, noIds, BemVolatileClasses)));
    }

    [Theory]
    [InlineData("btn")] [InlineData("btn-primary")] [InlineData("btn-search")] [InlineData("form-select")]
    [InlineData("nav-search")] [InlineData("add-to-cart-btn")] [InlineData("qty-input")]
    [InlineData("write-review-btn")] [InlineData("breadcrumb")] [InlineData("notice-bar")]
    [InlineData("notice-bar__inner")] [InlineData("header-search")] [InlineData("header-search__btn")]
    [InlineData("header-utils__btn")] [InlineData("mm-panel")] [InlineData("nav-bar")]
    [InlineData("list-item")] [InlineData("tab-content")]
    public void SemanticClass_is_kept(string token)
    {
        var el = El(token);
        var noIds = new HashSet<string>(StringComparer.Ordinal);
        Assert.Contains(token, Classes(AttributeBundles.ApplyBundleNoVolatileConsistent(el, noIds, BemVolatileClasses)));
    }

    [Fact]
    public void LabelledVolatileClassAndId_are_removed_like_noVolatile()
    {
        var (ids, classes) = Testbed.VolatilityLabels("page_21");
        var el = El("VideoPlayer_overlay__a2b3c4 keep-me-stable", id: "player-session-a3f4b5");
        foreach (var filtered in new[]
                 {
                     AttributeBundles.ApplyBundleNoVolatile(el, ids, classes),
                     AttributeBundles.ApplyBundleNoVolatileConsistent(el, ids, classes),
                 })
        {
            Assert.False(filtered.Attrs.ContainsKey("id"));
            Assert.DoesNotContain("VideoPlayer_overlay__a2b3c4", Classes(filtered));
            Assert.Contains("keep-me-stable", Classes(filtered));
        }
    }

    [Fact]
    public void UnlabelledRegexVolatileId_is_removed_by_consistent_only()
    {
        var none = new HashSet<string>(StringComparer.Ordinal);
        var el = El("keep-me-stable", id: "item-123456");               // matches VolatileIdRe
        Assert.True(Oracle.LocatorUsesVolatileSignal("css", "#item-123456", none, none));
        Assert.Equal("item-123456", AttributeBundles.ApplyBundleNoVolatile(el, none, none).Attrs["id"]);
        Assert.False(AttributeBundles.ApplyBundleNoVolatileConsistent(el, none, none).Attrs.ContainsKey("id"));
    }

    // CSS-special characters (synthetic; no such token exists in the 24-page corpus DOM)

    [Theory]
    [InlineData("md:flex")]
    [InlineData("w-1/2")]
    [InlineData("sm:w-[200px]")]
    [InlineData("v1.2")]
    public void SpecialCharacterStableToken_is_kept(string token)
    {
        var none = new HashSet<string>(StringComparer.Ordinal);
        Assert.False(AttributeBundles.PredicateFlagsClassToken(token, none, none));
        Assert.Contains(token, Classes(AttributeBundles.ApplyBundleNoVolatileConsistent(El(token), none, none)));
    }

    [Theory]
    [InlineData("hover:Toolbar_roleFilter__b1c2d3")]   // hashed CSS-module token behind a variant prefix
    [InlineData("md:css-xK2mPq9")]                      // styled-components hash behind a variant prefix
    public void SpecialCharacterVolatileToken_is_removed(string token)
    {
        var none = new HashSet<string>(StringComparer.Ordinal);
        // The valid-CSS selector for this token is [class~="..."]; the predicate flags it.
        Assert.True(Oracle.LocatorUsesVolatileSignal("css", $"[class~=\"{token}\"]", none, none));
        Assert.True(AttributeBundles.PredicateFlagsClassToken(token, none, none));
        Assert.DoesNotContain(token, Classes(AttributeBundles.ApplyBundleNoVolatileConsistent(El(token + " keep-me-stable"), none, none)));
    }

    [Fact]
    public void ReactStyleSpecialCharacterId_is_removed()
    {
        var none = new HashSet<string>(StringComparer.Ordinal);
        // `#:r1a` is not valid CSS and the predicate's #id regex does not capture it; [id=":r1a"] is valid.
        Assert.False(Oracle.LocatorUsesVolatileSignal("css", "#:r1a", none, none));
        Assert.True(AttributeBundles.PredicateFlagsId(":r1a", none, none));
        Assert.False(AttributeBundles.ApplyBundleNoVolatileConsistent(El("keep-me-stable", id: ":r1a"), none, none)
                                     .Attrs.ContainsKey("id"));
    }

    [Theory]
    [MemberData(nameof(LeakedTokens))]
    public void PlainIdentifier_verdict_is_identical_for_dot_and_attribute_forms(string pageId, string token)
    {
        var (ids, classes) = Testbed.VolatilityLabels(pageId);
        foreach (var tok in new[] { token, "keep-me-stable", "btn-primary", "breadcrumb__item" })
        {
            Assert.Equal(Oracle.LocatorUsesVolatileSignal("css", "." + tok, ids, classes),
                         AttributeBundles.PredicateFlagsClassToken(tok, ids, classes));
        }
    }

    [Fact]
    public void ConditionFive_bundle_set_is_BundleFull()
    {
        Assert.Same(AttributeBundles.BundleFull,
                    AttributeBundles.ResolveBundleSetForSignalCheck("B_noVolatileConsistent"));
    }
}

/// <summary>
/// Integration test (Playwright + python http.server): for all 24 pages × F0–F3, no class
/// or id token in a B_noVolatileConsistent observation is flagged by the predicate's
/// volatile check (Oracle.LocatorUsesVolatileSignal, exact-token forms).
/// </summary>
[Trait("Category", "Integration")]
public class NoVolatileConsistentObservationTests
{
    // `.tok` / `#id` are valid CSS only for plain identifiers; checked in addition for those.
    private static readonly System.Text.RegularExpressions.Regex PlainClass = new(@"^[A-Za-z][A-Za-z0-9_-]*$");
    private static readonly System.Text.RegularExpressions.Regex PlainId = new(@"^[A-Za-z0-9_-]+$");

    private static int FreePort()
    {
        var l = new TcpListener(IPAddress.Loopback, 0);
        l.Start();
        var port = ((IPEndPoint)l.LocalEndpoint).Port;
        l.Stop();
        return port;
    }

    [Fact]
    public async Task No_predicate_flagged_class_or_id_token_in_any_page_or_encoding()
    {
        var port = FreePort();
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

        var violations = new List<string>();
        int checkedTokens = 0, observations = 0;
        try
        {
            using var playwright = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await playwright.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                foreach (var pageId in Testbed.Pages)
                {
                    var (ids, classes) = Testbed.VolatilityLabels(pageId);
                    var page = await browser.NewPageAsync();
                    await page.GotoAsync($"http://127.0.0.1:{port}/pages/{pageId}.html", new() { Timeout = 90_000 });
                    await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle, new() { Timeout = 90_000 });
                    foreach (var enc in new[] { "F0", "F1", "F2", "F3" })
                    {
                        var (obsText, _, filtered) = await Observation.BuildObservationAsync(
                            page, "B_noVolatileConsistent", enc, ids, classes);
                        Assert.False(string.IsNullOrWhiteSpace(obsText), $"{pageId} {enc}: empty observation");
                        observations++;
                        foreach (var el in filtered)
                        {
                            if (el.Attrs.TryGetValue("id", out var id) && !string.IsNullOrEmpty(id))
                            {
                                checkedTokens++;
                                if (Oracle.LocatorUsesVolatileSignal("css", $"[id=\"{id}\"]", ids, classes)
                                    || (PlainId.IsMatch(id) && Oracle.LocatorUsesVolatileSignal("css", "#" + id, ids, classes)))
                                {
                                    violations.Add($"{pageId} {enc} id={id}");
                                }
                            }
                            if (el.Attrs.TryGetValue("class", out var cls))
                            {
                                foreach (var tok in cls.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                                {
                                    checkedTokens++;
                                    if (Oracle.LocatorUsesVolatileSignal("css", $"[class~=\"{tok}\"]", ids, classes)
                                        || (PlainClass.IsMatch(tok) && Oracle.LocatorUsesVolatileSignal("css", "." + tok, ids, classes)))
                                    {
                                        violations.Add($"{pageId} {enc} class={tok}");
                                    }
                                }
                            }
                        }
                    }
                    await page.CloseAsync();
                }
            }
            finally { await browser.CloseAsync(); }
        }
        finally
        {
            try { server.Kill(entireProcessTree: true); } catch { }
        }

        Assert.Equal(96, observations);
        Assert.True(checkedTokens > 0);
        Assert.True(violations.Count == 0,
            $"{violations.Count} predicate-flagged token(s) in B_noVolatileConsistent observations: "
            + string.Join("; ", violations.Take(20)));
    }
}
