using System.Security.Cryptography;
using System.Text.Json;
using BoundedAgents.Experiments;
using BoundedAgents.Experiments.Batch;
using Microsoft.Playwright;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// Addenda (е) / (е′) / (е″) against the committed September reference (real_pilot/survival_reference.json, pinned
/// below), offline, no model, no pilot record. (a) One reference load per site gives the committed hash on all 33
/// sites. (b) On the three timer sites (wikipedia, kaspersky, mobile.de), every unique September target survives with
/// the same determined result in three orders — as-is, reversed, a 5 s wait inside the window — and attempt 1's
/// pre-hash equals the reference. (c) With the pause skipped and a wait before the window, the pre-hash catches the
/// change; survival is then undetermined, never a different determined value. (d) Under parallel CPU load (one
/// spinning thread per core), determined results equal the unloaded ones; a failing pre-hash gives undetermined only.
/// Needs the decoded September HTML next to the repo; fails if it is missing.
/// </summary>
[Trait("Category", "RealPilot")]
public sealed class PilotSurvivalReferenceTests
{
    /// <summary>sha256 of real_pilot/survival_reference.json as committed (the analysis pins the same value).</summary>
    private const string ReferenceFileSha = "d115fe48f201bea1e2291563d511efc0ca8ef6c16e0ae37c1965c364af79b1b3";

    /// <summary>Reference is null for a site marked "undetermined (no stable reference)" (е′ point 3, е‴).</summary>
    private sealed record Site(string Key, string Domain, string Url, DateTime Timestamp, byte[] Body, string? Reference,
                               List<(string Marker, string Role, string Name)> Targets);

    private static readonly string Rp = Path.Combine(Testbed.RepoRoot, "experiments", "results", "revision1", "real_pilot");

    private static async Task<(List<Site> Sites, string Shim, string Cand)> LoadAsync()
    {
        var refPath = Path.Combine(Rp, "survival_reference.json");
        Assert.Equal(ReferenceFileSha,
            Convert.ToHexString(SHA256.HashData(await File.ReadAllBytesAsync(refPath))).ToLowerInvariant());
        var reference = JsonDocument.Parse(await File.ReadAllTextAsync(refPath)).RootElement.GetProperty("sites")
            .EnumerateArray().ToDictionary(s => s.GetProperty("key").GetString()!, s => s);
        var st = JsonDocument.Parse(await File.ReadAllTextAsync(Path.Combine(Rp, "survival_targets.json"))).RootElement;
        var htmlDir = Path.Combine(Path.GetDirectoryName(PilotPins.Production(Testbed.RepoRoot).HtmlDir)!, "CC-MAIN-2026-39");
        Assert.True(Directory.Exists(htmlDir), $"September HTML missing: {htmlDir}");
        var sites = new List<Site>();
        foreach (var s in st.GetProperty("sites").EnumerateArray())
        {
            var key = s.GetProperty("key").GetString()!;
            var domain = s.GetProperty("domain").GetString()!;
            var r = reference[key];
            var stable = r.GetProperty("stable").GetBoolean();
            Assert.True(stable || r.GetProperty("status").GetString() == "undetermined (no stable reference)",
                $"{key}: neither stable nor marked undetermined (no stable reference)");
            var targets = st.GetProperty("items").EnumerateArray()
                .Where(t => t.GetProperty("domain").GetString() == domain && t.GetProperty("status").GetString() == "unique")
                .Select(t => (t.GetProperty("marker").GetString()!, t.GetProperty("role").GetString()!,
                              t.GetProperty("name").GetString()!))
                .ToList();
            sites.Add(new Site(key, domain, s.GetProperty("url").GetString()!,
                s.GetProperty("timestamp").GetDateTime().ToUniversalTime(),
                await File.ReadAllBytesAsync(Path.Combine(htmlDir, s.GetProperty("html_file").GetString()!)),
                stable ? r.GetProperty("reference_sha256").GetString()! : null, targets));
        }
        Assert.Equal(33, sites.Count);
        return (sites, await File.ReadAllTextAsync(Path.Combine(Rp, "rp_shim_random.js")),
                await File.ReadAllTextAsync(Path.Combine(Rp, "rp_candidates.js")));
    }

    private static string Locator(string marker) => $"css:[data-oracle-id=\"{marker}\"]";

    [RealPilotFact]
    public async Task Pre_hash_equals_the_committed_reference_on_all_33_sites()
    {
        var (sites, shim, _) = await LoadAsync();
        using var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        try
        {
            await RealPilotOffline.WarmUpAsync(browser, sites[0].Url, sites[0].Body, sites[0].Timestamp, shim);
            var diff = new List<string>();
            Assert.True(sites.Count(s => s.Reference != null) >= 30, "fewer than 30 stable references");
            foreach (var s in sites.Where(s => s.Reference != null))
            {
                var (sha, mutations) = await RealPilotOffline.SeptemberReferenceLoadAsync(browser, s.Url, s.Body, s.Timestamp, shim);
                if (sha != s.Reference) diff.Add($"{s.Key}: {sha} != {s.Reference} (mutations {mutations})");
            }
            Assert.True(diff.Count == 0, string.Join("\n", diff));
        }
        finally { await browser.CloseAsync(); }
    }

    private static async Task<Dictionary<string, (bool? Um, bool? Mt, string Status, int Attempts, string Pre0)>> SurvivalAsync(
        IBrowser browser, Site s, string shim, string cand, IEnumerable<(string Marker, string Role, string Name)> targets,
        Func<IPage, Task>? insideWindow = null, bool pauseClock = true, Func<IPage, Task>? beforeWindow = null)
    {
        var res = new Dictionary<string, (bool?, bool?, string, int, string)>();
        foreach (var (marker, role, name) in targets)
        {
            var r = await RealPilotOffline.EvaluateSurvivalAsync(browser, s.Url, s.Body, s.Timestamp, shim, cand,
                marker, role, name, Locator(marker), s.Reference!, insideWindow: insideWindow, pauseClock: pauseClock,
                beforeWindow: beforeWindow);
            res[marker] = (r.UniqueMatch, r.MatchesTarget, r.Status, r.Attempts, r.PreHashes[0]);
        }
        return res;
    }

    [RealPilotTheory]
    [InlineData("wikipedia.org")]
    [InlineData("kaspersky.com")]
    [InlineData("mobile.de")]
    public async Task Survival_on_a_timer_site_gives_the_same_result_as_is_reversed_and_with_a_5s_wait(string domain)
    {
        var (sites, shim, cand) = await LoadAsync();
        var s = sites.Single(x => x.Domain == domain);
        Assert.NotEmpty(s.Targets);
        using var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        try
        {
            await RealPilotOffline.WarmUpAsync(browser, s.Url, s.Body, s.Timestamp, shim);
            var asIs = await SurvivalAsync(browser, s, shim, cand, s.Targets);
            var reversed = await SurvivalAsync(browser, s, shim, cand, Enumerable.Reverse(s.Targets));
            var waited = await SurvivalAsync(browser, s, shim, cand, s.Targets, insideWindow: _ => Task.Delay(5000));
            foreach (var run in new[] { asIs, reversed, waited })
            {
                Assert.All(run.Values, r =>
                {
                    Assert.Equal("determined", r.Status);
                    Assert.Equal(s.Reference, r.Pre0);
                    Assert.True(r.Um == true && r.Mt == true);
                });
            }
            Assert.Equal(asIs.ToDictionary(x => x.Key, x => (x.Value.Um, x.Value.Mt)),
                         reversed.ToDictionary(x => x.Key, x => (x.Value.Um, x.Value.Mt)));
            Assert.Equal(asIs.ToDictionary(x => x.Key, x => (x.Value.Um, x.Value.Mt)),
                         waited.ToDictionary(x => x.Key, x => (x.Value.Um, x.Value.Mt)));
        }
        finally { await browser.CloseAsync(); }
    }

    [RealPilotTheory]
    [InlineData("wikipedia.org", true)]
    [InlineData("kaspersky.com", true)]
    [InlineData("mobile.de", true)]
    public async Task With_the_pause_skipped_the_pre_hash_catches_the_change(string domain, bool domChanges)
    {
        var (sites, shim, cand) = await LoadAsync();
        var s = sites.Single(x => x.Domain == domain);
        using var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        try
        {
            await RealPilotOffline.WarmUpAsync(browser, s.Url, s.Body, s.Timestamp, shim);
            Func<IPage, Task> wait = _ => Task.Delay(3000);
            var (unpaused, _) = await RealPilotOffline.SeptemberReferenceLoadAsync(browser, s.Url, s.Body, s.Timestamp, shim,
                pauseClock: false, beforeWindow: wait);
            var skipped = await SurvivalAsync(browser, s, shim, cand, s.Targets.Take(3), pauseClock: false, beforeWindow: wait);
            if (domChanges)
            {
                Assert.NotEqual(s.Reference, unpaused);
                Assert.All(skipped.Values, r => { Assert.Equal("undetermined", r.Status); Assert.Null(r.Um); });
            }
            else
            {
                // The page's timers do not change this walk within the wait: nothing to catch; the result stays the
                // paused one (never a different determined value).
                Assert.Equal(s.Reference, unpaused);
                Assert.All(skipped.Values, r => Assert.True(r.Status == "undetermined" || (r.Um == true && r.Mt == true)));
            }
        }
        finally { await browser.CloseAsync(); }
    }

    [RealPilotFact]
    public async Task Under_parallel_cpu_load_determined_results_do_not_change()
    {
        var (sites, shim, cand) = await LoadAsync();
        using var pw = await Playwright.CreateAsync();
        var browser = await RealPilotOffline.LaunchAsync(pw);
        try
        {
            var timer = sites.Where(x => x.Domain is "wikipedia.org" or "kaspersky.com" or "mobile.de").ToList();
            await RealPilotOffline.WarmUpAsync(browser, timer[0].Url, timer[0].Body, timer[0].Timestamp, shim);
            var quiet = new Dictionary<string, (bool? Um, bool? Mt, string Status, int Attempts, string Pre0)>();
            foreach (var s in timer)
                foreach (var kv in await SurvivalAsync(browser, s, shim, cand, s.Targets)) quiet[$"{s.Key}|{kv.Key}"] = kv.Value;

            using var stop = new CancellationTokenSource();
            var spinners = Enumerable.Range(0, Environment.ProcessorCount).Select(_ => Task.Factory.StartNew(() =>
            {
                double x = 0;
                while (!stop.IsCancellationRequested) x = Math.Sqrt(x + 1.0);
                return x;
            }, TaskCreationOptions.LongRunning)).ToArray();
            var loaded = new Dictionary<string, (bool? Um, bool? Mt, string Status, int Attempts, string Pre0)>();
            try
            {
                foreach (var s in timer)
                    foreach (var kv in await SurvivalAsync(browser, s, shim, cand, s.Targets)) loaded[$"{s.Key}|{kv.Key}"] = kv.Value;
            }
            finally
            {
                stop.Cancel();
                await Task.WhenAll(spinners);
            }
            Assert.Equal(quiet.Keys.OrderBy(k => k), loaded.Keys.OrderBy(k => k));
            var differ = loaded.Where(kv => kv.Value.Status == "determined" && quiet[kv.Key].Status == "determined"
                                            && (kv.Value.Um, kv.Value.Mt) != (quiet[kv.Key].Um, quiet[kv.Key].Mt))
                               .Select(kv => kv.Key).ToList();
            Assert.True(differ.Count == 0, "determined results changed under load: " + string.Join(", ", differ));
            Assert.All(loaded.Values, r => Assert.True(r.Status == "undetermined" || r.Um == true && r.Mt == true));
        }
        finally { await browser.CloseAsync(); }
    }
}
