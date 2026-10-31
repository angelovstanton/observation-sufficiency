using System.Text.Json;
using System.Text.Json.Serialization;
using BoundedAgents.Experiments;
using BoundedAgents.Experiments.Batch;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using Microsoft.Playwright;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// The mutation window of addenda (а′) / (а″) / (д) (real_pilot/pilot_addendum_scoring_a2.md, _a3.md) on real pages,
/// offline, no model. (1) The observation walk and the Oracle evaluation do not write to the DOM: a window around the
/// walk alone and one around the evaluation alone count 0 records, on 2 testbed pages (every load) and on the 3 pilot
/// sites with page timers (a clean load within 5 — the timers, not the walk or the Oracle, are what moves the DOM).
/// (2) Survival (д): on 2 stable September pages the window holds exactly 1 excluded record (the Oracle marker on the
/// element found by role + name) and 0 others; on wikipedia a forced wait inside the window is caught.
/// Needs the decoded May / September HTML next to the repo (PilotPins.HtmlDir); skipped if it is missing.
/// </summary>
[Trait("Category", "RealPilot")]
public sealed class PilotMutationWindowTests
{
    private static readonly HashSet<string> None = new(StringComparer.Ordinal);

    private static PilotPlan Plan()
    {
        var o = PilotPins.Production(Testbed.RepoRoot) with
        {
            Env = name => name == "BAR_MODEL_DEPLOYMENT_1" ? "gpt-4.1" : null,
        };
        Assert.True(Directory.Exists(o.HtmlDir), $"pinned May HTML missing: {o.HtmlDir}");
        return PilotPreflight.Run(o);
    }

    /// <summary>Walk alone and Oracle evaluation alone, each in its own window: (walk count, evaluation count).</summary>
    private static async Task<(int Walk, int Eval)> WalkAndEvaluateAsync(
        IPage page, string bundle, string encoding, IReadOnlySet<string> volIds, IReadOnlySet<string> volCls,
        string marker, string locatorRaw)
    {
        await MutationWindow.OpenAsync(page);
        var (_, raw, _) = await Observation.BuildObservationAsync(page, bundle, encoding, volIds, volCls);
        var walk = await MutationWindow.CloseAsync(page);
        await MutationWindow.OpenAsync(page);
        var (lt, lv) = GroundingRunner.ParseLocatorForReplay(locatorRaw);
        var oracleRef = new OracleRef(marker);
        var el = await Oracle.FindOracleElementAsync(page, oracleRef);
        var set = AttributeBundles.ResolveBundleSetForSignalCheck(bundle);
        await Oracle.EvaluateLocatorAsync(page, lt, lv, el, raw, oracleRef.OracleId, a => set.Contains(a),
            null, volIds, volCls, Array.Empty<string>());
        return (walk, await MutationWindow.CloseAsync(page));
    }

    [Theory]
    [InlineData("page_01")]
    [InlineData("page_17")]   // nested shadow DOM
    public async Task Walk_and_oracle_write_nothing_on_static_testbed_pages(string pageId)
    {
        var dir = Path.Combine(Testbed.RepoRoot, "shared", "testbed", "pages");
        var body = await File.ReadAllBytesAsync(Path.Combine(dir, $"{pageId}.html"));
        var truth = JsonDocument.Parse(await File.ReadAllTextAsync(Path.Combine(dir, $"{pageId}.truth.json"))).RootElement;
        using var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        int checks = 0;
        foreach (var t in truth.GetProperty("targets").EnumerateArray())
        {
            var oracle = t.GetProperty("oracle").GetString()!;
            foreach (var (bundle, encoding, locator) in new[]
                     {
                         ("B_full", "F1", $"css:[data-oracle-id=\"{oracle}\"]"),
                         ("B_noVolatile", "F3", $"xpath://*[@data-oracle-id=\"{oracle}\"]"),
                     })
            {
                var (ctx, page, _) = await RealPilotOffline.LoadAsync(browser, $"https://testbed.invalid/pages/{pageId}.html",
                    body, null, null);
                try
                {
                    Assert.Equal((0, 0), await WalkAndEvaluateAsync(page, bundle, encoding, None, None, oracle, locator));
                    checks++;
                }
                finally { await ctx.CloseAsync(); }
            }
        }
        await browser.CloseAsync();
        Assert.True(checks >= 10, $"{checks} checks");
    }

    [RealPilotTheory]
    [InlineData("wikipedia.org")]
    [InlineData("kaspersky.com")]
    [InlineData("mobile.de")]
    public async Task Walk_and_oracle_write_nothing_on_the_three_timer_sites(string domain)
    {
        var p = Plan();
        var site = p.Sites.Single(s => s.Domain == domain);
        var body = await File.ReadAllBytesAsync(site.HtmlPath);
        var targets = p.TargetsBySite[site.Key];
        using var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        await RealPilotOffline.WarmUpAsync(browser, site.Url, body, site.Timestamp, p.ShimJs);
        // The page's own timers move these DOMs (≈0.3–0.5 s after the walk). To isolate the walk and the Oracle, the test
        // (only the test; the protocol does not) pauses the page clock after the load: no page timer fires afterwards, so
        // any record in the windows could only come from the walk or the evaluation.
        foreach (var t in targets.Take(3))
        {
            foreach (var locator in new[] { "xpath:" + t.Xpath, $"css:[data-oracle-id=\"{t.Marker}\"]" })
            {
                var (ctx, page, _, _, _, _) = await RealPilotOffline.ObserveCellAsync(browser, site.Url, body, site.Timestamp,
                    p.ShimJs, targets.Select(m => (m.Marker, m.Xpath)), "B_full", "F1", site.VolIds, site.VolClasses);
                try
                {
                    await ctx.Clock.PauseAtAsync(site.Timestamp.AddSeconds(10));
                    Assert.Equal((0, 0), await WalkAndEvaluateAsync(page, "B_full", "F1", site.VolIds, site.VolClasses,
                        t.Marker, locator));
                }
                finally { await ctx.CloseAsync(); }
            }
        }
        await browser.CloseAsync();
    }

    /// <summary>
    /// Addendum (а‴): the pause on a page loaded by the registered loader (SetFixedTime + Date/Math.random shim). Before
    /// the pause the page's timers run (control); after it no setTimeout / setInterval / requestAnimationFrame callback
    /// runs, none is fired by the pause (no forward jump: a 3 s timer stays pending), the mutation window counts 0,
    /// Date.now() stays the fixed time, and Math.random keeps the shim's sequence.
    /// </summary>
    [Fact]
    public async Task Clock_pause_at_the_current_time_fires_nothing_and_stops_every_timer()
    {
        var rp = Path.Combine(Testbed.RepoRoot, "experiments", "results", "revision1", "real_pilot");
        var shim = await File.ReadAllTextAsync(Path.Combine(rp, "rp_shim_random.js"));
        var fixedTime = new DateTime(2026, 5, 15, 0, 0, 0, DateTimeKind.Utc);
        const string html = @"<!doctype html><html><body><div id=a></div><script>
            window.__t = 0; window.__i = 0; window.__r = 0; window.__late = 0;
            function tick() { window.__t++; document.getElementById('a').setAttribute('t', window.__t); setTimeout(tick, 50); }
            setTimeout(tick, 50);
            setInterval(function () { window.__i++; document.body.setAttribute('i', window.__i); }, 70);
            function raf() { window.__r++; document.body.setAttribute('r', window.__r); requestAnimationFrame(raf); }
            requestAnimationFrame(raf);
            setTimeout(function () { window.__late++; document.body.classList.add('late'); }, 3000);
            </script></body></html>";
        const string counters = "() => [window.__t, window.__i, window.__r, window.__late, Date.now()]";
        using var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        var (ctx, page, _) = await RealPilotOffline.LoadAsync(browser, "https://clock.invalid/",
            System.Text.Encoding.UTF8.GetBytes(html), fixedTime, shim);
        try
        {
            await Task.Delay(400);
            var c0 = await page.EvaluateAsync<double[]>(counters);
            Assert.True(c0[0] > 0 && c0[1] > 0 && c0[2] > 0, "control: the timers run before the pause");
            await RealPilotOffline.PauseClockAsync(page, fixedTime);
            var c1 = await page.EvaluateAsync<double[]>(counters);
            await MutationWindow.OpenAsync(page);
            await Task.Delay(3500);
            var c2 = await page.EvaluateAsync<double[]>(counters);
            Assert.Equal(0, await MutationWindow.CloseAsync(page));
            Assert.Equal(c1, c2);                                  // nothing ran after the pause
            Assert.Equal(0, c2[3]);                                // the 3 s timer was not fired (no jump)
            Assert.InRange(c1[0] - c0[0], 0, 1);                   // no burst at the pause
            Assert.InRange(c1[1] - c0[1], 0, 1);
            Assert.Equal(new DateTimeOffset(fixedTime).ToUnixTimeMilliseconds(), (long)c2[4]);
            var random0 = await page.EvaluateAsync<double>("() => Math.random()");   // first call, after the pause

            // Math.random: the shim's sequence continues (seed 42, mulberry32), the pause does not touch it.
            var (ctx2, page2, _) = await RealPilotOffline.LoadAsync(browser, "https://clock.invalid/",
                System.Text.Encoding.UTF8.GetBytes("<!doctype html><p>x</p>"), fixedTime, shim);
            var expected = await page2.EvaluateAsync<double>("() => Math.random()");
            await ctx2.CloseAsync();
            Assert.Equal(expected, random0);
        }
        finally
        {
            await ctx.CloseAsync();
            await browser.CloseAsync();
        }
    }

    private sealed record SeptSite(string Key, string Domain, string Url, DateTime Timestamp,
                                   [property: JsonPropertyName("html_file")] string HtmlFile);

    private static async Task<(IBrowser Browser, IPlaywright Pw, SeptSite Site, byte[] Body, string Shim, string Cand,
                               List<(string Marker, string Role, string Name)> Targets)> SeptemberAsync(string domain)
    {
        var rp = Path.Combine(Testbed.RepoRoot, "experiments", "results", "revision1", "real_pilot");
        var st = JsonDocument.Parse(await File.ReadAllTextAsync(Path.Combine(rp, "survival_targets.json"))).RootElement;
        var site = st.GetProperty("sites").EnumerateArray()
            .Select(s => s.Deserialize<SeptSite>(new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!)
            .Single(s => s.Domain == domain);
        var htmlDir = Path.Combine(Path.GetDirectoryName(PilotPins.Production(Testbed.RepoRoot).HtmlDir)!, "CC-MAIN-2026-39");
        Assert.True(Directory.Exists(htmlDir), $"September HTML missing: {htmlDir}");
        var targets = st.GetProperty("items").EnumerateArray()
            .Where(t => t.GetProperty("domain").GetString() == domain && t.GetProperty("status").GetString() == "unique")
            .Select(t => (t.GetProperty("marker").GetString()!, t.GetProperty("role").GetString()!, t.GetProperty("name").GetString()!))
            .ToList();
        var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        return (browser, pw, site, await File.ReadAllBytesAsync(Path.Combine(htmlDir, site.HtmlFile)),
                await File.ReadAllTextAsync(Path.Combine(rp, "rp_shim_random.js")),
                await File.ReadAllTextAsync(Path.Combine(rp, "rp_candidates.js")), targets);
    }

    [RealPilotTheory]
    [InlineData("github.com")]
    [InlineData("wordpress.org")]
    public async Task Survival_window_excludes_exactly_the_one_marker_record_on_stable_pages(string domain)
    {
        var (browser, pw, site, body, shim, cand, targets) = await SeptemberAsync(domain);
        try
        {
            await RealPilotOffline.WarmUpAsync(browser, site.Url, body, site.Timestamp, shim);
            var (reference, _) = await RealPilotOffline.SeptemberReferenceLoadAsync(browser, site.Url, body, site.Timestamp, shim);
            foreach (var (marker, role, name) in targets.Take(3))
            {
                var r = await RealPilotOffline.EvaluateSurvivalAsync(browser, site.Url, body, site.Timestamp, shim, cand,
                    marker, role, name, $"css:[data-oracle-id=\"{marker}\"]", reference);
                Assert.Equal(new[] { reference }, r.PreHashes);
                Assert.Equal("determined", r.Status);
                Assert.Equal(new RealPilotOffline.SurvivalWindow(1, 0, 1), r.Windows[^1]);
                Assert.True(r.UniqueMatch == true && r.MatchesTarget == true);
            }
        }
        finally { await browser.CloseAsync(); pw.Dispose(); }
    }

    /// <summary>
    /// wikipedia (September; a timer adds a &lt;body&gt; class ≈1 s after load). With the clock paused (а‴), a 3 s wait inside
    /// the window changes nothing: determined, (1 excluded, 0 others). A DOM change inside the window is still caught:
    /// every attempt fails and survival is "undetermined" — never a silently different result.
    /// </summary>
    [RealPilotFact]
    public async Task Survival_window_with_the_clock_paused_holds_through_a_wait_and_catches_an_injected_mutation()
    {
        var (browser, pw, site, body, shim, cand, targets) = await SeptemberAsync("wikipedia.org");
        try
        {
            await RealPilotOffline.WarmUpAsync(browser, site.Url, body, site.Timestamp, shim);
            var (reference, _) = await RealPilotOffline.SeptemberReferenceLoadAsync(browser, site.Url, body, site.Timestamp, shim);
            var (marker, role, name) = targets[0];
            var locator = $"css:body:not(.jsl10n-visible) [data-oracle-id=\"{marker}\"]";
            var held = await RealPilotOffline.EvaluateSurvivalAsync(browser, site.Url, body, site.Timestamp, shim, cand,
                marker, role, name, locator, reference, insideWindow: _ => Task.Delay(3000));
            Assert.Equal("determined", held.Status);
            Assert.Equal(new RealPilotOffline.SurvivalWindow(1, 0, 1), held.Windows[^1]);

            var moved = await RealPilotOffline.EvaluateSurvivalAsync(browser, site.Url, body, site.Timestamp, shim, cand,
                marker, role, name, locator, reference,
                insideWindow: page => page.EvaluateAsync("() => document.body.classList.add('injected-by-test')"));
            Assert.Equal("undetermined", moved.Status);
            Assert.Null(moved.UniqueMatch);
            Assert.Equal(5, moved.Windows.Count);
            Assert.All(moved.Windows, w => Assert.True(w.Excluded == 1 && w.Others > 0, $"{w}"));
        }
        finally { await browser.CloseAsync(); pw.Dispose(); }
    }

    /// <summary>
    /// Addenda (е)/(е′) on a synthetic page whose timer changes the target button's class 1.5 s after load (after the
    /// network-idle wait). Paused right after the load: three cold reference loads give one hash, the window counts 0, and
    /// survival is determined on attempt 1 with pre-hash == reference. Pause skipped and a 2.5 s wait before the window
    /// (the timer fires there, where the window cannot see it): the pre-hash catches the change on every attempt →
    /// "undetermined", nothing evaluated. A wrong reference → "undetermined", never a determined value.
    /// </summary>
    [Fact]
    public async Task Survival_pre_hash_equals_the_reference_when_paused_and_catches_a_skipped_pause()
    {
        var rp = Path.Combine(Testbed.RepoRoot, "experiments", "results", "revision1", "real_pilot");
        var shim = await File.ReadAllTextAsync(Path.Combine(rp, "rp_shim_random.js"));
        var cand = await File.ReadAllTextAsync(Path.Combine(rp, "rp_candidates.js"));
        var fixedTime = new DateTime(2026, 9, 17, 4, 13, 5, DateTimeKind.Utc);
        const string url = "https://prehash.invalid/";
        var body = System.Text.Encoding.UTF8.GetBytes(@"<!doctype html><html><body><main>
            <button id=go class=before>Go</button><a href=/next>Next</a></main><script>
            setTimeout(function () { document.getElementById('go').className = 'after'; }, 1500);
            </script></body></html>");
        const string locator = "css:#go";
        using var pw = await Playwright.CreateAsync();

        var cold = new List<(string Sha, int Mutations)>();
        for (int c = 0; c < 3; c++)
        {
            var b = await RealPilotOffline.LaunchAsync(pw);
            try
            {
                await RealPilotOffline.WarmUpAsync(b, url, body, fixedTime, shim);
                cold.Add(await RealPilotOffline.SeptemberReferenceLoadAsync(b, url, body, fixedTime, shim));
            }
            finally { await b.CloseAsync(); }
        }
        Assert.Single(cold.Select(x => x.Sha).Distinct());
        Assert.All(cold, x => Assert.Equal(0, x.Mutations));
        var reference = cold[0].Sha;

        var browser = await RealPilotOffline.LaunchAsync(pw);
        try
        {
            await RealPilotOffline.WarmUpAsync(browser, url, body, fixedTime, shim);
            var unpaused = await RealPilotOffline.SeptemberReferenceLoadAsync(browser, url, body, fixedTime, shim,
                pauseClock: false, beforeWindow: _ => Task.Delay(2500));
            Assert.NotEqual(reference, unpaused.Sha256);                     // control: the timer changes the walk

            var ok = await RealPilotOffline.EvaluateSurvivalAsync(browser, url, body, fixedTime, shim, cand,
                "t_01", "button", "Go", locator, reference, insideWindow: _ => Task.Delay(2500));
            Assert.Equal("determined", ok.Status);
            Assert.Equal(1, ok.Attempts);
            Assert.Equal(new[] { reference }, ok.PreHashes);
            Assert.Equal(new RealPilotOffline.SurvivalWindow(1, 0, 1), ok.Windows[^1]);
            Assert.True(ok.UniqueMatch == true && ok.MatchesTarget == true);

            var skipped = await RealPilotOffline.EvaluateSurvivalAsync(browser, url, body, fixedTime, shim, cand,
                "t_01", "button", "Go", locator, reference, pauseClock: false, beforeWindow: _ => Task.Delay(2500));
            Assert.Equal("undetermined", skipped.Status);
            Assert.Null(skipped.UniqueMatch);
            Assert.Equal(5, skipped.PreHashes.Count);
            Assert.All(skipped.PreHashes, h => Assert.NotEqual(reference, h));
            Assert.All(skipped.Windows, w => Assert.Equal(-1, w.Matches));

            var wrong = await RealPilotOffline.EvaluateSurvivalAsync(browser, url, body, fixedTime, shim, cand,
                "t_01", "button", "Go", locator, new string('0', 64), maxAttempts: 2);
            Assert.Equal("undetermined", wrong.Status);
            Assert.Null(wrong.UniqueMatch);
            Assert.All(wrong.PreHashes, h => Assert.Equal(reference, h));
        }
        finally { await browser.CloseAsync(); }
    }
}
