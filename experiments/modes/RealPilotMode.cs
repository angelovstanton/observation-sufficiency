using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using BoundedAgents.Models;
using BoundedAgents.Experiments;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using BoundedAgents.Shared.Tokenizer;
using Microsoft.Playwright;

/// <summary>
/// Real-site pilot adapter (REAL_PILOT=probe|dump|shimcheck|survival|reference), zero LLM, zero network.
/// Rule: experiments/results/revision1/real_pilot/pilot_rule.md. Loads a cached, decoded HTML document
/// offline (Playwright route fulfils the first main-frame navigation, every other request is
/// aborted, WebSockets are not connected, service workers blocked, no host name resolves) and
/// runs the unchanged observation pipeline (Observation.BuildObservationAsync + encoders).
///
///   probe     — rp_candidates.js on the loaded DOM + the walked class/id values
///   dump      — the six cells, each on a fresh load with the site's data-oracle-id markers set by XPath
///               (RealPilotOffline.ObserveCellAsync, the paid run's function): manifest (o200k tokens,
///               sha256), full-prompt tokens per task, condition 5 per marker (B_full × F1 load)
///   shimcheck — the 24 corpus pages, six cells (fresh load per cell), with and without the shims
///   survival  — pilot_analysis_plan.md "Secondary: survival": the September page loaded the same way (shims,
///               clock at the September record), a new fresh load per stored locator (addendum (д)): inside
///               a mutation window, the target by role + accessible name, its Oracle marker, the locator
///               resolved (Oracle.EvaluateLocatorAsync, resolution only): unique match and that element;
///               ≤ 5 attempts, else "undetermined" (unstable DOM). Each attempt first checks the B_full × F1
///               pre-hash against the site's September reference (addendum (е)). Stops with exit 5 / 6 on the
///               load rule (е) point 3 / more than 5% undetermined (е″). Input: real_pilot/rp_survival.py
///   reference — addendum (е′): per site, ColdLoads cold loads (new browser, warm-up, the survival load, clock
///               paused, the B_full × F1 walk hashed). Input: real_pilot/rp_survival.py reference
///
/// Env: BAR_RP_INPUT (JSON written by the real_pilot/*.py scripts), BAR_RP_OUT (output dir).
/// </summary>
internal static class RealPilotMode
{
    private static readonly (string Bundle, string Encoding)[] Cells =
    {
        ("B_full", "F1"), ("B_noVolatileConsistent", "F1"), ("B_full_minus_volClass", "F1"),
        ("B_full", "F3"), ("B_noVolatileConsistent", "F3"), ("B_full_minus_volClass", "F3"),
    };

    private sealed record Marker(string Id, string Xpath, string[] SignalAttrs);

    private sealed record Site(string Key, string Url, string HtmlPath, DateTime? Timestamp,
                               string[] VolIds, string[] VolClasses, Marker[] Markers, string[] Tasks);

    private sealed record Input(Site[] Sites, bool Shims, bool WriteObs);

    private sealed record SurvivalLocator(string EventKey, string Marker, string LocatorRaw);

    /// <summary>A September target (addendum (д)): found on every load by role + accessible name, no XPath.</summary>
    private sealed record SurvivalTarget(string Id, string Role, string Name);

    private sealed record SurvivalSite(string Key, string Url, string HtmlPath, DateTime Timestamp, string ReferenceSha,
                                       SurvivalTarget[] Targets, SurvivalLocator[] Locators);

    private sealed record SurvivalInput(SurvivalSite[] Sites);

    /// <summary>A September page whose reference (addendum (е′)) is generated: ColdLoads browser starts.</summary>
    private sealed record ReferenceSite(string Key, string Url, string HtmlPath, DateTime Timestamp);

    private sealed record ReferenceInput(ReferenceSite[] Sites, int ColdLoads);

    /// <summary>Survival stop codes: (е) point 3 load rule; (е″) point 4, more than 5% undetermined.</summary>
    internal const int ExitLoadRule = 5, ExitUndetermined = 6;

    private static readonly JsonSerializerOptions JsonIn = new() { PropertyNameCaseInsensitive = true };
    private static readonly JsonSerializerOptions JsonOut = new() { WriteIndented = false };

    public static async Task<int> RunAsync(string mode)
    {
        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var pilotDir = Path.Combine(repoRoot, "experiments", "results", "revision1", "real_pilot");
        var outDir = Environment.GetEnvironmentVariable("BAR_RP_OUT")
                     ?? throw new InvalidOperationException("BAR_RP_OUT not set");
        Directory.CreateDirectory(outDir);
        var candidatesJs = await File.ReadAllTextAsync(Path.Combine(pilotDir, "rp_candidates.js"));
        var shimJs = await File.ReadAllTextAsync(Path.Combine(pilotDir, "rp_shim_random.js"));

        using var playwright = await Playwright.CreateAsync();
        if (mode == "reference")
        {
            // Every reference load starts its own browser (a cold load, addendum (е′) point 2).
            var refPath = Environment.GetEnvironmentVariable("BAR_RP_INPUT")
                          ?? throw new InvalidOperationException("BAR_RP_INPUT not set");
            var refInput = JsonSerializer.Deserialize<ReferenceInput>(await File.ReadAllTextAsync(refPath), JsonIn)!;
            return await ReferenceAsync(playwright, refInput, outDir, shimJs);
        }
        var browser = await RealPilotOffline.LaunchAsync(playwright);
        try
        {
            switch (mode)
            {
                case "shimcheck":
                    return await ShimCheckAsync(browser, repoRoot, outDir, shimJs);
                case "survival":
                    var survivalPath = Environment.GetEnvironmentVariable("BAR_RP_INPUT")
                                       ?? throw new InvalidOperationException("BAR_RP_INPUT not set");
                    var survivalInput = JsonSerializer.Deserialize<SurvivalInput>(
                        await File.ReadAllTextAsync(survivalPath), JsonIn)!;
                    return await SurvivalAsync(browser, survivalInput, outDir, shimJs, candidatesJs);
                case "probe":
                case "dump":
                    var inputPath = Environment.GetEnvironmentVariable("BAR_RP_INPUT")
                                    ?? throw new InvalidOperationException("BAR_RP_INPUT not set");
                    var input = JsonSerializer.Deserialize<Input>(await File.ReadAllTextAsync(inputPath), JsonIn)!;
                    return mode == "probe"
                        ? await ProbeAsync(browser, input, outDir, candidatesJs, shimJs)
                        : await DumpAsync(browser, input, outDir, shimJs);
                default:
                    Console.Error.WriteLine($"REAL_PILOT: unknown mode '{mode}' (probe|dump|shimcheck|survival|reference)");
                    return 2;
            }
        }
        finally { await browser.CloseAsync(); }
    }

    // Helpers; the offline load itself (pilot_rule.md §2 (б)) is in experiments/RealPilotOffline.cs
    private static string Sha(string s) =>
        Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();

    private static string OneLine(Exception e) =>
        Regex.Replace($"{e.GetType().Name}: {e.Message}", @"\s+", " ").Trim();

    // Probe
    private static async Task<int> ProbeAsync(IBrowser browser, Input input, string outDir,
                                              string candidatesJs, string shimJs)
    {
        foreach (var site in input.Sites)
        {
            object result;
            IBrowserContext? ctx = null;
            try
            {
                var (c, page, stats) = await RealPilotOffline.LoadAsync(browser, site.Url, await File.ReadAllBytesAsync(site.HtmlPath),
                                                       site.Timestamp, input.Shims ? shimJs : null);
                ctx = c;
                var cand = await page.EvaluateAsync<JsonElement>(candidatesJs);
                var walked = await Observation.WalkDomAsync(page);
                var classAttrs = new SortedSet<string>(StringComparer.Ordinal);
                var ids = new SortedSet<string>(StringComparer.Ordinal);
                foreach (var el in walked)
                {
                    if (el.Attrs.TryGetValue("class", out var cv) && !string.IsNullOrEmpty(cv)) classAttrs.Add(cv);
                    if (el.Attrs.TryGetValue("id", out var iv) && !string.IsNullOrEmpty(iv)) ids.Add(iv);
                }
                result = new
                {
                    key = site.Key, ok = true, error = (string?)null,
                    load = new { fulfilled = stats.Fulfilled, aborted = stats.Aborted, websockets = stats.WebSockets, ws_frames_received = stats.WsFramesReceived },
                    walked_elements = walked.Count, class_attrs = classAttrs, ids, candidates = cand,
                };
            }
            catch (Exception e)
            {
                result = new { key = site.Key, ok = false, error = OneLine(e) };
            }
            finally
            {
                if (ctx is not null) await ctx.CloseAsync();
            }
            await File.WriteAllTextAsync(Path.Combine(outDir, $"{site.Key}.probe.json"),
                                         JsonSerializer.Serialize(result, JsonOut));
            Console.WriteLine($"  probe {site.Key}");
        }
        return 0;
    }

    // Dump
    private static async Task<int> DumpAsync(IBrowser browser, Input input, string outDir, string shimJs)
    {
        var manifest = Path.Combine(outDir, "manifest.tsv");
        var prompts = Path.Combine(outDir, "prompt_tokens.tsv");
        var cond5 = Path.Combine(outDir, "cond5.tsv");
        var sites = Path.Combine(outDir, "sites.tsv");
        await File.WriteAllTextAsync(manifest, "site\tbundle\tencoding\ttokens\tsha256\tdata_oracle_hits\n");
        await File.WriteAllTextAsync(prompts, "site\tbundle\tencoding\ttask_index\tprompt_tokens\n");
        await File.WriteAllTextAsync(cond5, "site\tmarker\tfound\tcondition5_B_full\n");
        await File.WriteAllTextAsync(sites,
            "site\tok\terror\tfulfilled\taborted\twebsockets\tws_frames_received\tmarkers_set\tnvc_extra_class\tnvc_extra_id\tloads\n");
        var systemTokens = TokenCounter.CountTokens(GroundingRunner.SystemPrompt);

        foreach (var site in input.Sites)
        {
            try
            {
                // Observation protocol (pilot_rule.md addendum 2026-10-13): every cell on a fresh load, through
                // RealPilotOffline.ObserveCellAsync, the function the paid run uses (experiments/batch PilotExecutor).
                var body = await File.ReadAllBytesAsync(site.HtmlPath);
                var markers = site.Markers.Select(m => (m.Id, m.Xpath)).ToArray();
                var volIds = new HashSet<string>(site.VolIds, StringComparer.Ordinal);
                var volCls = new HashSet<string>(site.VolClasses, StringComparer.Ordinal);
                var stats = new RealPilotOffline.LoadStats();
                var markersSet = int.MaxValue;
                var loads = 0;

                var rows = new StringBuilder();
                var promptRows = new StringBuilder();
                IReadOnlyList<ElementData>? raw = null;   // B_full × F1 load: condition 5, NVC extras
                foreach (var (bundle, encoding) in Cells)
                {
                    var (ctx, _, s, set, obsText, rawWithAnchors) = await RealPilotOffline.ObserveCellAsync(
                        browser, site.Url, body, site.Timestamp, input.Shims ? shimJs : null, markers,
                        bundle, encoding, volIds, volCls);
                    await ctx.CloseAsync();
                    loads++;
                    stats.Fulfilled += s.Fulfilled;
                    stats.Aborted += s.Aborted;
                    stats.WebSockets += s.WebSockets;
                    stats.WsFramesReceived += s.WsFramesReceived;
                    markersSet = Math.Min(markersSet, set);
                    if (bundle == "B_full" && encoding == "F1")
                    {
                        raw = rawWithAnchors;
                    }
                    if (input.WriteObs)
                    {
                        await File.WriteAllTextAsync(Path.Combine(outDir, $"{site.Key}__{bundle}__{encoding}.txt"), obsText);
                    }
                    var hits = Regex.Matches(obsText, "data-oracle", RegexOptions.IgnoreCase).Count;
                    rows.Append($"{site.Key}\t{bundle}\t{encoding}\t{TokenCounter.CountTokens(obsText)}\t{Sha(obsText)}\t{hits}\n");
                    for (var i = 0; i < site.Tasks.Length; i++)
                    {
                        var pt = systemTokens + TokenCounter.CountTokens(GroundingRunner.BuildUserPrompt(obsText, site.Tasks[i]));
                        promptRows.Append($"{site.Key}\t{bundle}\t{encoding}\t{i}\t{pt}\n");
                    }
                }

                // Condition 5 per marker, the call Oracle.EvaluateLocatorAsync makes (B_full set).
                var c5 = new StringBuilder();
                var fullSet = AttributeBundles.ResolveBundleSetForSignalCheck("B_full");
                foreach (var m in site.Markers)
                {
                    var el = raw!.FirstOrDefault(e => e.Attrs.TryGetValue("data-oracle-id", out var v) && v == m.Id);
                    var p = Oracle.ComputeStableSignalPresence(m.SignalAttrs, a => fullSet.Contains(a), el, volIds, volCls);
                    c5.Append($"{site.Key}\t{m.Id}\t{el is not null}\t{p}\n");
                }

                // Values the NVC path strips beyond the CLI lists (selector-level predicate hits).
                var extraCls = new HashSet<string>(StringComparer.Ordinal);
                var extraIds = new HashSet<string>(StringComparer.Ordinal);
                foreach (var el in raw!)
                {
                    if (el.Attrs.TryGetValue("class", out var cv) && !string.IsNullOrEmpty(cv))
                    {
                        foreach (var tok in cv.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                        {
                            if (!volCls.Contains(tok) && AttributeBundles.PredicateFlagsClassToken(tok, volIds, volCls))
                                extraCls.Add(tok);
                        }
                    }
                    if (el.Attrs.TryGetValue("id", out var iv) && !string.IsNullOrEmpty(iv)
                        && !volIds.Contains(iv) && AttributeBundles.PredicateFlagsId(iv, volIds, volCls))
                    {
                        extraIds.Add(iv);
                    }
                }

                await File.AppendAllTextAsync(manifest, rows.ToString());
                await File.AppendAllTextAsync(prompts, promptRows.ToString());
                await File.AppendAllTextAsync(cond5, c5.ToString());
                await File.AppendAllTextAsync(sites,
                    $"{site.Key}\tTrue\t\t{stats.Fulfilled}\t{stats.Aborted}\t{stats.WebSockets}\t{stats.WsFramesReceived}\t{markersSet}\t{extraCls.Count}\t{extraIds.Count}\t{loads}\n");
                await File.WriteAllTextAsync(Path.Combine(outDir, $"{site.Key}.nvc_extra.json"),
                    JsonSerializer.Serialize(new { classes = extraCls.OrderBy(x => x, StringComparer.Ordinal),
                                                   ids = extraIds.OrderBy(x => x, StringComparer.Ordinal) }, JsonOut));
            }
            catch (Exception e)
            {
                await File.AppendAllTextAsync(sites, $"{site.Key}\tFalse\t{OneLine(e)}\t\t\t\t\t\t\t\t\n");
            }
            Console.WriteLine($"  dump {site.Key}");
        }
        return 0;
    }

    // Survival (September page; resolution only; addendum (д))
    private static async Task<int> SurvivalAsync(IBrowser browser, SurvivalInput input, string outDir, string shimJs,
                                                 string candidatesJs)
    {
        var results = Path.Combine(outDir, "survival.tsv");
        var sites = Path.Combine(outDir, "survival_sites.tsv");
        await File.WriteAllTextAsync(results,
            "site\tevent_key\tmarker\tlocator_type\tunique_match\tmatches_target\tstatus\tattempts\twindows\tpre_hashes\n");
        await File.WriteAllTextAsync(sites, "site\tok\terror\tlocators\tdetermined\tundetermined\n");
        bool warm = false;
        // Stop rules: (е) point 3 — more than 10 of the first 100 evaluations need more than one load; (е″) point 4 —
        // more than 5% of all locators undetermined. Checked after every locator; the output of a stopped run is not used.
        var total = input.Sites.Sum(s => s.Locators.Length);
        int evaluated = 0, retriedInFirst100 = 0, undeterminedAll = 0;
        foreach (var site in input.Sites)
        {
            try
            {
                var body = await File.ReadAllBytesAsync(site.HtmlPath);
                if (!warm)
                {
                    // Addendum (а″)/(д): one warm-up load after the browser start, not evaluated.
                    await RealPilotOffline.WarmUpAsync(browser, site.Url, body, site.Timestamp, shimJs);
                    warm = true;
                }
                var targets = site.Targets.ToDictionary(t => t.Id, StringComparer.Ordinal);
                var rows = new StringBuilder();
                int determined = 0, undetermined = 0;
                foreach (var l in site.Locators)
                {
                    // A new fresh load per locator; pre-hash == the site's reference (е), then the target by role +
                    // name inside the mutation window.
                    var t = targets[l.Marker];
                    var r = await RealPilotOffline.EvaluateSurvivalAsync(browser, site.Url, body, site.Timestamp, shimJs,
                        candidatesJs, t.Id, t.Role, t.Name, l.LocatorRaw, site.ReferenceSha);
                    var (type, _) = GroundingRunner.ParseLocatorForReplay(l.LocatorRaw);
                    if (r.Status == "determined") determined++; else { undetermined++; undeterminedAll++; }
                    rows.Append($"{site.Key}\t{l.EventKey}\t{l.Marker}\t{type}\t{r.UniqueMatch}\t{r.MatchesTarget}\t{r.Status}\t" +
                                $"{r.Attempts}\t{string.Join(",", r.Windows.Select(w => $"{w.Excluded}/{w.Others}/{w.Matches}"))}\t" +
                                $"{string.Join(",", r.PreHashes)}\n");
                    evaluated++;
                    if (evaluated <= 100 && r.Attempts > 1) retriedInFirst100++;
                    string? stop = retriedInFirst100 > 10
                        ? $"load rule (е) point 3: {retriedInFirst100} of the first {Math.Min(evaluated, 100)} evaluations needed more than one load"
                        : undeterminedAll * 20 > total
                            ? $"(е″) point 4: {undeterminedAll} undetermined > 5% of {total} locators"
                            : null;
                    if (stop is not null)
                    {
                        await File.AppendAllTextAsync(results, rows.ToString());
                        await File.WriteAllTextAsync(Path.Combine(outDir, "STOPPED.txt"), stop + "\n");
                        Console.Error.WriteLine($"[survival] STOPPED after {evaluated}/{total}: {stop}");
                        return retriedInFirst100 > 10 ? ExitLoadRule : ExitUndetermined;
                    }
                }
                await File.AppendAllTextAsync(results, rows.ToString());
                await File.AppendAllTextAsync(sites, $"{site.Key}\tTrue\t\t{site.Locators.Length}\t{determined}\t{undetermined}\n");
            }
            catch (Exception e)
            {
                await File.AppendAllTextAsync(sites, $"{site.Key}\tFalse\t{OneLine(e)}\t{site.Locators.Length}\t\t\n");
            }
            Console.WriteLine($"  survival {site.Key}");
        }
        return 0;
    }

    // Reference (addenda (е), (е′)): the September B_full × F1 pre-hash, ColdLoads cold loads per site
    private static async Task<int> ReferenceAsync(IPlaywright playwright, ReferenceInput input, string outDir, string shimJs)
    {
        var results = Path.Combine(outDir, "reference.tsv");
        await File.WriteAllTextAsync(results, "site\tcold\tsha256\tmutations\tutc\terror\n");
        foreach (var site in input.Sites)
        {
            var body = await File.ReadAllBytesAsync(site.HtmlPath);
            for (int c = 1; c <= input.ColdLoads; c++)
            {
                // A cold load: a new browser start, the warm-up load (а″), then the reference load.
                var browser = await RealPilotOffline.LaunchAsync(playwright);
                string row;
                try
                {
                    await RealPilotOffline.WarmUpAsync(browser, site.Url, body, site.Timestamp, shimJs);
                    var (sha, mutations) = await RealPilotOffline.SeptemberReferenceLoadAsync(
                        browser, site.Url, body, site.Timestamp, shimJs);
                    row = $"{site.Key}\t{c}\t{sha}\t{mutations}\t{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\t\n";
                }
                catch (Exception e)
                {
                    row = $"{site.Key}\t{c}\t\t\t{DateTime.UtcNow:yyyy-MM-ddTHH:mm:ssZ}\t{OneLine(e)}\n";
                }
                finally
                {
                    await browser.CloseAsync();
                }
                await File.AppendAllTextAsync(results, row);
            }
            Console.WriteLine($"  reference {site.Key}");
        }
        return 0;
    }

    // Shimcheck (corpus pages, with vs without shims)
    private static async Task<int> ShimCheckAsync(IBrowser browser, string repoRoot, string outDir, string shimJs)
    {
        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var manifest = Path.Combine(outDir, "shimcheck.tsv");
        await File.WriteAllTextAsync(manifest, "page\tshims\tbundle\tencoding\ttokens\tsha256\n");
        var fixedTime = new DateTime(2026, 5, 15, 0, 0, 0, DateTimeKind.Utc);
        foreach (var n in Enumerable.Range(1, 24))
        {
            var pageId = $"page_{n:D2}";
            var truth = JsonSerializer.Deserialize<TruthFile>(
                await File.ReadAllTextAsync(Path.Combine(testbedDir, "pages", $"{pageId}.truth.json")), JsonIn)!;
            var volIds = new HashSet<string>(truth.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
            var volCls = new HashSet<string>(truth.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
            var body = await File.ReadAllBytesAsync(Path.Combine(testbedDir, "pages", $"{pageId}.html"));
            var url = $"{Config.TestbedBaseUrl.TrimEnd('/')}/pages/{pageId}.html";
            foreach (var shims in new[] { false, true })
            {
                // Same observation protocol as the dump: a fresh load per cell (no markers on corpus pages).
                var rows = new StringBuilder();
                foreach (var (bundle, encoding) in Cells)
                {
                    var (ctx, _, _, _, obsText, _) = await RealPilotOffline.ObserveCellAsync(
                        browser, url, body, fixedTime, shims ? shimJs : null, Array.Empty<(string, string)>(),
                        bundle, encoding, volIds, volCls);
                    await ctx.CloseAsync();
                    rows.Append($"{pageId}\t{shims}\t{bundle}\t{encoding}\t{TokenCounter.CountTokens(obsText)}\t{Sha(obsText)}\n");
                }
                await File.AppendAllTextAsync(manifest, rows.ToString());
            }
            Console.WriteLine($"  shimcheck {pageId}");
        }
        return 0;
    }
}
