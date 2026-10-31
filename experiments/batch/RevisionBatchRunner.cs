using System.Text.Json.Nodes;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;

namespace BoundedAgents.Experiments.Batch;

public sealed record BatchRunSummary(int Planned, int AlreadyDone, int NewRecords, int Replayed, int LlmCalls,
                                     int Rejected429, long SpentInputTokens)
{
    /// <summary>Pilot: records written for reused (not called) cells in this run.</summary>
    public int Reused { get; init; }
}

/// <summary>
/// The budget of a profile, in its ledger's unit. Batch: input tokens (spent = Σ native prompt_tokens,
/// bound = the reservation, cap = BAR_BATCH_MAX_INPUT_TOKENS). Pilot: µUSD at list price.
/// </summary>
public sealed record BudgetModel(
    string Unit, string CapName, string StopLabel, long Cap,
    Func<BatchJournal, long> Spent, Func<long, long> Bound)
{
    /// <summary>
    /// What the cap is checked against: Σ API-reported usage of the responses (<see cref="Spent"/>) + the bound of
    /// every released request with unknown outcome, which may have been billed (real_pilot/pilot_addendum_scoring.md (б)).
    /// </summary>
    public long Liability(BatchJournal j) => Spent(j) + j.ReleasedReservations.Sum(Bound);
}

/// <summary>
/// Pilot executors: how the latest evaluation passed the scoring checkpoint (addendum (а′)); written into every
/// pilot record (<see cref="BatchRecords.ScoringFields"/>).
/// </summary>
public interface IScoringReport
{
    ScoringResult? LastScoring { get; }
}

/// <summary>What the common run loop needs from a profile (built after its preflight passed).</summary>
public sealed class RunSpec
{
    public required string Title { get; init; }
    public required BatchExpectations X { get; init; }
    /// <summary>The selected called events, in run order.</summary>
    public required IReadOnlyList<PlanEvent> Order { get; init; }
    public required BudgetModel Budget { get; init; }
    public required string OutDir { get; init; }
    public required Func<string, string?> Env { get; init; }
    public required int MaxAttempts { get; init; }
    /// <summary>Pilot: o200k CountTokens(SystemPrompt) + CountTokens(user prompt) per key, as planned.</summary>
    public IReadOnlyDictionary<string, int>? PlannedInputTokens { get; init; }
}

/// <summary>
/// The paid batch. Order of guarantees, each before the first paid call:
/// preflight (plan / cells / deployments / pages / prompt / manifests / budget) → exclusive lock
/// → strict semantic journal + shard load → stop if any request has an unknown outcome
/// → every done record re-scored from its journaled locator against the live DOM (pilot: on a fresh load).
/// Per event: observation sha256 must equal the pinned dump → journaled response is replayed
/// (no call) → spent + released liability + reservation ≤ cap → "pending" (flushed) → call → "response"
/// (flushed) → oracle → record → stop if native usage exceeded the reservation.
/// A release (BAR_BATCH_RELEASE / BAR_BATCH_RELEASE_OVERRUN) is processed only on the execute path, after the lock
/// and the journal load: it writes "released" / "overrun_released" and stops (exit 4) before the executor is
/// created, with no request.
/// The pilot profile (<see cref="PilotRunner"/>) runs the same loop (<see cref="RunCoreAsync"/>).
/// </summary>
public static class RevisionBatchRunner
{
    public static async Task<BatchRunSummary> RunAsync(
        BatchOptions o, Func<IBatchExecutor> executorFactory, ILlmCaller caller,
        Func<TimeSpan, Task>? delay = null, Action<string>? log = null)
    {
        var pf = BatchPreflight.Run(o);
        var spec = new RunSpec
        {
            Title = $"Revision 1 batch — blocks {string.Join(",", pf.Blocks.Order())}",
            X = BatchExpectations.From(pf, o.ExpectedPlanSha256),
            Order = pf.Selected.OrderBy(x => x.Block, StringComparer.Ordinal)
                               .ThenBy(x => x.Model, StringComparer.Ordinal)
                               .ThenBy(x => x.Page, StringComparer.Ordinal)
                               .ThenBy(x => x.Bundle, StringComparer.Ordinal)
                               .ThenBy(x => x.Encoding, StringComparer.Ordinal)
                               .ThenBy(x => x.Repetition)
                               .ThenBy(x => x.TaskId, StringComparer.Ordinal).ToList(),
            Budget = new BudgetModel("input tokens", "BAR_BATCH_MAX_INPUT_TOKENS", "input-token cap", pf.MaxInputTokens,
                                     j => j.SpentInputTokens, reservation => reservation),
            OutDir = o.OutDir,
            Env = o.Env,
            MaxAttempts = o.MaxAttempts,
        };
        return await RunCoreAsync(spec, executorFactory, caller, delay, log);
    }

    /// <summary>The loop every profile runs; see the class summary for the order of guarantees.</summary>
    public static async Task<BatchRunSummary> RunCoreAsync(
        RunSpec o, Func<IBatchExecutor> executorFactory, ILlmCaller caller,
        Func<TimeSpan, Task>? delay = null, Action<string>? log = null)
    {
        delay ??= Task.Delay;
        log ??= Console.WriteLine;
        var x = o.X;
        var budget = o.Budget;

        Directory.CreateDirectory(o.OutDir);
        using var lockHandle = BatchLock.Acquire(o.OutDir);

        var journal = BatchJournal.Load(o.OutDir, x);
        var done = BatchRecords.LoadDone(o.OutDir, x, journal);

        // A budget overrun (native usage above the reservation) is persistent: it blocks every
        // start until it is released explicitly, after the budget model has been reviewed.
        var releaseOverrun = (o.Env("BAR_BATCH_RELEASE_OVERRUN") ?? "")
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var overruns = journal.OpenOverruns();
        if (releaseOverrun.Length > 0)
        {
            var notOpen = releaseOverrun.Where(k => !overruns.Contains(k)).ToList();
            if (notOpen.Count > 0)
            {
                throw new BatchRefusedException(
                    $"BAR_BATCH_RELEASE_OVERRUN names keys without an open overrun: {string.Join(", ", notOpen)}");
            }
            foreach (var k in releaseOverrun)
            {
                // Its usage is known (the response) and already counted; the line restates it for the record.
                var r = journal.ResponseFor(k)!;
                journal.Append(BatchJournal.OverrunReleased, k, new JsonObject
                {
                    ["attempt"] = journal.LastAttempt(k), ["reason"] = "operator BAR_BATCH_RELEASE_OVERRUN",
                    ["reservation"] = journal.ReservationOf(k),
                    ["prompt_tokens"] = r["prompt_tokens"]!.GetValue<long>(),
                    ["completion_tokens"] = r["completion_tokens"]!.GetValue<long>(),
                });
            }
            throw new BatchStoppedException(
                $"released {releaseOverrun.Length} overrun(s); unset BAR_BATCH_RELEASE_OVERRUN and start again");
        }
        if (overruns.Count > 0)
        {
            throw new BatchStoppedException(
                $"{overruns.Count} budget overrun(s) on record (native prompt_tokens > reservation) — no call made. " +
                $"Review the reservation model, then release explicitly via BAR_BATCH_RELEASE_OVERRUN=<key>[,…]: " +
                string.Join(", ", overruns));
        }
        if (budget.Liability(journal) > budget.Cap)
        {
            throw new BatchStoppedException(
                $"spent + released liability {budget.Liability(journal):N0} {budget.Unit} > {budget.CapName} {budget.Cap:N0} — no call made");
        }

        var release = (o.Env("BAR_BATCH_RELEASE") ?? "")
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var unknown = journal.UnknownKeys();
        if (release.Length > 0)
        {
            var notUnknown = release.Where(k => !unknown.Contains(k)).ToList();
            if (notUnknown.Count > 0)
            {
                throw new BatchRefusedException(
                    $"BAR_BATCH_RELEASE names keys without an unknown outcome: {string.Join(", ", notUnknown)}");
            }
            foreach (var k in release)
            {
                // The request may have been billed: its reservation stays a budget liability (BudgetModel.Liability).
                journal.Append(BatchJournal.Released, k, new JsonObject
                {
                    ["attempt"] = journal.LastAttempt(k), ["reason"] = "operator BAR_BATCH_RELEASE",
                    ["reservation"] = journal.ReservationOf(k),
                });
            }
            throw new BatchStoppedException(
                $"released {release.Length} key(s); unset BAR_BATCH_RELEASE and start again (they will be called)");
        }
        if (unknown.Count > 0)
        {
            throw new BatchStoppedException(
                $"{unknown.Count} request(s) with unknown outcome (pending/error without response) — no call made. " +
                $"Reconcile with the provider, then release explicitly via BAR_BATCH_RELEASE=<key>[,…]: " +
                string.Join(", ", unknown));
        }

        await using var executor = executorFactory();

        // Re-score every done record from its journaled locator; any difference refuses the run.
        foreach (var (key, rec) in done.OrderBy(kv => kv.Key, StringComparer.Ordinal))
        {
            var e = x.Plan.TryGetValue(key, out var called) ? called : x.Reused[key].Event;
            var recorded = BatchRecords.ScoreOf(rec);
            var recomputed = await executor.RescoreAsync(e, rec["locator_raw"]!.GetValue<string>());
            if (recomputed != recorded)
            {
                throw new BatchRefusedException(
                    $"{key}: recorded score {recorded} != score recomputed from the journaled locator {recomputed}");
            }
        }

        // Reused cells (pilot) whose called source is already done: a stop between the two writes.
        int reusedWritten = 0;
        var reusedBySource = x.Reused.Values.ToLookup(r => r.SourceKey, StringComparer.Ordinal);
        foreach (var re in x.Reused.Values.Where(r => !done.ContainsKey(r.Event.Key) && done.ContainsKey(r.SourceKey))
                                   .OrderBy(r => r.Event.Key, StringComparer.Ordinal).ToList())
        {
            await WriteReusedAsync(re);
        }

        var todo = o.Order.Where(e => !done.ContainsKey(e.Key)).ToList();
        log($"── {o.Title}: {o.Order.Count} planned, " +
            $"{o.Order.Count - todo.Count} on disk (re-scored), {todo.Count} to do; {budget.Unit} spent (+ released liability) so far " +
            $"{budget.Liability(journal):N0} / cap {budget.Cap:N0}");

        int newRecords = 0, replayed = 0, calls = 0, rejected = 0;
        foreach (var e in todo)
        {
            var deployment = x.DeploymentOf(e);
            var expectedSha = x.ObservationShaOf(e);
            string? obsSha = null;
            JsonObject? used = null;
            bool fromJournal = false;
            string? overReservation = null;

            async Task<LlmResponse> CallModel(string obsText, string userPrompt)
            {
                obsSha = Hashing.Sha256Hex(obsText);
                if (obsSha != expectedSha)
                {
                    throw new BatchRefusedException(
                        $"{e.Key}: observation sha256 {obsSha} != audited {expectedSha} — no call made");
                }
                if (o.PlannedInputTokens is { } planned)
                {
                    var live = TokenCounter.CountTokens(GroundingRunner.SystemPrompt) + TokenCounter.CountTokens(userPrompt);
                    if (live != planned[e.Key])
                    {
                        throw new BatchRefusedException(
                            $"{e.Key}: input tokens {live} != planned {planned[e.Key]} — no call made");
                    }
                }

                var prior = journal.ResponseFor(e.Key);
                if (prior is not null)
                {
                    used = prior;
                    fromJournal = true;
                    return ToResponse(prior);
                }

                var reservation = BatchBudget.Reservation(userPrompt);
                for (int n = 1; ; n++)
                {
                    // Before every attempt: the whole request must fit, in the ledger's unit.
                    if (budget.Liability(journal) + budget.Bound(reservation) > budget.Cap)
                    {
                        throw new BatchStoppedException(
                            $"{budget.StopLabel}: spent + released liability {budget.Liability(journal):N0} + reservation {budget.Bound(reservation):N0} > " +
                            $"{budget.CapName} {budget.Cap:N0} — stopped before {e.Key}, no call made");
                    }
                    var attempt = journal.NextAttempt(e.Key);
                    journal.Append(BatchJournal.Pending, e.Key, new JsonObject
                    {
                        ["attempt"] = attempt, ["deployment"] = deployment, ["observation_sha256"] = obsSha,
                        ["reservation"] = reservation,
                    });
                    LlmCallDetail d;
                    try
                    {
                        calls++;
                        d = await caller.CallAsync(GroundingRunner.SystemPrompt, userPrompt, deployment);
                    }
                    catch (LlmRateLimitedException rl)
                    {
                        rejected++;
                        var wait = rl.RetryAfter ?? TimeSpan.FromSeconds(Math.Pow(2, n));
                        journal.Append(BatchJournal.Rejected429, e.Key, new JsonObject
                        {
                            ["attempt"] = attempt, ["retry_after_ms"] = (long)wait.TotalMilliseconds,
                        });
                        if (n >= o.MaxAttempts)
                        {
                            throw new BatchStoppedException(
                                $"{e.Key}: HTTP 429 on all {o.MaxAttempts} attempts of this run — stopped (not executed; callable next run)");
                        }
                        log($"  [429] {e.Key} attempt {attempt} ({n}/{o.MaxAttempts} this run), waiting {wait.TotalSeconds:0.#} s");
                        await delay(wait);
                        continue;
                    }
                    catch (Exception ex)
                    {
                        journal.Append(BatchJournal.Error, e.Key, new JsonObject
                        {
                            ["attempt"] = attempt, ["message"] = $"{ex.GetType().Name}: {ex.Message}",
                        });
                        throw new BatchStoppedException(
                            $"{e.Key}: request failed with unknown outcome ({ex.GetType().Name}: {ex.Message}) — stopped, no retry");
                    }

                    journal.Append(BatchJournal.Response, e.Key, new JsonObject
                    {
                        ["attempt"] = attempt,
                        ["deployment"] = deployment,
                        ["locator_raw"] = d.Response.Content,
                        ["prompt_tokens"] = d.Response.PromptTokens,
                        ["completion_tokens"] = d.Response.CompletionTokens,
                        ["model_id"] = d.Response.ModelId,
                        ["response_model"] = d.ResponseModel,
                        ["finish_reason"] = d.FinishReason,
                        ["system_fingerprint"] = d.SystemFingerprint,
                        ["observation_sha256"] = obsSha,
                    });
                    used = journal.ResponseFor(e.Key);
                    var overOut = x.MaxCompletionTokens is long maxOut && d.Response.CompletionTokens > maxOut;
                    if (d.Response.PromptTokens > reservation || overOut)
                    {
                        // Persist the stop before anything else can fail: later starts refuse until released.
                        journal.Append(BatchJournal.BudgetOverrun, e.Key, new JsonObject
                        {
                            ["attempt"] = attempt, ["prompt_tokens"] = d.Response.PromptTokens, ["reservation"] = reservation,
                        });
                        overReservation = $"{e.Key}: native prompt_tokens {d.Response.PromptTokens} > reservation " +
                                          $"{reservation}" +
                                          (overOut ? $" or completion_tokens {d.Response.CompletionTokens} > {x.MaxCompletionTokens}" : "") +
                                          " — the budget model no longer bounds the next call; stopped";
                    }
                    return d.Response;
                }
            }

            var record = await executor.ExecuteAsync(e, deployment, CallModel);
            if (used is null || obsSha is null)
            {
                throw new BatchRefusedException($"{e.Key}: executor returned without passing the model gate");
            }

            var node = JsonNode.Parse(record.ToJsonl())!.AsObject();
            node["rep"] = e.Rep;
            node["block"] = e.Block;
            node["event_key"] = e.Key;
            node["plan_sha256"] = x.PlanSha256;
            node["observation_sha256"] = obsSha;
            node["response_model_id"] = used["response_model"]?.DeepClone();
            node["finish_reason"] = used["finish_reason"]?.DeepClone();
            node["system_fingerprint"] = used["system_fingerprint"]?.DeepClone();
            node["llm_attempts"] = used["attempt"]!.GetValue<int>();
            node["replayed_from_journal"] = fromJournal;
            if (x.MarksReuse)
            {
                node["reused"] = false;
                node["reused_from_event_key"] = null;
                SetScoring(node, e.Key);
            }
            StrictJsonl.AppendDurable(BatchRecords.ShardPath(o.OutDir, e, deployment), node);
            done[e.Key] = node;

            newRecords++;
            if (fromJournal)
            {
                replayed++;
            }
            log($"  [{newRecords,4}/{todo.Count}] {e.Key} b{e.Block} " +
                (record.Success ? "ok" : $"FAIL/{record.FailureMode}") +
                $"  obs={record.ObservationTokens} in={record.PromptTokensTotal} out={record.CompletionTokens}" +
                (fromJournal ? "  (replayed from journal)" : ""));
            foreach (var re in reusedBySource[e.Key])
            {
                await WriteReusedAsync(re);
            }
            if (overReservation is not null)
            {
                throw new BatchStoppedException(overReservation);
            }
        }

        var summary = new BatchRunSummary(o.Order.Count, o.Order.Count - todo.Count, newRecords, replayed,
                                          calls, rejected, journal.SpentInputTokens) { Reused = reusedWritten };
        log($"── Done: {summary}");
        return summary;

        // A reused cell: no call, no journal entry. Its observation is byte-identical to its source's,
        // so its score is recomputed (zero LLM; its own observation hash is part of the score) from the
        // source's locator and must equal the source's; the record is the source's, re-keyed and marked.
        async Task WriteReusedAsync(ReusedEvent re)
        {
            var e = re.Event;
            var src = done[re.SourceKey];
            var srcScore = BatchRecords.ScoreOf(src);
            var score = await executor.RescoreAsync(e, src["locator_raw"]!.GetValue<string>());
            if (score.ObservationSha256 != x.ObservationShaOf(e) || score != srcScore)
            {
                throw new BatchRefusedException(
                    $"{e.Key}: reused score {score} != source {re.SourceKey} score {srcScore} — not written");
            }
            var node = src.DeepClone().AsObject();
            node["run_id"] = Guid.NewGuid().ToString();
            node["bundle"] = e.Bundle;
            node["encoding"] = e.Encoding;
            node["task_id"] = e.TaskId;
            node["timestamp_utc"] = DateTimeOffset.UtcNow.ToString("O");
            node["rep"] = e.Rep;
            node["block"] = e.Block;
            node["event_key"] = e.Key;
            node["observation_sha256"] = x.ObservationShaOf(e);
            node["replayed_from_journal"] = false;
            node["reused"] = true;
            node["reused_from_event_key"] = re.SourceKey;
            SetScoring(node, e.Key);   // this record's own evaluation, not the source's
            StrictJsonl.AppendDurable(BatchRecords.ShardPath(o.OutDir, e, x.DeploymentOf(e)), node);
            done[e.Key] = node;
            reusedWritten++;
            log($"  [reused] {e.Key} ← {re.SourceKey} (no call)");
        }

        // Pilot records carry how their evaluation passed the scoring checkpoint (addendum (а′) point 4).
        void SetScoring(JsonObject node, string key)
        {
            var s = (executor as IScoringReport)?.LastScoring
                    ?? throw new BatchRefusedException($"{key}: the executor reported no scoring checkpoint — not written");
            node["scoring_attempts"] = s.Attempts;
            node["scoring_mutations"] = new JsonArray(s.Mutations.Select(m => (JsonNode?)JsonValue.Create(m)).ToArray());
            node["scoring_ms"] = s.Ms;
        }
    }

    private static LlmResponse ToResponse(JsonObject j) => new(
        j["locator_raw"]!.GetValue<string>(),
        j["prompt_tokens"]!.GetValue<int>(),
        j["completion_tokens"]!.GetValue<int>(),
        j["model_id"]!.GetValue<string>());
}
