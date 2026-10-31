using BoundedAgents.Shared.Harness;

namespace BoundedAgents.Experiments.Batch;

/// <summary>
/// The real-site pilot (selected only with <c>--plan pilot</c>): <see cref="PilotPreflight"/>, then the
/// batch's own loop (<see cref="RevisionBatchRunner.RunCoreAsync"/>) with the pilot's expectations,
/// plan order, µUSD budget and per-event input-token check. Own journal / lock / records directory.
/// </summary>
public static class PilotRunner
{
    public static RunSpec Spec(PilotOptions o, PilotPlan p) => new()
    {
        Title = $"Real-site pilot — {p.Sites.Count} sites, {p.Events.Count} called + {p.Reused.Count} reused",
        X = p.Expectations,
        Order = p.Events,
        Budget = p.Budget,
        OutDir = o.OutDir,
        Env = o.Env,
        MaxAttempts = o.MaxAttempts,
        PlannedInputTokens = PilotPreflight.PlannedInputTokensOf(p),
    };

    public static Task<BatchRunSummary> RunAsync(
        PilotOptions o, Func<PilotPlan, IBatchExecutor> executorFactory, ILlmCaller caller,
        Func<TimeSpan, Task>? delay = null, Action<string>? log = null)
    {
        var p = PilotPreflight.Run(o);
        return RevisionBatchRunner.RunCoreAsync(Spec(o, p), () => executorFactory(p), caller, delay, log);
    }
}

/// <summary>Command line of the pilot profile (exit codes as the batch: 0 / 3 refused / 4 stopped).</summary>
public static class PilotEntry
{
    public static async Task<int> RunAsync(string repoRoot, BatchMode mode)
    {
        var options = PilotPins.Production(repoRoot);
        try
        {
            if (mode != BatchMode.Execute)
            {
                var p = PilotPreflight.Run(options);
                Console.WriteLine(
                    $"[batch] pilot preflight PASS: plan {PilotPins.PlanSha256[..12]}…, {p.Events.Count:N0} events to call " +
                    $"(+{p.Reused.Count} reused, no call), {p.PlannedInputTokens:N0} input tokens (o200k), {p.Sites.Count} sites; " +
                    $"deployments {string.Join(", ", p.Deployments.Select(kv => $"{kv.Key}={kv.Value}"))}; " +
                    $"cap {p.Budget.Cap:N0} µUSD (USD {p.Budget.Cap / 1_000_000m:0.00})");
                if (mode == BatchMode.VerifyObservations)
                {
                    await using var ex = new PilotBatchExecutor(p);
                    var report = await PilotVerify.RunAsync(p, ex.ObserveCellAsync, Console.WriteLine);
                    return report.Pass ? 0 : 3;
                }
                return 0;
            }

            var caller = new AzureLlmCaller(Config.AzureOpenAiEndpoint);
            await PilotRunner.RunAsync(options, plan => new PilotBatchExecutor(plan), caller);
            return 0;
        }
        catch (BatchRefusedException ex)
        {
            Console.Error.WriteLine($"[batch] REFUSED: {ex.Message}");
            return 3;
        }
        catch (BatchStoppedException ex)
        {
            Console.Error.WriteLine($"[batch] STOPPED: {ex.Message}");
            return 4;
        }
    }

}

/// <summary>Outcome of <see cref="PilotVerify.RunAsync"/>; <see cref="Mismatches"/> name the cell and the hash seen.</summary>
public sealed record PilotVerifyReport(
    int Cells, int CellsOk, int Tokens, int TokensOk, int Cond5, int Cond5Ok, int Observations,
    IReadOnlyList<string> Mismatches)
{
    public bool Pass => CellsOk == Cells && TokensOk == Tokens && Cond5Ok == Cond5;
}

/// <summary>
/// Zero-LLM verification of the pilot by the run path: every cell the plan or the reuse map uses is
/// observed once, by <paramref name="observeCell"/> — in production PilotBatchExecutor.ObserveCellAsync,
/// a fresh offline load whose first walk is that cell, exactly as the paid run (and resume re-scoring)
/// builds it. Checks: sha256 == observations_manifest.tsv; every called event's input tokens == the plan;
/// condition 5 on B_full == the target's stratum. One cell per load, unlike the observation dump: on a
/// page whose DOM changes after load, walking several cells in one load depends on timing.
/// </summary>
public static class PilotVerify
{
    public static async Task<PilotVerifyReport> RunAsync(
        PilotPlan p, Func<PlanEvent, Task<(string ObsText, IReadOnlyDictionary<string, bool>? Cond5)>> observeCell,
        Action<string> log)
    {
        int cells = 0, cellsOk = 0, tok = 0, tokOk = 0, c5 = 0, c5Ok = 0, observations = 0;
        var mismatches = new List<string>();
        foreach (var site in p.Sites)
        {
            var used = p.Info.Values.Where(i => i.Event.Page == site.Key)
                                    .GroupBy(i => (i.Event.Bundle, i.Event.Encoding))
                                    .Select(g => g.OrderBy(i => i.Event.Key, StringComparer.Ordinal).First().Event)
                                    .OrderBy(e => e.Encoding, StringComparer.Ordinal).ThenBy(e => e.Bundle, StringComparer.Ordinal)
                                    .ToList();
            var obs = new Dictionary<(string, string), string>();
            IReadOnlyDictionary<string, bool>? cond5 = null;
            foreach (var e in used)
            {
                var (text, c) = await observeCell(e);
                observations++;
                obs[(e.Bundle, e.Encoding)] = text;
                if (e.Bundle == "B_full" && e.Encoding == "F1")
                {
                    cond5 = c;
                }
                var sha = Hashing.Sha256Hex(text);
                var ok = sha == p.ObservationSha[(site.Key, e.Bundle, e.Encoding)];
                cells++;
                cellsOk += ok ? 1 : 0;
                if (!ok)
                {
                    mismatches.Add($"{site.Key} {e.Bundle}×{e.Encoding} {sha}");
                }
                log($"  {(ok ? "ok      " : "MISMATCH")} {site.Key} {e.Bundle}×{e.Encoding} {sha[..12]}…");
            }
            foreach (var e in p.Events.Where(e => e.Page == site.Key))
            {
                var info = p.Info[e.Key];
                var live = Shared.Tokenizer.TokenCounter.CountTokens(GroundingRunner.SystemPrompt)
                           + Shared.Tokenizer.TokenCounter.CountTokens(
                               GroundingRunner.BuildUserPrompt(obs[(e.Bundle, e.Encoding)], info.Target.Task));
                tok++;
                if (live == info.InputTokens)
                {
                    tokOk++;
                }
                else
                {
                    log($"  TOKENS   {e.Key}: {live} != planned {info.InputTokens}");
                }
            }
            foreach (var t in p.TargetsBySite[site.Key])
            {
                var ok = cond5 is not null && cond5.TryGetValue(t.Marker, out var v) && v == (t.Stratum == "has stable signal");
                c5++;
                c5Ok += ok ? 1 : 0;
                if (!ok)
                {
                    log($"  COND5    {site.Key} {t.Marker}: {(cond5?.GetValueOrDefault(t.Marker))} vs stratum '{t.Stratum}'");
                }
            }
        }
        var report = new PilotVerifyReport(cells, cellsOk, tok, tokOk, c5, c5Ok, observations, mismatches);
        log($"[batch] pilot observations (run path: fresh load per cell): {cellsOk}/{cells} identical to " +
            $"observations_manifest.tsv; input tokens {tokOk}/{tok} == plan; condition 5 == stratum {c5Ok}/{c5}");
        return report;
    }
}
