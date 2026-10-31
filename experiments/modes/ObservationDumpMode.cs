using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using BoundedAgents.Shared.Tokenizer;

/// <summary>
/// Observation dump (DUMP_OBSERVATIONS=1), zero LLM.
/// For every page: B_full×F1 (token census source), B_noVolatile and B_noVolatileConsistent
/// × F0–F3, built with Observation.BuildObservationAsync. Writes the observation texts, a
/// manifest (o200k_base tokens + sha256) and a census of every distinct class/id token of
/// the raw DOM walk with the predicate's verdict on it.
///
/// Guard: every class/id token left in a B_noVolatileConsistent observation is re-checked
/// with the predicate (AttributeBundles.PredicateFlags*, i.e. Oracle.LocatorUsesVolatileSignal);
/// any flagged token is a violation and the mode exits with code 2.
///
/// Env: BAR_DUMP_DIR (default experiments/results/revision1/observations), BAR_PAGE_IDS (default all 24).
/// </summary>
internal static class ObservationDumpMode
{
    private static readonly string[] DomEncodings = { "F0", "F1", "F2", "F3" };

    public static async Task<int> RunAsync()
    {
        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var outDir = Environment.GetEnvironmentVariable("BAR_DUMP_DIR")
                     ?? Path.Combine(repoRoot, "experiments", "results", "revision1", "observations");
        var pageIds = (Environment.GetEnvironmentVariable("BAR_PAGE_IDS")
                       ?? string.Join(",", Enumerable.Range(1, 24).Select(n => $"page_{n:D2}")))
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        if (Directory.Exists(outDir))
        {
            Directory.Delete(outDir, recursive: true);
        }
        Directory.CreateDirectory(outDir);
        var manifestPath = Path.Combine(outDir, "manifest.tsv");
        await File.WriteAllTextAsync(manifestPath, "page\tbundle\tencoding\ttokens\tsha256\n");

        var cells = new List<(string Bundle, string Encoding)> { ("B_full", "F1") };
        cells.AddRange(DomEncodings.Select(e => ("B_noVolatile", e)));
        cells.AddRange(DomEncodings.Select(e => ("B_noVolatileConsistent", e)));

        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var port = new Uri(Config.TestbedBaseUrl).Port;
        var server = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        server.BeginOutputReadLine();   // drain: an unread pipe blocks http.server
        server.BeginErrorReadLine();
        await Task.Delay(1200);

        var census = new List<object>();
        var signalRows = new List<object>();   // per target × encoding × bundle: condition 5 + signal values
        var violations = new List<string>();
        try
        {
            using var playwright = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await playwright.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                foreach (var pageId in pageIds)
                {
                    var truth = JsonSerializer.Deserialize<TruthFile>(
                        await File.ReadAllTextAsync(Path.Combine(testbedDir, "pages", $"{pageId}.truth.json")),
                        new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
                    var volIds = new HashSet<string>(truth.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
                    var volCls = new HashSet<string>(truth.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);

                    var page = await browser.NewPageAsync();
                    await page.GotoAsync($"{Config.TestbedBaseUrl.TrimEnd('/')}/pages/{pageId}.html",
                                         new() { Timeout = 90_000 });
                    await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle,
                                                     new() { Timeout = 90_000 });

                    foreach (var (bundle, encoding) in cells)
                    {
                        var (obsText, raw, filtered) = await Observation.BuildObservationAsync(
                            page, bundle, encoding, volIds, volCls);
                        await File.WriteAllTextAsync(Path.Combine(outDir, $"{pageId}__{bundle}__{encoding}.txt"), obsText);
                        var sha = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(obsText))).ToLowerInvariant();
                        await File.AppendAllTextAsync(manifestPath,
                            $"{pageId}\t{bundle}\t{encoding}\t{TokenCounter.CountTokens(obsText)}\t{sha}\n");

                        if (bundle is "B_noVolatile" or "B_noVolatileConsistent")
                        {
                            var signalSet = AttributeBundles.ResolveBundleSetForSignalCheck(bundle);
                            foreach (var t in truth.Targets)
                            {
                                var oracleEl = raw.FirstOrDefault(e =>
                                    e.Attrs.TryGetValue("data-oracle-id", out var oid) && oid == t.Oracle);
                                // Same call Oracle.EvaluateLocatorAsync makes for condition 5.
                                bool cond5 = Oracle.ComputeStableSignalPresence(
                                    t.SignalAttrs, a => signalSet.Contains(a), oracleEl, volIds, volCls);
                                var signals = new List<object>();
                                foreach (var attr in t.SignalAttrs.Where(a => a is "id" or "class"))
                                {
                                    var val = oracleEl?.Attrs.GetValueOrDefault(attr) ?? "";
                                    var tokens = attr == "class"
                                        ? val.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                                        : (val.Length > 0 ? new[] { val } : Array.Empty<string>());
                                    foreach (var tok in tokens)
                                    {
                                        signals.Add(new
                                        {
                                            attr, value = tok,
                                            listed = attr == "id" ? volIds.Contains(tok) : volCls.Contains(tok),
                                            predicate_flags = attr == "id"
                                                ? AttributeBundles.PredicateFlagsId(tok, volIds, volCls)
                                                : AttributeBundles.PredicateFlagsClassToken(tok, volIds, volCls),
                                        });
                                    }
                                }
                                signalRows.Add(new
                                {
                                    page = pageId, task_id = t.Id, encoding, bundle,
                                    oracle_found = oracleEl is not null,
                                    signal_attrs = t.SignalAttrs, condition5 = cond5, id_class_signals = signals,
                                });
                            }
                        }

                        if (bundle == "B_noVolatileConsistent")
                        {
                            foreach (var el in filtered)
                            {
                                if (el.Attrs.TryGetValue("id", out var id) && !string.IsNullOrEmpty(id)
                                    && AttributeBundles.PredicateFlagsId(id, volIds, volCls))
                                {
                                    violations.Add($"{pageId} {encoding} id={id}");
                                }
                                if (el.Attrs.TryGetValue("class", out var cls) && !string.IsNullOrEmpty(cls))
                                {
                                    foreach (var tok in cls.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                                    {
                                        if (AttributeBundles.PredicateFlagsClassToken(tok, volIds, volCls))
                                        {
                                            violations.Add($"{pageId} {encoding} class={tok}");
                                        }
                                    }
                                }
                            }
                        }

                        // Census once per page, from the raw DOM walk (oracle anchors are not class/id).
                        if (bundle == "B_full")
                        {
                            var ids = raw.Select(e => e.Attrs.GetValueOrDefault("id"))
                                         .Where(v => !string.IsNullOrEmpty(v)).Distinct(StringComparer.Ordinal);
                            var classTokens = raw.SelectMany(e => (e.Attrs.GetValueOrDefault("class") ?? "")
                                                  .Split(' ', StringSplitOptions.RemoveEmptyEntries))
                                                 .Distinct(StringComparer.Ordinal);
                            foreach (var id in ids.OrderBy(x => x, StringComparer.Ordinal))
                            {
                                census.Add(new
                                {
                                    page = pageId, kind = "id", token = id,
                                    listed = volIds.Contains(id!),
                                    predicate_flags = AttributeBundles.PredicateFlagsId(id!, volIds, volCls),
                                    predicate_flags_with_empty_lists = AttributeBundles.PredicateFlagsId(
                                        id!, new HashSet<string>(), new HashSet<string>()),
                                });
                            }
                            foreach (var tok in classTokens.OrderBy(x => x, StringComparer.Ordinal))
                            {
                                census.Add(new
                                {
                                    page = pageId, kind = "class", token = tok,
                                    listed = volCls.Contains(tok),
                                    predicate_flags = AttributeBundles.PredicateFlagsClassToken(tok, volIds, volCls),
                                    predicate_flags_with_empty_lists = AttributeBundles.PredicateFlagsClassToken(
                                        tok, new HashSet<string>(), new HashSet<string>()),
                                });
                            }
                        }
                    }
                    await page.CloseAsync();
                    Console.WriteLine($"  {pageId}: {cells.Count} observations written");
                }
            }
            finally { await browser.CloseAsync(); }
        }
        finally
        {
            try { server.Kill(entireProcessTree: true); } catch { }
        }

        await File.WriteAllTextAsync(Path.Combine(outDir, "token_census.json"),
            JsonSerializer.Serialize(census, new JsonSerializerOptions { WriteIndented = true }));
        await File.WriteAllTextAsync(Path.Combine(outDir, "oracle_signals.json"),
            JsonSerializer.Serialize(signalRows, new JsonSerializerOptions { WriteIndented = true }));
        await File.WriteAllTextAsync(Path.Combine(outDir, "guard_violations.txt"),
            string.Join("\n", violations) + (violations.Count > 0 ? "\n" : ""));

        Console.WriteLine();
        if (violations.Count > 0)
        {
            Console.WriteLine($"  GUARD FAIL — {violations.Count} predicate-flagged class/id token(s) left in "
                              + "B_noVolatileConsistent observations (see guard_violations.txt)");
            return 2;
        }
        Console.WriteLine("  GUARD PASS — no class/id token in any B_noVolatileConsistent observation is flagged by the predicate");
        return 0;
    }
}
