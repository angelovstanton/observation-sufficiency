using BoundedAgents.Experiments.Batch;
using BoundedAgents.Shared.Harness;

// Paid batch: the only way to execute experiments/results/revision1/batch_plan.json.
//
//   dotnet run --project experiments/batch -- --preflight-only        static checks, zero LLM
//   dotnet run --project experiments/batch -- --verify-observations   + every planned observation vs the
//                                                            pinned dump (browser), zero LLM
//   BAR_BATCH_MAX_INPUT_TOKENS=<n> BAR_BATCH_CONFIRM_PLAN=<12 chars of the plan sha256>
//     dotnet run --project experiments/batch -- --execute             the paid run
//
// There is no default mode: without arguments, or with BAR_BATCH_CONFIRM_PLAN set without
// --execute, nothing runs (exit 2). BAR_BATCH_CONFIRM_PLAN is the "plan" prefix printed by
// --preflight-only, set in the process for one run (a .env line naming it is refused).
//
// Optional: BAR_BATCH_BLOCKS=1,2 (subset), BAR_BATCH_RELEASE=<key>[,…] (operator release of a
// request with unknown outcome, after reconciling with the provider; nothing is called). A release is read
// only with --execute and the confirmation (there is no release-only mode): it is journaled ("released",
// with the request's reservation, which stays a budget liability) and the run stops, exit 4, before the
// executor is created and before any request. Unset it and start again.
//
// Real-site pilot, only with "--plan pilot" (experiments/results/revision1/real_pilot/pilot_plan.json; cap from
// the plan, µUSD; output under experiments/results/revision1/batch_runs_pilot/; confirm = the pilot plan's prefix):
//   dotnet run --project experiments/batch -- --plan pilot (--preflight-only | --verify-observations | --execute)
// Exit: 0 ok · 2 refused to start (flags) · 3 preflight/consistency refusal · 4 stopped · 1 other.
// Output only under experiments/results/revision1/batch_runs/ (pilot: batch_runs_pilot/): records, journal.jsonl, .lock.

Console.OutputEncoding = System.Text.Encoding.UTF8;

// Read the .env Config will load with the same parser (DotNetEnv), without loading it. Refuse on an
// unparseable file, any REVISION_BATCH line, a BAR_BATCH line the parser does not set, or any
// BAR_BATCH_CONFIRM line.
var dotEnvProblems = BoundedAgents.Experiments.LegacyBatchGuard.DotEnvProblems(AppContext.BaseDirectory)
    .Concat(BatchEntry.DotEnvConfirmProblems(AppContext.BaseDirectory)).ToList();
if (dotEnvProblems.Count > 0)
{
    return BatchEntry.Refuse(dotEnvProblems);
}

// Before and after .env is loaded (Config's static constructor loads it into the process env).
var flagProblems = BatchEntry.CheckFlags(Environment.GetEnvironmentVariable, args);
if (flagProblems.Count > 0)
{
    return BatchEntry.Refuse(flagProblems);
}
_ = Config.TestbedBaseUrl;

var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
return await BatchEntry.RunAsync(Environment.GetEnvironmentVariable, args, async (pilot, mode) =>
{
    if (pilot)
    {
        // Second profile, only with "--plan pilot" (same guards above; own pins, journal and records).
        return await PilotEntry.RunAsync(repoRoot, mode);
    }
    var options = BatchPins.Production(repoRoot);

    try
    {
        if (mode != BatchMode.Execute)
        {
            var pf = BatchPreflight.Run(options);
            Console.WriteLine($"[batch] preflight PASS: plan {BatchPins.PlanSha256[..12]}…, {pf.AllEvents.Count} events, " +
                              $"blocks {string.Join(",", pf.Blocks.Order())} → {pf.Selected.Count} selected; " +
                              $"deployments {string.Join(", ", pf.Deployments.Select(kv => $"{kv.Key}={kv.Value}"))}; " +
                              $"{pf.ExpectedObservationSha.Count} observation cells pinned; cap {pf.MaxInputTokens:N0}");
            if (mode == BatchMode.VerifyObservations)
            {
                var cells = pf.AllEvents.Select(e => (e.Page, e.Bundle, e.Encoding)).Distinct()
                              .OrderBy(c => c.Page, StringComparer.Ordinal).ThenBy(c => c.Bundle, StringComparer.Ordinal)
                              .ThenBy(c => c.Encoding, StringComparer.Ordinal).ToList();
                int bad = 0;
                await using var ex = new PlaywrightBatchExecutor(repoRoot);
                foreach (var (page, bundle, enc) in cells)
                {
                    var sha = Hashing.Sha256Hex(await ex.BuildObservationAsync(page, bundle, enc));
                    var ok = sha == pf.ExpectedObservationSha[(page, bundle, enc)];
                    bad += ok ? 0 : 1;
                    Console.WriteLine($"  {(ok ? "ok      " : "MISMATCH")} {page} {bundle}×{enc} {sha[..12]}…");
                }
                Console.WriteLine($"[batch] observations: {cells.Count - bad}/{cells.Count} identical to the audited dump");
                return bad == 0 ? 0 : 3;
            }
            return 0;
        }

        var caller = new AzureLlmCaller(Config.AzureOpenAiEndpoint);
        await RevisionBatchRunner.RunAsync(options, () => new PlaywrightBatchExecutor(repoRoot), caller);
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
});
