using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

/// <summary>
/// Sensitivity run (SENSITIVITY_CONSISTENT=1): grounds the B_noVolatileConsistent
/// bundle only on the (page, encoding) cells listed in a cells file — the cells whose
/// observation differs byte-for-byte from B_noVolatile. Same canonical prompt, model
/// (BAR_MODEL_DEPLOYMENT_1 = gpt-4.1, temperature 0 via LlmClient), regime and repetition 0
/// as the main matrix; same GroundingRunner.RunOneAsync path; same record schema.
///
/// Output: experiments/results/revision1/consistent_runs/consistent_&lt;pageId&gt;.jsonl (resumable,
/// per-record flush). Never writes to experiments/runs/.
///
/// Env: BAR_CELLS_FILE (default experiments/results/revision1/consistent_cells.json:
///      [{"page": "page_17", "encoding": "F0"}, ...]).
/// </summary>
internal static class ConsistentSensitivityMode
{
    private const string Bundle = "B_noVolatileConsistent";

    public static async Task RunAsync()
    {
        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var resultsDir = Path.Combine(repoRoot, "experiments", "results", "revision1");
        var cellsFile = Environment.GetEnvironmentVariable("BAR_CELLS_FILE")
                        ?? Path.Combine(resultsDir, "consistent_cells.json");
        var outDir = Path.Combine(resultsDir, "consistent_runs");
        Directory.CreateDirectory(outDir);

        using var cellsDoc = JsonDocument.Parse(await File.ReadAllTextAsync(cellsFile));
        var cells = cellsDoc.RootElement.EnumerateArray()
            .Select(c => (Page: c.GetProperty("page").GetString()!, Encoding: c.GetProperty("encoding").GetString()!))
            .ToList();
        var byPage = cells.GroupBy(c => c.Page).OrderBy(g => g.Key, StringComparer.Ordinal).ToList();

        var deployment = Config.Get("BAR_MODEL_DEPLOYMENT_1");
        var (clientType, endpoint) = Helpers.RouteModel(deployment);
        var seed = Config.RandomSeed;
        const string regime = "full_page";
        const int repZero = 0;

        Console.WriteLine($"── Revision 1 sensitivity — {Bundle} × {cells.Count} cells ({byPage.Count} pages) × {deployment}");
        Console.WriteLine($"  Cells file: {cellsFile}");
        Console.WriteLine($"  Output:     {outDir}");
        Console.WriteLine();

        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var port = new Uri(Config.TestbedBaseUrl).Port;

        async Task<Process> StartServer(Process? old = null)
        {
            if (old is not null)
            {
                try { old.Kill(entireProcessTree: true); } catch { }
                await Task.Delay(600);
            }
            var srv = Process.Start(new ProcessStartInfo
            {
                FileName = "python",
                Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            })!;
            srv.BeginOutputReadLine();   // drain: an unread pipe blocks http.server
            srv.BeginErrorReadLine();
            await Task.Delay(1200);
            return srv;
        }

        int done = 0, ok = 0;
        Process? server = null;
        try
        {
            foreach (var pageGroup in byPage)
            {
                var pageId = pageGroup.Key;
                var truth = JsonSerializer.Deserialize<TruthFile>(
                    await File.ReadAllTextAsync(Path.Combine(testbedDir, "pages", $"{pageId}.truth.json")),
                    new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
                var volIds = new HashSet<string>(truth.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
                var volCls = new HashSet<string>(truth.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
                var outFile = Path.Combine(outDir, $"consistent_{pageId}.jsonl");
                var onDisk = Helpers.LoadDoneSet(outFile);

                foreach (var (_, encoding) in pageGroup.OrderBy(c => c.Encoding, StringComparer.Ordinal))
                {
                    server = await StartServer(server);
                    Console.WriteLine($"── {pageId} {Bundle}×{encoding}");
                    foreach (var t in truth.Targets)
                    {
                        if (onDisk.Contains((Bundle, encoding, t.Id, repZero)))
                        {
                            continue;
                        }

                        Task<GroundingRecord> Run() => GroundingRunner.RunOneAsync(
                            taskId: t.Id,
                            taskDescription: t.Intent,
                            oracleRef: new OracleRef(t.Oracle),
                            pagePath: $"pages/{pageId}.html",
                            bundle: Bundle,
                            encoding: encoding,
                            regime: regime,
                            model: deployment,
                            endpoint: endpoint,
                            clientType: clientType,
                            repetition: repZero,
                            expectedStableSignal: t.ExpectedStableSignal,
                            volatileIds: volIds,
                            volatileClasses: volCls,
                            signalAttrs: t.SignalAttrs,
                            seed: seed);

                        GroundingRecord record;
                        try
                        {
                            record = await Run();
                        }
                        catch (TimeoutException)
                        {
                            Console.Error.WriteLine($"  [server timeout — restarting and retrying {t.Id}]");
                            server = await StartServer(server);
                            record = await Run();
                        }

                        await File.AppendAllTextAsync(outFile, record.ToJsonl() + "\n");
                        onDisk.Add((Bundle, encoding, t.Id, repZero));
                        done++;
                        if (record.Success)
                        {
                            ok++;
                        }
                        Console.WriteLine($"  [{done,3}] {pageId} {encoding} {t.Id}  "
                                          + (record.Success ? "ok" : $"FAIL/{record.FailureMode}")
                                          + $"  obs={record.ObservationTokens} prompt={record.PromptTokensTotal}");
                    }
                }
            }
        }
        finally
        {
            if (server is not null)
            {
                try { server.Kill(entireProcessTree: true); } catch { }
            }
        }

        Console.WriteLine();
        Console.WriteLine($"── Done: {done} new records this run, {ok} successes. 429 retries: {LlmClient.TotalRetries429}");
    }
}
