using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

internal static class AxisCMode
{
    // ---------------------------------------------------------------------------
    // Axis C cross-model robustness sweep.
    //
    // Models (sequential, cheapest first):
    //   gpt-4.1-nano  : 4 diagnostic cells × 24 pages × ~10 targets  = 960 calls
    //   o4-mini       : COP-only (B_noVolatile×F3) × 24 × ~10        = 240 calls
    //   claude-sonnet : same 4 cells × 24 × ~10                       = 960 calls
    //
    // GPT-4.1 data is REUSED (filter existing matrix files) — no re-run.
    // Output: experiments/runs/axisc_<model-slug>_<pageId>.jsonl, same GroundingRecord schema.
    // Progress table: printed every 30 min and at each model completion.
    // Run with: AXIS_C=1 dotnet run --project experiments/
    // ---------------------------------------------------------------------------

    public static async Task RunAsync()
    {
        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var runsDir = Path.Combine(repoRoot, "experiments", "runs");
        var port = new Uri(Config.TestbedBaseUrl).Port;
        var seed = Config.RandomSeed;
        const string regime = "full_page";
        const int repZero = 0;
        const int TPM_GUARD = 75_000;  // skip Claude cell if max obs tok exceeds this
        const double EUR_USD = 1.08;

        var pageIds = (Environment.GetEnvironmentVariable("BAR_PAGE_IDS")
            ?? "page_01,page_02,page_03,page_04,page_05,page_06,page_07,page_08,page_09,page_10," +
               "page_11,page_12,page_13,page_14,page_15,page_16,page_17,page_18,page_19,page_20," +
               "page_21,page_22,page_23,page_24")
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        (string Bundle, string Encoding)[] cells4 =
            [("B_full", "F1"), ("B_noVolatile", "F1"), ("B_noVolatile", "F3"), ("B_noVolatile", "F2")];
        (string Bundle, string Encoding)[] cellsCop =
            [("B_noVolatile", "F3")];

        // Sequential run order: nano (cheapest/fastest) → o4-mini → Claude (priciest)
        var axisModels = new (string Deploy, (string Bundle, string Encoding)[] Cells)[]
        {
            (Config.Get("BAR_MODEL_DEPLOYMENT_2"), cells4),    // gpt-4.1-nano
            (Config.Get("BAR_MODEL_DEPLOYMENT_4"), cellsCop),  // o4-mini
            (Config.Get("BAR_MODEL_DEPLOYMENT_5"), cells4),    // claude-sonnet-4-6
        };

        // Input rates per 1M tokens — for cost column in progress table only, not the cost metric
        static double InRate(string d)
        {
            if (d.StartsWith("gpt-4.1-nano", StringComparison.OrdinalIgnoreCase))
            {
                return 0.10;
            }

            if (d.StartsWith("o4-mini", StringComparison.OrdinalIgnoreCase))
            {
                return 1.10;
            }

            if (d.StartsWith("claude-", StringComparison.OrdinalIgnoreCase))
            {
                return 3.00;
            }

            return 2.00;
        }

        // Pre-load max obs tokens per (page-path, bundle, encoding) from GPT-4.1 matrix.
        // Used for the Claude TPM guard: if max_obs > 75K, the cell is skipped.
        var obsMax = new Dictionary<(string Page, string Bundle, string Encoding), int>();
        foreach (var pid in pageIds)
        {
            var mf = Path.Combine(runsDir, $"matrix_{pid}.jsonl");
            if (!File.Exists(mf))
            {
                continue;
            }

            foreach (var line in await File.ReadAllLinesAsync(mf))
            {
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                try
                {
                    using var doc = JsonDocument.Parse(line);
                    var r = doc.RootElement;
                    var key = (r.GetProperty("page").GetString()!,
                               r.GetProperty("bundle").GetString()!,
                               r.GetProperty("encoding").GetString()!);
                    var tok = r.GetProperty("observation_tokens").GetInt32();
                    if (!obsMax.TryGetValue(key, out var prev) || tok > prev)
                    {
                        obsMax[key] = tok;
                    }
                }
                catch { /* skip malformed lines */ }
            }
        }

        Directory.CreateDirectory(runsDir);
        var axisProgressLog = Path.Combine(runsDir, "axisc_progress.log");

        Console.WriteLine("══ AXIS C — cross-model robustness run ════════════════════════════════════");
        Console.WriteLine($"  Pages: {pageIds.Length}  |  Models: nano → o4-mini → claude");
        Console.WriteLine($"  Cells: 4 diagnostic (nano/claude)  COP-only (o4-mini)");
        Console.WriteLine($"  Output: experiments/runs/axisc_<model>_<page>.jsonl  (schema_version=1.0)");
        Console.WriteLine($"  TPM guard: Claude cells with max_obs_tok > {TPM_GUARD:N0} are skipped");
        Console.WriteLine();

        var modelStats = axisModels.Select(_ => new AxisCModelStats()).ToArray();

        // HTTP server — restarted per (bundle, encoding) pair (same pattern as main matrix loop)
        ProcessStartInfo MakePsi() => new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        async Task<Process> StartServer(Process? old = null)
        {
            if (old is not null) { try { old.Kill(entireProcessTree: true); } catch { } await Task.Delay(600); }
            var srv = Process.Start(MakePsi())!;
            await Task.Delay(1200);
            return srv;
        }

        // Progress table — printed to console and appended to axisc_progress.log
        void PrintProgressTable()
        {
            var now = DateTimeOffset.UtcNow;
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("══════════════════════════════════════════════════════════════════════════════════");
            sb.AppendLine($"AXIS C PROGRESS  [{now:u}]");
            sb.AppendLine("══════════════════════════════════════════════════════════════════════════════════");
            sb.AppendLine($"{"Model",-24}  {"Done/Total",11}  {"ObsTok(M)",9}  {"APITok(M)",9}  {"Cost€",7}  {"429s",5}  {"Rate/m",7}  ETA");
            for (int i = 0; i < axisModels.Length; i++)
            {
                var (dep, _) = axisModels[i];
                var s = modelStats[i];
                double mins = Math.Max(s.Elapsed.TotalMinutes, 0.001);
                double rate = s.Done > 0 ? s.Done / mins : 0;
                string eta = s.Total == 0 ? "--"
                             : s.Done >= s.Total ? "DONE"
                             : rate <= 0 ? "?"
                             : Helpers.FormatDuration(TimeSpan.FromMinutes((s.Total - s.Done) / rate));
                double eur = s.ObsTok / 1e6 * InRate(dep) / EUR_USD;
                sb.AppendLine(
                    $"{dep,-24}  {s.Done,5}/{s.Total,-5}  {s.ObsTok / 1e6,8:F1}M  {s.ApiTok / 1e6,8:F1}M" +
                    $"  {eur,6:F1}€  {s.Retries429,5}  {rate,7:F1}  {eta}");
            }
            sb.AppendLine("══════════════════════════════════════════════════════════════════════════════════");
            var table = sb.ToString();
            Console.Write(table);
            File.AppendAllText(axisProgressLog, table);
        }

        // ── Per-model sequential loop ──────────────────────────────────────────────────
        for (int mi = 0; mi < axisModels.Length; mi++)
        {
            var (deployment, cells) = axisModels[mi];
            var stats = modelStats[mi];
            var (clientType, endpoint) = Helpers.RouteModel(deployment);
            var modelSlug = deployment.Replace('.', '-');
            bool isClaude = deployment.StartsWith("claude-", StringComparison.OrdinalIgnoreCase);

            LlmClient.TotalRetries429 = 0;
            stats.ModelStart = DateTimeOffset.UtcNow;
            var lastReport = stats.ModelStart.AddMinutes(-31); // negative offset → forces first report at start

            Console.WriteLine($"\n══ MODEL: {deployment} ═══════════════════════════════════════════════════");
            Console.WriteLine($"  ClientType: {clientType}  Endpoint: {Helpers.TruncateEndpoint(endpoint)}");
            Console.WriteLine($"  Cells: {string.Join("  ", cells.Select(c => $"{c.Bundle}×{c.Encoding}"))}");

            // Pre-count remaining calls for this model (accounting for resume + TPM skips)
            foreach (var pid in pageIds)
            {
                var tp = Path.Combine(repoRoot, "shared", "testbed", "pages", $"{pid}.truth.json");
                if (!File.Exists(tp))
                {
                    continue;
                }

                var tf = JsonSerializer.Deserialize<TruthFile>(
                    File.ReadAllText(tp),
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
                var doneP = Helpers.LoadDoneSet(Path.Combine(runsDir, $"axisc_{modelSlug}_{pid}.jsonl"));
                foreach (var (b, e) in cells)
                {
                    if (isClaude && obsMax.TryGetValue(($"pages/{pid}.html", b, e), out var mx) && mx > TPM_GUARD)
                    {
                        continue;
                    }

                    stats.Total += tf.Targets.Count(t => !doneP.Contains((b, e, t.Id, repZero)));
                }
            }
            Console.WriteLine($"  Remaining calls (after resume + TPM-skip deduction): {stats.Total}");
            Console.WriteLine();

            PrintProgressTable();

            // ── Per-page loop ─────────────────────────────────────────────────────────
            foreach (var pageId in pageIds)
            {
                var truthPath = Path.Combine(repoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json");
                if (!File.Exists(truthPath))
                {
                    Console.WriteLine($"  [WARN] {pageId}: truth.json not found — skipped");
                    continue;
                }

                var truthFile = JsonSerializer.Deserialize<TruthFile>(
                    await File.ReadAllTextAsync(truthPath),
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
                var volatileIds = new HashSet<string>(truthFile.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
                var volatileClasses = new HashSet<string>(truthFile.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
                var targets = truthFile.Targets
                    .Select(t => (TaskId: t.Id, Description: t.Intent,
                                  Oracle: new OracleRef(t.Oracle),
                                  Page: $"pages/{pageId}.html",
                                  ExpectedStableSignal: t.ExpectedStableSignal,
                                  SignalAttrs: (IReadOnlyList<string>)t.SignalAttrs))
                    .ToList();

                var outFile = Path.Combine(runsDir, $"axisc_{modelSlug}_{pageId}.jsonl");
                var done = Helpers.LoadDoneSet(outFile);

                Process? server = null;
                try
                {
                    foreach (var (bundle, encoding) in cells)
                    {
                        // Claude TPM guard: skip entire (page, cell) if obs token count exceeds the window
                        if (isClaude)
                        {
                            var pagePath = $"pages/{pageId}.html";
                            if (obsMax.TryGetValue((pagePath, bundle, encoding), out var maxObs) && maxObs > TPM_GUARD)
                            {
                                var msg = $"[SKIP-TPM] {pageId} {bundle}×{encoding}: max_obs_tok={maxObs:N0} > {TPM_GUARD:N0} (Claude 80K TPM)";
                                Console.WriteLine($"  {msg}");
                                await File.AppendAllTextAsync(axisProgressLog, $"{DateTimeOffset.UtcNow:u}  {msg}\n");
                                stats.SkippedTpm++;
                                continue;
                            }
                        }

                        if (targets.All(t => done.Contains((bundle, encoding, t.TaskId, repZero))))
                        {
                            Console.WriteLine($"  {pageId} {bundle}×{encoding} [{targets.Count} records on disk — skipped]");
                            continue;
                        }

                        server = await StartServer(server);
                        Console.WriteLine($"  ── {pageId} {bundle}×{encoding} ──");
                        int pairDone = 0, pairOk = 0;

                        foreach (var t in targets)
                        {
                            if (done.Contains((bundle, encoding, t.TaskId, repZero)))
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
                                    model: deployment,
                                    endpoint: endpoint,
                                    clientType: clientType,
                                    repetition: repZero,
                                    expectedStableSignal: t.ExpectedStableSignal,
                                    volatileIds: volatileIds,
                                    volatileClasses: volatileClasses,
                                    signalAttrs: t.SignalAttrs,
                                    seed: seed);
                            }
                            catch (TimeoutException)
                            {
                                Console.Error.WriteLine($"  [server timeout — restarting and retrying {t.TaskId}]");
                                server = await StartServer(server);
                                record = await GroundingRunner.RunOneAsync(
                                    taskId: t.TaskId,
                                    taskDescription: t.Description,
                                    oracleRef: t.Oracle,
                                    pagePath: t.Page,
                                    bundle: bundle,
                                    encoding: encoding,
                                    regime: regime,
                                    model: deployment,
                                    endpoint: endpoint,
                                    clientType: clientType,
                                    repetition: repZero,
                                    expectedStableSignal: t.ExpectedStableSignal,
                                    volatileIds: volatileIds,
                                    volatileClasses: volatileClasses,
                                    signalAttrs: t.SignalAttrs,
                                    seed: seed);
                            }

                            // Per-record atomic flush — a crash cannot lose more than the in-flight record
                            await File.AppendAllTextAsync(outFile, record.ToJsonl() + "\n");
                            done.Add((bundle, encoding, t.TaskId, repZero));
                            pairDone++;
                            if (record.Success)
                            {
                                pairOk++;
                            }

                            // Update model stats
                            stats.Done++;
                            stats.ObsTok += record.ObservationTokens;
                            stats.ApiTok += record.PromptTokensTotal;
                            stats.Retries429 = LlmClient.TotalRetries429;

                            // One-line progress
                            var elapsed = stats.Elapsed;
                            double ratePM = stats.Done > 0 ? stats.Done / Math.Max(elapsed.TotalMinutes, 0.001) : 0;
                            var etaTs = (stats.Done < stats.Total && ratePM > 0)
                                ? (TimeSpan?)TimeSpan.FromMinutes((stats.Total - stats.Done) / ratePM) : null;
                            var statusStr = record.Success ? "ok" : $"FAIL/{record.FailureMode}";
                            Console.WriteLine(
                                $"[{stats.Done,4}/{stats.Total}] {deployment}  {pageId} {bundle}×{encoding} {t.TaskId}  " +
                                $"{statusStr}  tok={record.ObservationTokens}  " +
                                $"(elapsed {Helpers.FormatDuration(elapsed)}, ~{(etaTs.HasValue ? Helpers.FormatDuration(etaTs.Value) : "?")} left)");
                            await File.AppendAllTextAsync(axisProgressLog,
                                $"{DateTimeOffset.UtcNow:u}  [{stats.Done,4}/{stats.Total}]  {deployment}  {pageId}  {bundle}×{encoding}  {t.TaskId}  {statusStr}\n");

                            // 30-min progress table
                            if ((DateTimeOffset.UtcNow - lastReport).TotalMinutes >= 30)
                            {
                                PrintProgressTable();
                                lastReport = DateTimeOffset.UtcNow;
                            }
                        }

                        if (pairDone > 0)
                        {
                            Console.WriteLine($"  → {pairOk}/{pairDone} ok  {bundle}×{encoding}");
                        }
                    }
                }
                finally { try { server?.Kill(entireProcessTree: true); } catch { } }
            }

            Console.WriteLine($"\n── {deployment} COMPLETE ───────────────────────────────────────────────────");
            PrintProgressTable();
        }

        Console.WriteLine("\n══ AXIS C COMPLETE ═══════════════════════════════════════════════════════════");
        Console.WriteLine("  Final record counts:");
        for (int i = 0; i < axisModels.Length; i++)
        {
            var (dep, _) = axisModels[i];
            var s = modelStats[i];
            Console.WriteLine($"  {dep,-28}: {s.Done}/{s.Total} calls  ({s.SkippedTpm} TPM-skipped cells)  {s.Retries429} total 429 retries");
        }
    }
}
