using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

// ---------------------------------------------------------------------------
// Matrix runner — multi-page, all bundles × all encodings, GPT-4.1
//
// Scope: 7 bundles × 5 encodings (25 valid pairs + 10 skipped) × 10 targets
//        × MODEL_DEPLOYMENT_1 × repetition=0 × each page in BAR_PAGE_IDS
//
// Usage (from repo root):
//   dotnet run --project experiments/                                     # page_01 only
//   BAR_PAGE_IDS=page_05,page_08,page_10 dotnet run --project experiments/
//
// Requires .env with BAR_AZURE_OPENAI_ENDPOINT, BAR_AZURE_OPENAI_KEY + BAR_MODEL_DEPLOYMENT_1.
// Auth: API key via AzureKeyCredential (no DefaultAzureCredential / az login).
// Output: experiments/results/matrix_{pageId}.jsonl per page (gitignored)
// ---------------------------------------------------------------------------

Console.OutputEncoding = System.Text.Encoding.UTF8;

// ── Smoke test (DOM walk + tokenizer only, no LLM call) ─────────────────
if (Environment.GetEnvironmentVariable("SMOKE_TEST") == "1")
{
    await SmokeTests.RunAsync();
    return;
}
// ── LLM connectivity smoke test (5 calls, one per model) ─────────────────
if (Environment.GetEnvironmentVariable("LLM_SMOKE_TEST") == "1")
{
    await SmokeTests.RunLlmAsync();
    return;
}
// ── Predicate control set (hand-labeled verdicts, zero LLM) ──────────────
if (Environment.GetEnvironmentVariable("PREDICATE_CONTROLS") == "1")
{
    await PredicateControlsMode.RunAsync();
    return;
}
// ── Encoding-invariance validation (B_full × F0/F1/F2/F3 only) ──────────
if (Environment.GetEnvironmentVariable("VALIDATE_ENCODING") == "1")
{
    await EncodingValidationMode.RunAsync();
    return;
}
// ── Axis C — cross-model robustness (nano + o4-mini + Claude) ────────────
if (Environment.GetEnvironmentVariable("AXIS_C") == "1")
{
    await AxisCMode.RunAsync();
    return;
}
// ── Offline replay (re-classify archived locators, zero LLM spend) ───────
if (args.Contains("--replay"))
{
    var idx = Array.IndexOf(args, "--replay");
    var repoRootR = Helpers.FindRepoRoot(AppContext.BaseDirectory);
    var runsDirR = Path.Combine(repoRootR, "experiments", "runs");
    var archiveDirR = idx + 1 < args.Length && !args[idx + 1].StartsWith("--")
        ? args[idx + 1]
        : Directory.GetDirectories(runsDirR, "archive_*")
                   .OrderByDescending(d => d).FirstOrDefault()
          ?? throw new InvalidOperationException("No archive_* directory found under experiments/runs/. Specify path: --replay <dir>");
    await ReplayMode.RunAsync(repoRootR, runsDirR, archiveDirR);
    return;
}
// ─────────────────────────────────────────────────────────────────────────

// ── Page list from env ───────────────────────────────────────────────────
var pageIds = (Environment.GetEnvironmentVariable("BAR_PAGE_IDS") ?? "page_01")
    .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

// ── Compatible matrix definition (same for every page) ──────────────────
//
// Valid DOM-walk pairs: 6 bundles × 4 encodings = 24
// Valid ARIA pair:      B_playwrightMCP × F4       =  1
// Skipped pairs:        10 (logged below)

var domWalkBundles = new[] { "B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore" };
var domWalkEncodings = new[] { "F0", "F1", "F2", "F3" };

var validPairs = new List<(string Bundle, string Encoding)>();
foreach (var b in domWalkBundles)
{
    foreach (var e in domWalkEncodings)
    {
        validPairs.Add((b, e));
    }
}

validPairs.Add(("B_playwrightMCP", "F4"));

var skippedPairs = new List<(string Bundle, string Encoding, string Reason)>();
foreach (var e in domWalkEncodings)
{
    skippedPairs.Add(("B_playwrightMCP", e,
        "B_playwrightMCP requires the real Playwright ARIA snapshot path (F4 only)"));
}

foreach (var b in domWalkBundles)
{
    skippedPairs.Add((b, "F4",
        "F4 is the ARIA snapshot; applying it to a DOM-walk bundle is undefined"));
}

Console.WriteLine($"── Matrix runner — {string.Join(", ", pageIds)} × GPT-4.1 ─────────");
Console.WriteLine($"  Pages:         {pageIds.Length}");
Console.WriteLine($"  Valid pairs:   {validPairs.Count}  (24 DOM-walk + 1 ARIA)");
Console.WriteLine($"  Skipped pairs: {skippedPairs.Count}");
Console.WriteLine();
Console.WriteLine("  Skipped pairs:");
foreach (var (b, e, r) in skippedPairs)
{
    Console.WriteLine($"    {b} × {e}: {r}");
}

Console.WriteLine();
Console.WriteLine("── Canonical system prompt ───────────────────────────────────────────");
Console.WriteLine(GroundingRunner.SystemPrompt);
Console.WriteLine();

var model = Config.Get("BAR_MODEL_DEPLOYMENT_1");
var endpoint = Config.AzureOpenAiEndpoint;
var seed = Config.RandomSeed;
const string regime = "full_page";
const int repZero = 0;

var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
var port = new Uri(Config.TestbedBaseUrl).Port;
var runsDir = Path.Combine(repoRoot, "experiments", "runs");
Directory.CreateDirectory(runsDir);

// Archive old results generated by a prior harness version.
// Mixing schema versions (pre-CSS-only, pre-shadow-pierce) is not reproducible;
// keep the files for reference but start the fresh run from scratch.
var oldResultsDir = Path.Combine(repoRoot, "experiments", "results");
if (Directory.Exists(oldResultsDir))
{
    var toArchive = Directory.GetFiles(oldResultsDir, "*.jsonl");
    if (toArchive.Length > 0)
    {
        var archiveTag = DateTimeOffset.UtcNow.ToString("yyyyMMdd");
        var archiveDir = Path.Combine(runsDir, $"archive_{archiveTag}");
        Directory.CreateDirectory(archiveDir);
        foreach (var f in toArchive)
        {
            File.Move(f, Path.Combine(archiveDir, Path.GetFileName(f)), overwrite: true);
        }

        Console.WriteLine($"  Archived {toArchive.Length} old result file(s) → experiments/runs/archive_{archiveTag}/");
        Console.WriteLine();
    }
}

var startTime = DateTimeOffset.UtcNow;
var progressLog = Path.Combine(runsDir, "progress.log");
int callsDone = 0;
int totalCalls = 0;

ProcessStartInfo MakeServerPsi() => new ProcessStartInfo
{
    FileName = "python",
    Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
    UseShellExecute = false,
    RedirectStandardOutput = true,
    RedirectStandardError = true,
};

async Task<Process> StartFreshServerAsync(Process? old = null)
{
    if (old is not null)
    {
        try { old.Kill(entireProcessTree: true); } catch { }
        await Task.Delay(600);
    }
    var srv = Process.Start(MakeServerPsi())!;
    await Task.Delay(1200);
    return srv;
}

// ── Per-page loop ─────────────────────────────────────────────────────────
foreach (var pageId in pageIds)
{
    Console.WriteLine($"\n══ {pageId} {new string('═', Math.Max(0, 64 - pageId.Length - 4))}");

    // ── Load targets from truth.json ─────────────────────────────────────
    var truthPath = Path.Combine(repoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json");
    var truthJson = await File.ReadAllTextAsync(truthPath);
    var truthFile = JsonSerializer.Deserialize<TruthFile>(truthJson,
                        new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
                    ?? throw new InvalidOperationException($"Failed to deserialize {pageId}.truth.json");

    var volatileIds = new HashSet<string>(truthFile.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
    var volatileClasses = new HashSet<string>(truthFile.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);

    var targets = truthFile.Targets
        .Select(t => (TaskId: t.Id, Description: t.Intent, Oracle: new OracleRef(t.Oracle),
                      Page: $"pages/{pageId}.html", ExpectedStableSignal: t.ExpectedStableSignal,
                      SignalAttrs: (IReadOnlyList<string>)t.SignalAttrs))
        .ToList();

    var noneTargetIds = truthFile.Targets
        .Where(t => t.SignalAttrs.Length == 0)
        .Select(t => t.Id)
        .ToHashSet(StringComparer.Ordinal);

    var signalAttrsByTask = targets.ToDictionary(
        t => t.TaskId, t => t.SignalAttrs, StringComparer.Ordinal);

    Console.WriteLine($"  Loaded {targets.Count} targets  ({noneTargetIds.Count} NONE-signal: {string.Join(", ", noneTargetIds.OrderBy(x => x))})");
    Console.WriteLine();

    // ── Output file ──────────────────────────────────────────────────────
    var outputFile = Path.Combine(runsDir, $"matrix_{pageId}.jsonl");

    // ── Resume: load already-flushed records from disk (per-record granularity) ─
    var allRecords = new Dictionary<(string, string), List<GroundingRecord>>();
    var completedRecords = new HashSet<(string Bnd, string Enc, string Tid, int Rep)>();
    if (File.Exists(outputFile))
    {
        foreach (var line in await File.ReadAllLinesAsync(outputFile))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            using var doc = JsonDocument.Parse(line);
            var r = doc.RootElement;
            completedRecords.Add((
                r.GetProperty("bundle").GetString()!,
                r.GetProperty("encoding").GetString()!,
                r.GetProperty("task_id").GetString()!,
                r.GetProperty("repetition").GetInt32()));
        }
        if (completedRecords.Count > 0)
        {
            Console.WriteLine($"  [resume] {completedRecords.Count} records on disk — will skip");
        }
    }

    // Tally how many LLM calls this page contributes to the global progress counter
    foreach (var (b, e) in validPairs)
    {
        totalCalls += targets.Count(t => !completedRecords.Contains((b, e, t.TaskId, repZero)));
    }

    // ── Matrix run ────────────────────────────────────────────────────────
    Process? server = null;
    try
    {
        foreach (var (bundle, encoding) in validPairs)
        {
            // Skip the whole pair if every target is already on disk
            if (targets.All(t => completedRecords.Contains((bundle, encoding, t.TaskId, repZero))))
            {
                Console.WriteLine($"── {bundle} × {encoding}  [skipped — all {targets.Count} records on disk]");
                continue;
            }

            server = await StartFreshServerAsync(server);
            Console.WriteLine($"── {bundle} × {encoding} ──────────────────────────────────────────────");
            int pairSuccess = 0, pairRan = 0;

            foreach (var t in targets)
            {
                if (completedRecords.Contains((bundle, encoding, t.TaskId, repZero)))
                {
                    continue;
                }

                GroundingRecord record;
                try
                {
                    record = await GroundingRunner.RunOneAsync(
                        taskId: t.TaskId,
                        taskDescription: t.Description,
                        oracleRef: t.Oracle,
                        pagePath: t.Page,
                        bundle: bundle,
                        encoding: encoding,
                        regime: regime,
                        model: model,
                        endpoint: endpoint,
                        clientType: LlmClientType.AzureOpenAI,
                        repetition: repZero,
                        expectedStableSignal: t.ExpectedStableSignal,
                        volatileIds: volatileIds,
                        volatileClasses: volatileClasses,
                        signalAttrs: t.SignalAttrs,
                        seed: seed);
                }
                catch (TimeoutException)
                {
                    Console.WriteLine($"  [server timeout — restarting and retrying {t.TaskId}]");
                    server = await StartFreshServerAsync(server);
                    record = await GroundingRunner.RunOneAsync(
                        taskId: t.TaskId,
                        taskDescription: t.Description,
                        oracleRef: t.Oracle,
                        pagePath: t.Page,
                        bundle: bundle,
                        encoding: encoding,
                        regime: regime,
                        model: model,
                        endpoint: endpoint,
                        clientType: LlmClientType.AzureOpenAI,
                        repetition: repZero,
                        expectedStableSignal: t.ExpectedStableSignal,
                        volatileIds: volatileIds,
                        volatileClasses: volatileClasses,
                        signalAttrs: t.SignalAttrs,
                        seed: seed);
                }

                // Per-record flush — a crash cannot lose more than the in-flight record
                await File.AppendAllTextAsync(outputFile, record.ToJsonl() + "\n");
                pairRan++;
                if (record.Success)
                {
                    pairSuccess++;
                }

                callsDone++;

                // One-line progress: global index, page, pair, target, status, elapsed, ETA
                var elapsed = DateTimeOffset.UtcNow - startTime;
                var etaTs = callsDone > 0 && callsDone < totalCalls
                    ? TimeSpan.FromTicks(elapsed.Ticks / callsDone * (totalCalls - callsDone))
                    : (TimeSpan?)null;
                var statusStr = record.Success ? "ok" : $"FAIL/{record.FailureMode}";
                Console.WriteLine(
                    $"[{callsDone,4}/{totalCalls}] {pageId} {bundle}×{encoding} {t.TaskId}  " +
                    $"{statusStr}  tok={record.ObservationTokens}  " +
                    $"(elapsed {Helpers.FormatDuration(elapsed)}, ~{(etaTs.HasValue ? Helpers.FormatDuration(etaTs.Value) : "?")} left)");

                // Progress log — open+close per write so tail -f sees it immediately
                await File.AppendAllTextAsync(progressLog,
                    $"{DateTimeOffset.UtcNow:u}  [{callsDone,4}/{totalCalls}]  {pageId}  {bundle}×{encoding}  {t.TaskId}  {statusStr}\n");
            }

            if (pairRan > 0)
            {
                Console.WriteLine($"  → {pairSuccess}/{pairRan} succeeded in this batch  [flushed per record]");
            }

            Console.WriteLine();
        }
    }
    finally
    {
        try { server?.Kill(entireProcessTree: true); } catch { }
    }

    // ── Re-read full records from JSONL (handles resumed runs with null placeholders) ──
    var jsonReadOpts = new JsonSerializerOptions
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };
    var allFlat = (await File.ReadAllLinesAsync(outputFile))
        .Where(l => !string.IsNullOrWhiteSpace(l))
        .Select(l => JsonSerializer.Deserialize<GroundingRecord>(l, jsonReadOpts)!)
        .ToList();
    allRecords = allFlat
        .GroupBy(r => (r.Bundle, r.Encoding))
        .ToDictionary(g => g.Key, g => g.ToList());
    Console.WriteLine($"  Total records on disk: {allFlat.Count} across {allRecords.Count} pairs");
    Console.WriteLine();

    // ── §8 Verification gate ───────────────────────────────────────────────
    await PerPageVerificationGate.RunAsync(pageId, domWalkEncodings, volatileIds, volatileClasses,
        noneTargetIds, allFlat, allRecords, () => StartFreshServerAsync());

    // ── Results table ─────────────────────────────────────────────────────
    Console.WriteLine($"── {pageId} results (success / {targets.Count} targets) ─────────────────────");
    var allBundlesOrdered = new[] { "B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore", "B_playwrightMCP" };
    var allEncodingsOrdered = new[] { "F0", "F1", "F2", "F3", "F4" };
    Console.Write($"  {"Bundle",-16}");
    foreach (var enc in allEncodingsOrdered)
    {
        Console.Write($"  {enc,5}");
    }

    Console.WriteLine();
    Console.Write($"  {new string('─', 16)}");
    foreach (var _ in allEncodingsOrdered)
    {
        Console.Write($"  {new string('─', 5)}");
    }

    Console.WriteLine();
    foreach (var bnd in allBundlesOrdered)
    {
        Console.Write($"  {bnd,-16}");
        foreach (var enc in allEncodingsOrdered)
        {
            if (allRecords.TryGetValue((bnd, enc), out var recs))
            {
                Console.Write($"  {recs.Count(r => r.Success),2}/{targets.Count}");
            }
            else
            {
                Console.Write($"  {"SKIP",5}");
            }
        }
        Console.WriteLine();
    }
    Console.WriteLine();

    // ── Prediction-table contradiction check (generic) ────────────────────
    Console.WriteLine($"── {pageId} prediction-table contradiction check ──────────────────────");

    var contradictions = new List<string>();
    foreach (var (key, recs) in allRecords)
    {
        var (bundle, encoding) = key;
        foreach (var r in recs)
        {
            if (!signalAttrsByTask.TryGetValue(r.TaskId, out var sAttrs))
            {
                continue;
            }

            bool absent = Helpers.SignalAbsentInBundle(sAttrs, bundle);

            if (noneTargetIds.Contains(r.TaskId) && r.Success)
            {
                contradictions.Add($"  [{r.TaskId} {bundle}×{encoding}] SUCCESS for NONE-signal target — PAGE BUG or PREDICATE BUG");
            }
            else if (absent && r.Success)
            {
                contradictions.Add($"  [{r.TaskId} {bundle}×{encoding}] SUCCESS but all signal_attrs absent from bundle — PREDICATE BUG");
            }
            else if (absent && !r.Success && r.FailureMode == "model_grabbed_brittle_signal")
            {
                contradictions.Add($"  [{r.TaskId} {bundle}×{encoding}] failure_mode=model_grabbed_brittle_signal but signal absent from bundle — should be observation_lacked_stable_signal (CLASSIFICATION BUG)");
            }
        }
    }

    if (contradictions.Count == 0)
    {
        Console.WriteLine("  No prediction-table contradictions.");
    }
    else
    {
        Console.WriteLine($"  {contradictions.Count} contradiction(s):");
        foreach (var c in contradictions)
        {
            Console.WriteLine(c);
        }
    }
    Console.WriteLine();

    // ── Per-pair notable fails ────────────────────────────────────────────
    Console.WriteLine($"── {pageId} notable fails ─────────────────────────────────────────────");
    foreach (var (key, recs) in allRecords.OrderBy(kv => kv.Key.Item1).ThenBy(kv => kv.Key.Item2))
    {
        var fails = recs.Where(r => !r.Success).ToList();
        if (fails.Count > 0)
        {
            Console.WriteLine($"  {key.Item1} × {key.Item2}: {string.Join(", ", fails.Select(r => $"{r.TaskId}[{r.FailureMode}]"))}");
        }
    }
    Console.WriteLine();

    // ── page_08 token cost table at Extreme tier ──────────────────────────
    if (pageId == "page_08")
    {
        Console.WriteLine("── page_08 token cost at Extreme tier (avg tokens across targets) ────");
        var costBundles = new[] { "B_full", "B_identityCore" };
        var costEncodings = new[] { "F0", "F1", "F3" };
        Console.Write($"  {"Bundle",-16}");
        foreach (var e in costEncodings)
        {
            Console.Write($"  {e,9}");
        }

        Console.WriteLine();
        foreach (var b in costBundles)
        {
            Console.Write($"  {b,-16}");
            foreach (var e in costEncodings)
            {
                if (allRecords.TryGetValue((b, e), out var recs) && recs.Count > 0)
                {
                    Console.Write($"  {(int)recs.Average(r => r.ObservationTokens),9:N0}");
                }
                else
                {
                    Console.Write($"  {"N/A",9}");
                }
            }
            Console.WriteLine();
        }
        Console.WriteLine();
    }

} // end foreach pageId

// ── Summary ────────────────────────────────────────────────────────────────
await SummaryMode.RunAsync(runsDir, pageIds, validPairs, startTime);

// ---------------------------------------------------------------------------







