using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using BoundedAgents.Shared.Tokenizer;

/// <summary>
/// Batch observation dump (DUMP_BATCH_OBSERVATIONS=1), zero LLM.
/// For every page builds, with Observation.BuildObservationAsync:
///   - the bundle ladder × F1 (B_full, B_noVolatile, B_noState, B_noSemantic, B_identityCore,
///     B_minimalCore) + B_noVolatileConsistent × F1;
///   - the four Block 1 single ablations × F1 (B_full_minus_volClass / _volId / _state / _aria);
///   - F2 and F2L × {B_full, B_noVolatile} (Block 2).
/// Writes the observation texts, manifest.tsv (o200k_base tokens + sha256), condition 5 per
/// target × bundle (cond5_batch.json, the same Oracle.ComputeStableSignalPresence call the
/// runner makes) and the bundle composition as the code defines it (bundle_composition.json).
///
/// Env: BAR_DUMP_DIR (default experiments/results/revision1/batch_observations, wiped first),
///      BAR_PAGE_IDS (default all 24).
/// </summary>
internal static class BatchObservationDumpMode
{
    private static readonly string[] Ladder =
        { "B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore" };

    private static readonly string[] Ablations =
        { "B_full_minus_volClass", "B_full_minus_volId", "B_full_minus_state", "B_full_minus_aria" };

    // Bundles whose condition 5 is recorded (DOM-walk bundles; F-independent).
    private static readonly string[] Cond5Bundles =
        { "B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore",
          "B_noVolatileConsistent", "B_full_minus_volClass", "B_full_minus_volId", "B_full_minus_state",
          "B_full_minus_aria" };

    public static async Task<int> RunAsync()
    {
        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var outDir = Environment.GetEnvironmentVariable("BAR_DUMP_DIR")
                     ?? Path.Combine(repoRoot, "experiments", "results", "revision1", "batch_observations");
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

        var cells = new List<(string Bundle, string Encoding)>();
        cells.AddRange(Ladder.Select(b => (b, "F1")));
        cells.Add(("B_noVolatileConsistent", "F1"));
        cells.AddRange(Ablations.Select(b => (b, "F1")));
        foreach (var b in new[] { "B_full", "B_noVolatile" })
        {
            cells.Add((b, "F2"));
            cells.Add((b, "F2L"));
        }

        await File.WriteAllTextAsync(Path.Combine(outDir, "bundle_composition.json"),
            JsonSerializer.Serialize(Composition(), new JsonSerializerOptions { WriteIndented = true }));

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

        var cond5Rows = new List<object>();
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

                    IReadOnlyList<ElementData>? raw = null;
                    foreach (var (bundle, encoding) in cells)
                    {
                        var (obsText, rawWithAnchors, _) = await Observation.BuildObservationAsync(
                            page, bundle, encoding, volIds, volCls);
                        raw ??= rawWithAnchors;
                        await File.WriteAllTextAsync(Path.Combine(outDir, $"{pageId}__{bundle}__{encoding}.txt"), obsText);
                        var sha = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(obsText))).ToLowerInvariant();
                        await File.AppendAllTextAsync(manifestPath,
                            $"{pageId}\t{bundle}\t{encoding}\t{TokenCounter.CountTokens(obsText)}\t{sha}\n");
                    }

                    foreach (var t in truth.Targets)
                    {
                        var oracleEl = raw!.FirstOrDefault(e =>
                            e.Attrs.TryGetValue("data-oracle-id", out var oid) && oid == t.Oracle);
                        var perBundle = new Dictionary<string, bool>();
                        foreach (var b in Cond5Bundles)
                        {
                            var set = AttributeBundles.ResolveBundleSetForSignalCheck(b);
                            // Same call Oracle.EvaluateLocatorAsync makes for condition 5.
                            perBundle[b] = Oracle.ComputeStableSignalPresence(
                                t.SignalAttrs, a => set.Contains(a), oracleEl, volIds, volCls);
                        }
                        cond5Rows.Add(new
                        {
                            page = pageId, task_id = t.Id, signal_attrs = t.SignalAttrs,
                            oracle_found = oracleEl is not null, condition5 = perBundle,
                        });
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

        await File.WriteAllTextAsync(Path.Combine(outDir, "cond5_batch.json"),
            JsonSerializer.Serialize(cond5Rows, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"  Done: {pageIds.Length} pages × {cells.Count} cells → {outDir}");
        return 0;
    }

    /// <summary>The attribute sets exactly as the harness code defines them.</summary>
    private static object Composition()
    {
        static string[] Sorted(IEnumerable<string> s) => s.OrderBy(x => x, StringComparer.Ordinal).ToArray();
        var staticBundles = new[] { "B_full", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore",
                                    "B_full_minus_state", "B_full_minus_aria" };
        return new
        {
            bundle_full = Sorted(AttributeBundles.BundleFull),
            categories = AttributeBundles.AttributeCategories.ToDictionary(kv => kv.Key, kv => Sorted(kv.Value)),
            static_bundles = staticBundles.ToDictionary(b => b, b => Sorted(AttributeBundles.GetBundle(b))),
            // Value-level bundles: no static entry of their own; condition 5 uses this set.
            condition5_sets = Cond5Bundles.ToDictionary(b => b,
                b => Sorted(AttributeBundles.ResolveBundleSetForSignalCheck(b))),
            f2_legend = ObservationEncoders.F2Legend,
        };
    }
}
