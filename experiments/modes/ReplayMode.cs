using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

internal static class ReplayMode
{
    /// <summary>
    /// Offline replay (--replay): re-classifies the archived locators in
    /// <paramref name="archiveDir"/> through the current predicate against live pages and writes
    /// experiments/runs/replay_&lt;date&gt;.jsonl. Zero LLM — the model outputs were recorded earlier.
    /// </summary>
    public static async Task RunAsync(string repoRoot, string runsDir, string archiveDir)
    {
        Console.WriteLine($"── Replay mode ───────────────────────────────────────────────────────");
        Console.WriteLine($"  Archive: {archiveDir}");
        Console.WriteLine();

        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var port = new Uri(Config.TestbedBaseUrl).Port;
        var jsonOpts = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            PropertyNameCaseInsensitive = true,
        };

        // ── Read all archived records ────────────────────────────────────────
        var archiveFiles = Directory.GetFiles(archiveDir, "*.jsonl");
        if (archiveFiles.Length == 0)
        {
            throw new InvalidOperationException($"No *.jsonl files found in {archiveDir}");
        }

        var archived = new List<(string Page, string Bundle, string Encoding, string TaskId, string LocatorRaw)>();
        foreach (var file in archiveFiles)
        {
            foreach (var line in await File.ReadAllLinesAsync(file))
            {
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                using var doc = JsonDocument.Parse(line);
                var r = doc.RootElement;
                archived.Add((
                    r.GetProperty("page").GetString()!,
                    r.GetProperty("bundle").GetString()!,
                    r.GetProperty("encoding").GetString()!,
                    r.GetProperty("task_id").GetString()!,
                    r.GetProperty("locator_raw").GetString()!));
            }
        }

        int total = archived.Count;
        int done = 0;
        var dateTag = DateTimeOffset.UtcNow.ToString("yyyyMMdd");
        var outPath = Path.Combine(runsDir, $"replay_{dateTag}.jsonl");
        Console.WriteLine($"  Records to replay: {total}");
        Console.WriteLine($"  Output: {outPath}");
        Console.WriteLine();

        // ── Group by page ────────────────────────────────────────────────────
        var byPage = archived
            .GroupBy(r => r.Page)
            .ToDictionary(g => g.Key, g => g.ToList());

        // ── Truth cache ───────────────────────────────────────────────────────
        var truthCache = new Dictionary<string, TruthFile>(StringComparer.Ordinal);
        TruthFile GetTruth(string pageId)
        {
            if (truthCache.TryGetValue(pageId, out var tf))
            {
                return tf;
            }

            var path = Path.Combine(repoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json");
            var json = File.ReadAllText(path);
            tf = JsonSerializer.Deserialize<TruthFile>(json,
                     new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
            truthCache[pageId] = tf;
            return tf;
        }

        // ── NONE-target tracking ─────────────────────────────────────────────
        var noneViolations = new List<string>();

        // ── Start server ─────────────────────────────────────────────────────
        var server = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        await Task.Delay(1200);

        try
        {
            using var playwright = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await playwright.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                foreach (var (pagePath, records) in byPage)
                {
                    // pagePath = "pages/page_01.html"  →  pageId = "page_01"
                    var pageId = Path.GetFileNameWithoutExtension(pagePath);
                    var truth = GetTruth(pageId);
                    var volIds = new HashSet<string>(truth.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
                    var volCls = new HashSet<string>(truth.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
                    var targetLookup = truth.Targets.ToDictionary(t => t.Id, StringComparer.Ordinal);

                    var page = await browser.NewPageAsync();
                    var pageUrl = $"{Config.TestbedBaseUrl.TrimEnd('/')}/{pagePath}";
                    await page.GotoAsync(pageUrl, new() { Timeout = 90_000 });
                    await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle, new() { Timeout = 90_000 });

                    foreach (var (_, bundle, encoding, taskId, locatorRaw) in records)
                    {
                        if (!targetLookup.TryGetValue(taskId, out var target))
                        {
                            throw new InvalidOperationException($"Task {taskId} not found in {pageId}.truth.json");
                        }

                        var newRecord = await GroundingRunner.ReplayOneAsync(
                            page, taskId, new OracleRef(target.Oracle), pagePath,
                            bundle, encoding, locatorRaw,
                            target.ExpectedStableSignal, volIds, volCls,
                            target.SignalAttrs);

                        await File.AppendAllTextAsync(outPath, newRecord.ToJsonl() + "\n");
                        done++;
                        var status = newRecord.Success ? "ok" : $"FAIL/{newRecord.FailureMode ?? "?"}";
                        Console.WriteLine($"[{done,4}/{total}] {pageId} {bundle}×{encoding} {taskId}  {status}  " +
                                          $"signal={newRecord.StableSignalPresentInBundle}");

                        bool isNone = target.SignalAttrs.Length == 0;
                        if (isNone && newRecord.Success)
                        {
                            noneViolations.Add($"{pageId} {bundle}×{encoding} {taskId}");
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

        // ── NONE-target invariant report ─────────────────────────────────────
        Console.WriteLine();
        Console.WriteLine("── Replay complete ───────────────────────────────────────────────────");
        Console.WriteLine($"  Total records replayed: {done}");
        Console.WriteLine($"  Output: {outPath}");
        Console.WriteLine();
        if (noneViolations.Count == 0)
        {
            Console.WriteLine("  NONE-target invariant: PASS — no NONE target succeeded");
        }
        else
        {
            Console.WriteLine($"  NONE-target invariant: FAIL — {noneViolations.Count} NONE target(s) succeeded:");
            foreach (var v in noneViolations)
            {
                Console.WriteLine($"    {v}");
            }
        }
    }
}
