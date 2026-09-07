using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

internal static class EncodingValidationMode
{
    /// <summary>
    /// VALIDATE_ENCODING=1 mode: B_full × {F0,F1,F2,F3} — success pattern must be
    /// identical across encodings (format change must not affect which targets succeed).
    /// Always runs on the first page in BAR_PAGE_IDS (default page_01).
    /// </summary>
    public static async Task RunAsync()
    {
        var pageId = (Environment.GetEnvironmentVariable("BAR_PAGE_IDS") ?? "page_01")
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .First();

        Console.WriteLine($"── Encoding-invariance validation — {pageId} × B_full × {{F0,F1,F2,F3}} ──");
        Console.WriteLine("   Invariant: success/fail pattern must be identical across F0–F3.");
        Console.WriteLine();

        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var truthPath = Path.Combine(repoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json");
        var truthJson = await File.ReadAllTextAsync(truthPath);
        var truthFile = JsonSerializer.Deserialize<TruthFile>(truthJson,
                              new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
        var volatileIds = new HashSet<string>(truthFile.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
        var volatileClasses = new HashSet<string>(truthFile.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
        var noneIds = truthFile.Targets
            .Where(t => t.SignalAttrs.Length == 0).Select(t => t.Id).ToHashSet(StringComparer.Ordinal);
        var targets = truthFile.Targets
            .Select(t => (t.Id, t.Intent, Oracle: new OracleRef(t.Oracle),
                          Page: $"pages/{pageId}.html", t.ExpectedStableSignal,
                          SignalAttrs: (IReadOnlyList<string>)t.SignalAttrs))
            .ToList();

        var model = Config.Get("BAR_MODEL_DEPLOYMENT_1");
        var endpoint = Config.AzureOpenAiEndpoint;
        var seed = Config.RandomSeed;

        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var port = new Uri(Config.TestbedBaseUrl).Port;
        using var server = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        await Task.Delay(1200);

        var results = new Dictionary<string, Dictionary<string, bool>>(StringComparer.OrdinalIgnoreCase);
        var locators = new Dictionary<string, Dictionary<string, string>>(StringComparer.OrdinalIgnoreCase);

        try
        {
            foreach (var enc in new[] { "F0", "F1", "F2", "F3" })
            {
                Console.WriteLine($"  Running B_full × {enc} ...");
                results[enc] = new Dictionary<string, bool>(StringComparer.Ordinal);
                locators[enc] = new Dictionary<string, string>(StringComparer.Ordinal);

                foreach (var t in targets)
                {
                    var record = await GroundingRunner.RunOneAsync(
                        taskId: t.Id,
                        taskDescription: t.Intent,
                        oracleRef: t.Oracle,
                        pagePath: t.Page,
                        bundle: "B_full",
                        encoding: enc,
                        regime: "full_page",
                        model: model,
                        endpoint: endpoint,
                        clientType: LlmClientType.AzureOpenAI,
                        repetition: 0,
                        expectedStableSignal: t.ExpectedStableSignal,
                        volatileIds: volatileIds,
                        volatileClasses: volatileClasses,
                        signalAttrs: t.SignalAttrs,
                        seed: seed);

                    results[enc][t.Id] = record.Success;
                    locators[enc][t.Id] = record.LocatorValue;
                    var mark = record.Success ? "✓" : "✗";
                    Console.WriteLine($"    {t.Id} {mark}  {record.LocatorType}:{record.LocatorValue[..Math.Min(70, record.LocatorValue.Length)]}{(record.LocatorValue.Length > 70 ? "…" : "")}");
                }
                Console.WriteLine($"  B_full × {enc}: {results[enc].Values.Count(v => v)}/{targets.Count}");
                Console.WriteLine();
            }
        }
        finally
        {
            try { server.Kill(entireProcessTree: true); } catch { }
        }

        Console.WriteLine($"── Per-target pattern (✓=success ✗=fail) ────────────────────────────");
        Console.WriteLine($"  {"Target",-8}  {"F0",4}  {"F1",4}  {"F2",4}  {"F3",4}  {"Consistent?",12}");
        Console.WriteLine($"  {new string('─', 8)}  {new string('─', 4)}  {new string('─', 4)}  {new string('─', 4)}  {new string('─', 4)}  {new string('─', 12)}");

        bool allConsistent = true;
        var violations = new List<string>();
        foreach (var t in targets)
        {
            bool f0 = results["F0"][t.Id], f1 = results["F1"][t.Id],
                 f2 = results["F2"][t.Id], f3 = results["F3"][t.Id];
            bool consistent = f0 == f1 && f1 == f2 && f2 == f3;
            if (!consistent) { allConsistent = false; violations.Add(t.Id); }
            string mark(bool b) => b ? "✓" : "✗";
            Console.WriteLine($"  {t.Id,-8}  {mark(f0),4}  {mark(f1),4}  {mark(f2),4}  {mark(f3),4}  {(consistent ? "OK" : "VIOLATION!"),12}");
            if (!consistent)
            {
                foreach (var enc in new[] { "F0", "F1", "F2", "F3" })
                {
                    Console.WriteLine($"    {enc}: {(results[enc][t.Id] ? "✓" : "✗")} {locators[enc][t.Id]}");
                }
            }
        }

        Console.WriteLine();
        Console.WriteLine($"  Encoding-invariance: {(allConsistent ? "PASS" : $"FAIL — violations: {string.Join(", ", violations)}")}");
        foreach (var tid in noneIds.OrderBy(x => x))
        {
            bool anyPass = new[] { "F0", "F1", "F2", "F3" }.Any(e => results[e][tid]);
            Console.WriteLine($"  {tid} (NONE signal): {(anyPass ? "[PREDICATE BUG] succeeded in at least one encoding!" : "fails in all 4 encodings — correct")}");
        }
    }
}
