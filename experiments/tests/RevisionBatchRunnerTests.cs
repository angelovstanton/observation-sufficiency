using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json.Nodes;
using BoundedAgents.Models;
using BoundedAgents.Experiments.Batch;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;
using Xunit;

namespace Experiments.Tests;

/// <summary>Fake model: counts calls; scripted outcomes (ok / 429 / failure). Never touches the network.</summary>
internal sealed class FakeCaller : ILlmCaller
{
    private readonly Queue<string> _script;
    public int Calls { get; private set; }
    /// <summary>Native usage to report; default = the two strings + 11 framing tokens (as measured).</summary>
    public int? PromptTokens { get; init; }

    public FakeCaller(params string[] script) => _script = new Queue<string>(script);

    public Task<LlmCallDetail> CallAsync(string systemPrompt, string userPrompt, string deployment)
    {
        Calls++;
        var step = _script.Count > 0 ? _script.Dequeue() : "ok";
        return step switch
        {
            "429" => throw new LlmRateLimitedException(TimeSpan.FromMilliseconds(1), new Exception("fake 429")),
            "fail" => throw new HttpRequestException("fake connection reset"),
            // Possibly billed outcomes: the request may have reached the model.
            "timeout" => throw new TaskCanceledException("fake client timeout after send", new TimeoutException()),
            "503" => throw new HttpRequestException("fake 503", null, System.Net.HttpStatusCode.ServiceUnavailable),
            _ => Task.FromResult(new LlmCallDetail(
                new LlmResponse("css:#fake",
                    PromptTokens ?? TokenCounter.CountTokens(systemPrompt) + TokenCounter.CountTokens(userPrompt) + 11,
                    7, deployment),
                ResponseModel: deployment + "-2025-04-14", FinishReason: "Stop", SystemFingerprint: "fp_fake")),
        };
    }
}

/// <summary>
/// Fake executor: a fixed observation text per cell, the canonical prompt, and a deterministic
/// fake score (success iff the locator is css:#fake) that RescoreAsync recomputes identically.
/// </summary>
internal sealed class FakeExecutor : IBatchExecutor
{
    public Func<PlanEvent, string> Observation { get; init; } = BatchFixture.ObsText;
    public bool ThrowAfterResponse { get; init; }

    public static BatchScore Score(string obs, string locatorRaw)
    {
        var (t, v) = GroundingRunner.ParseLocatorForReplay(locatorRaw);
        var ok = locatorRaw == "css:#fake";
        return new BatchScore(Hashing.Sha256Hex(obs), 3, t, v, ok, ok ? null : "model_grabbed_brittle_signal",
                              ok, ok, ok, ok, true);
    }

    public Task<BatchScore> RescoreAsync(PlanEvent e, string locatorRaw) =>
        Task.FromResult(Score(Observation(e), locatorRaw));

    public async Task<GroundingRecord> ExecuteAsync(
        PlanEvent e, string deployment, Func<string, string, Task<LlmResponse>> callModel)
    {
        var obs = Observation(e);
        var r = await callModel(obs, GroundingRunner.BuildUserPrompt(obs, "task " + e.TaskId));
        if (ThrowAfterResponse)
        {
            throw new InvalidOperationException("simulated crash after the paid response (oracle/browser)");
        }
        var sc = Score(obs, r.Content);
        return new GroundingRecord(
            RunId: Guid.NewGuid().ToString(), TaskId: e.TaskId, Page: $"pages/{e.Page}.html", Bundle: e.Bundle,
            Encoding: e.Encoding, Regime: "full_page", Model: deployment, Repetition: e.Repetition,
            ObservationTokens: sc.ObservationTokens, PromptTokensTotal: r.PromptTokens, CompletionTokens: r.CompletionTokens,
            LocatorRaw: r.Content, LocatorType: sc.LocatorType, LocatorValue: sc.LocatorValue, Success: sc.Success,
            FailureMode: sc.FailureMode, PredicateUniqueMatch: sc.PredicateUniqueMatch,
            PredicateMatchesOracle: sc.PredicateMatchesOracle, PredicateNonVolatile: sc.PredicateNonVolatile,
            PredicateNonPositional: sc.PredicateNonPositional,
            StableSignalPresentInBundle: sc.StableSignalPresentInBundle, ModelIdReturned: r.ModelId,
            TokenizerVersion: "o200k_base", SchemaVersion: "1.0", TestbedPage: $"pages/{e.Page}.html",
            TimestampUtc: DateTimeOffset.UtcNow.ToString("O"), Seed: 42);
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}

/// <summary>A tiny plan in the committed plan's format, in a temp directory: page_01 × t_01..t_03, gpt-4.1, B_full×F1.</summary>
internal sealed class BatchFixture : IDisposable
{
    public string Root { get; } = Path.Combine(Path.GetTempPath(), "batch_" + Guid.NewGuid().ToString("N")[..10]);
    public string PlanPath => Path.Combine(Root, "plan.json");
    public string OutDir => Path.Combine(Root, "out");
    public string ManifestPath => Path.Combine(Root, "manifest.tsv");
    public Dictionary<string, string?> Env { get; } = new()
    {
        ["BAR_MODEL_DEPLOYMENT_1"] = "gpt-4.1",
        ["BAR_BATCH_MAX_INPUT_TOKENS"] = "1000000000",
    };
    public List<JsonObject> Events { get; } = new();

    public static string ObsText(PlanEvent e) => $"OBS {e.Page} {e.Bundle} {e.Encoding}";

    public BatchFixture(int tasks = 3)
    {
        Directory.CreateDirectory(Root);
        for (int i = 1; i <= tasks; i++)
        {
            Events.Add(Ev("1", "gpt-4.1", "B_full", "F1", "page_01", $"t_{i:D2}", 0));
        }
        File.WriteAllText(ManifestPath,
            "page\tbundle\tencoding\ttokens\tsha256\n" +
            $"page_01\tB_full\tF1\t3\t{Hashing.Sha256Hex("OBS page_01 B_full F1")}\n");
        WritePlan();
    }

    public static JsonObject Ev(string block, string model, string bundle, string enc, string page, string task, int repetition) => new()
    {
        ["block"] = block, ["model"] = model, ["model_env"] = "BAR_MODEL_DEPLOYMENT_1", ["bundle"] = bundle,
        ["encoding"] = enc, ["page"] = page, ["task_id"] = task, ["repetition"] = repetition, ["rep"] = repetition + 1,
    };

    public void WritePlan() =>
        File.WriteAllText(PlanPath, new JsonObject { ["events"] = new JsonArray(Events.Select(e => (JsonNode)e.DeepClone()).ToArray()) }.ToJsonString());

    public BatchOptions Options(IReadOnlyDictionary<PlanCell, int>? cells = null) => new()
    {
        RepoRoot = Testbed.RepoRoot,
        PlanPath = PlanPath,
        ExpectedPlanSha256 = Hashing.FileSha256(PlanPath),
        OutDir = OutDir,
        AllowedCells = cells ?? new Dictionary<PlanCell, int> { [new("1", "gpt-4.1", "B_full", "F1", 1)] = Events.Count },
        ModelEnv = new Dictionary<string, string> { ["gpt-4.1"] = "BAR_MODEL_DEPLOYMENT_1" },
        ObservationManifests = new[] { (ManifestPath, Hashing.FileSha256(ManifestPath)) },
        ExpectedPagesDigest = BatchPins.PagesDigestSha256,
        ExpectedPromptDigest = BatchPins.PromptDigestSha256,
        Env = k => Env.GetValueOrDefault(k),
    };

    public Task<BatchRunSummary> Run(FakeCaller caller, FakeExecutor? ex = null, BatchOptions? o = null) =>
        RevisionBatchRunner.RunAsync(o ?? Options(), () => ex ?? new FakeExecutor(), caller,
                                     delay: _ => Task.CompletedTask, log: _ => { });

    public string JournalPath => Path.Combine(OutDir, "journal.jsonl");
    public string ShardPath => Path.Combine(OutDir, "batch_1_gpt-4-1_page_01.jsonl");
    public List<JsonObject> Journal() => File.Exists(JournalPath)
        ? File.ReadAllLines(JournalPath).Select(l => JsonNode.Parse(l)!.AsObject()).ToList() : new();
    public List<JsonObject> Records() => File.Exists(ShardPath)
        ? File.ReadAllLines(ShardPath).Select(l => JsonNode.Parse(l)!.AsObject()).ToList() : new();

    public void Dispose()
    {
        try { Directory.Delete(Root, recursive: true); } catch { }
    }
}

/// <summary>
/// Batch runner: journal, lock, strict resume, preflight, budget, retries.
/// Fake LLM client only, zero real model calls.
/// </summary>
public class RevisionBatchRunnerTests
{
    // Resume / journal

    [Fact]
    public async Task Restart_after_recorded_events_makes_no_new_calls()
    {
        using var fx = new BatchFixture();
        var c1 = new FakeCaller();
        var s1 = await fx.Run(c1);
        Assert.Equal((3, 3, 0), (c1.Calls, s1.NewRecords, s1.Replayed));

        var c2 = new FakeCaller();
        var s2 = await fx.Run(c2);
        Assert.Equal(0, c2.Calls);
        Assert.Equal((3, 0), (s2.AlreadyDone, s2.NewRecords));
        Assert.Equal(3, fx.Records().Count);
    }

    [Fact]
    public async Task Crash_after_response_before_record_is_recovered_from_journal_without_a_call()
    {
        using var fx = new BatchFixture(tasks: 1);
        var c1 = new FakeCaller();
        await Assert.ThrowsAsync<InvalidOperationException>(() => fx.Run(c1, new FakeExecutor { ThrowAfterResponse = true }));
        Assert.Equal(1, c1.Calls);
        Assert.Empty(fx.Records());
        Assert.Equal(new[] { "pending", "response" }, fx.Journal().Select(j => j["type"]!.GetValue<string>()));

        var c2 = new FakeCaller();
        var s2 = await fx.Run(c2);
        Assert.Equal(0, c2.Calls);
        Assert.Equal((1, 1), (s2.NewRecords, s2.Replayed));
        var rec = Assert.Single(fx.Records());
        Assert.True(rec["replayed_from_journal"]!.GetValue<bool>());
        Assert.Equal("css:#fake", rec["locator_raw"]!.GetValue<string>());
        Assert.Equal("gpt-4.1-2025-04-14", rec["response_model_id"]!.GetValue<string>());
        Assert.Equal("Stop", rec["finish_reason"]!.GetValue<string>());
    }

    [Fact]
    public async Task Pending_without_response_refuses_before_any_call_until_released()
    {
        using var fx = new BatchFixture(tasks: 2);
        var c1 = new FakeCaller("fail");                      // unknown outcome on the first event
        var stop = await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c1));
        Assert.Contains("unknown outcome", stop.Message);
        Assert.Equal(1, c1.Calls);

        var c2 = new FakeCaller();
        var again = await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c2));
        Assert.Contains("gpt-4.1|B_full|F1|page_01|t_01|0", again.Message);
        Assert.Equal(0, c2.Calls);

        // Operator release after reconciling: records "released" and stops — still no call.
        fx.Env["BAR_BATCH_RELEASE"] = "gpt-4.1|B_full|F1|page_01|t_01|0";
        var c3 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c3));
        Assert.Equal(0, c3.Calls);
        Assert.Equal("released", fx.Journal()[^1]["type"]!.GetValue<string>());

        fx.Env.Remove("BAR_BATCH_RELEASE");
        var c4 = new FakeCaller();
        var s4 = await fx.Run(c4);
        Assert.Equal((2, 2), (c4.Calls, s4.NewRecords));
    }

    /// <summary>Release liability, batch profile (input tokens): the released reservation counts against the cap.</summary>
    [Fact]
    public async Task Released_reservation_counts_against_the_input_token_cap()
    {
        using var fx = new BatchFixture(tasks: 2);
        const string key = "gpt-4.1|B_full|F1|page_01|t_01|0";
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(new FakeCaller("fail")));
        var reservation = fx.Journal().Single(j => j["type"]!.GetValue<string>() == "pending")["reservation"]!.GetValue<long>();
        fx.Env["BAR_BATCH_RELEASE"] = key;
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(new FakeCaller()));
        fx.Env.Remove("BAR_BATCH_RELEASE");
        Assert.Equal(reservation, fx.Journal()[^1]["reservation"]!.GetValue<long>());

        // liability r + the retry's own reservation r > cap (2r − 1): stopped before the retry, no call.
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = (2 * reservation - 1).ToString();
        var c1 = new FakeCaller();
        var stop = await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c1));
        Assert.Equal(0, c1.Calls);
        Assert.Contains("released liability", stop.Message);

        // Exactly at the cap (2r): the retry is called (attempt 2, own pending); the next event no longer fits.
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = (2 * reservation).ToString();
        var c2 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c2));
        Assert.Equal(1, c2.Calls);
        var pendings = fx.Journal().Where(j => j["type"]!.GetValue<string>() == "pending" && j["key"]!.GetValue<string>() == key).ToList();
        Assert.Equal(new[] { 1, 2 }, pendings.Select(j => j["attempt"]!.GetValue<int>()));
        Assert.Single(fx.Records());
    }

    /// <summary>
    /// A released line restates the pending's reservation; a different value refuses. A line without it (the batch
    /// journal of 295dddd, before the release-liability addendum) still loads, and its liability is the pending's.
    /// </summary>
    [Theory]
    [InlineData("legacy")]
    [InlineData("tampered")]
    public async Task Released_line_reservation_is_checked_and_a_legacy_line_without_it_loads(string variant)
    {
        using var fx = new BatchFixture(tasks: 2);
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(new FakeCaller("fail")));
        fx.Env["BAR_BATCH_RELEASE"] = "gpt-4.1|B_full|F1|page_01|t_01|0";
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(new FakeCaller()));
        fx.Env.Remove("BAR_BATCH_RELEASE");

        var lines = File.ReadAllLines(fx.JournalPath);
        var last = JsonNode.Parse(lines[^1])!.AsObject();
        var reservation = last["reservation"]!.GetValue<long>();
        if (variant == "legacy")
        {
            last.Remove("reservation");
        }
        else
        {
            last["reservation"] = reservation + 1;
        }
        lines[^1] = last.ToJsonString();
        File.WriteAllLines(fx.JournalPath, lines);

        var c = new FakeCaller();
        if (variant == "legacy")
        {
            var s = await fx.Run(c);
            Assert.Equal((2, 2), (c.Calls, s.NewRecords));
            var j = BatchJournal.Load(fx.OutDir, BatchExpectations.From(BatchPreflight.Run(fx.Options()), fx.Options().ExpectedPlanSha256));
            Assert.Equal(new[] { reservation }, j.ReleasedReservations);
        }
        else
        {
            var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
            Assert.Contains("reservation", ex.Message);
            Assert.Equal(0, c.Calls);
        }
    }

    [Fact]
    public async Task Hand_written_pending_line_refuses_before_any_call()
    {
        using var fx = new BatchFixture(tasks: 1);
        Directory.CreateDirectory(fx.OutDir);
        var pending = new JsonObject
        {
            ["type"] = "pending", ["key"] = "gpt-4.1|B_full|F1|page_01|t_01|0",
            ["plan_sha256"] = Hashing.FileSha256(fx.PlanPath), ["ts"] = "x",
            ["attempt"] = 1, ["deployment"] = "gpt-4.1", ["reservation"] = 1000,
            ["observation_sha256"] = Hashing.Sha256Hex("OBS page_01 B_full F1"),
        };
        File.WriteAllText(fx.JournalPath, pending.ToJsonString() + "\n");
        var c = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c));
        Assert.Equal(0, c.Calls);
    }

    [Theory]
    [InlineData("shard", true)]
    [InlineData("shard", false)]
    [InlineData("journal", true)]
    [InlineData("journal", false)]
    public async Task Partial_or_malformed_jsonl_line_refuses_and_leaves_the_file_untouched(string which, bool partialLast)
    {
        using var fx = new BatchFixture();
        await fx.Run(new FakeCaller());
        var path = which == "shard" ? fx.ShardPath : fx.JournalPath;
        var lines = File.ReadAllLines(path);
        var damaged = partialLast
            ? string.Join("\n", lines) + "\n" + lines[0][..20]                            // torn last line, no '\n'
            : lines[0] + "\n{not json\n" + string.Join("\n", lines.Skip(1)) + "\n";        // malformed middle line
        File.WriteAllText(path, damaged);
        var before = File.ReadAllBytes(path);

        var c = new FakeCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
        Assert.Equal(0, c.Calls);
        Assert.Equal(before, File.ReadAllBytes(path));
    }

    [Fact]
    public async Task Record_from_another_plan_or_without_journaled_response_refuses()
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());
        var rec = fx.Records()[0];
        rec["plan_sha256"] = new string('0', 64);
        File.WriteAllText(fx.ShardPath, rec.ToJsonString() + "\n");
        var c = new FakeCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));

        rec["plan_sha256"] = Hashing.FileSha256(fx.PlanPath);
        File.WriteAllText(fx.ShardPath, rec.ToJsonString() + "\n");
        File.Delete(fx.JournalPath);
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
        Assert.Contains("no journaled response", ex.Message);
        Assert.Equal(0, c.Calls);
    }

    // Lock

    [Fact]
    public async Task Second_runner_is_refused_before_any_call()
    {
        using var fx = new BatchFixture();
        Directory.CreateDirectory(fx.OutDir);
        using (BatchLock.Acquire(fx.OutDir))
        {
            var c = new FakeCaller();
            var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
            Assert.Contains("another batch runner", ex.Message);
            Assert.Equal(0, c.Calls);
        }
        var after = new FakeCaller();
        await fx.Run(after);
        Assert.Equal(3, after.Calls);
    }

    // Preflight

    [Fact]
    public async Task Wrong_deployment_on_the_slot_refuses()
    {
        using var fx = new BatchFixture();
        fx.Env["BAR_MODEL_DEPLOYMENT_1"] = "claude-sonnet-4.6";
        var c = new FakeCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
        Assert.Contains("BAR_MODEL_DEPLOYMENT_1", ex.Message);
        Assert.Equal(0, c.Calls);
        Assert.False(Directory.Exists(fx.OutDir));
    }

    private static Dictionary<string, string?> RealSlots() => new()
    {
        ["BAR_MODEL_DEPLOYMENT_1"] = "gpt-4.1",
        ["BAR_MODEL_DEPLOYMENT_2"] = "gpt-4.1-nano",
        ["BAR_MODEL_DEPLOYMENT_4"] = "o4-mini",
        ["BAR_BATCH_MAX_INPUT_TOKENS"] = "120000000",
    };

    [Fact]
    public void Production_preflight_passes_on_the_audited_plan_with_the_real_slots()
    {
        var env = RealSlots();
        var o = BatchPins.Production(Testbed.RepoRoot) with { Env = k => env.GetValueOrDefault(k) };
        var pf = BatchPreflight.Run(o);
        Assert.Equal(4500, pf.AllEvents.Count);
        Assert.Equal(4500, pf.Selected.Count);
        Assert.Equal(210, pf.ExpectedObservationSha.Count);
        Assert.Equal(BatchPins.PlanSha256, Hashing.FileSha256(o.PlanPath));
    }

    [Fact]
    public void Production_preflight_refuses_the_old_env_example_slot_layout()
    {
        var env = RealSlots();
        env["BAR_MODEL_DEPLOYMENT_3"] = "o4-mini";              // the old .env.example layout
        env["BAR_MODEL_DEPLOYMENT_4"] = "claude-sonnet-4.6";
        var o = BatchPins.Production(Testbed.RepoRoot) with { Env = k => env.GetValueOrDefault(k) };
        var ex = Assert.Throws<BatchRefusedException>(() => BatchPreflight.Run(o));
        Assert.Contains("BAR_MODEL_DEPLOYMENT_4", ex.Message);
    }

    [Fact]
    public void Production_preflight_refuses_a_changed_plan()
    {
        using var fx = new BatchFixture();
        var copy = Path.Combine(fx.Root, "batch_plan.json");
        var bytes = File.ReadAllBytes(Path.Combine(Testbed.RepoRoot, "experiments", "results", "revision1", "batch_plan.json"));
        File.WriteAllBytes(copy, bytes.Concat(new[] { (byte)' ' }).ToArray());
        var env = RealSlots();
        var o = BatchPins.Production(Testbed.RepoRoot) with { PlanPath = copy, Env = k => env.GetValueOrDefault(k) };
        var ex = Assert.Throws<BatchRefusedException>(() => BatchPreflight.Run(o));
        Assert.Contains("!= audited", ex.Message);
    }

    [Fact]
    public void Missing_budget_cap_refuses()
    {
        using var fx = new BatchFixture();
        fx.Env.Remove("BAR_BATCH_MAX_INPUT_TOKENS");
        var ex = Assert.Throws<BatchRefusedException>(() => BatchPreflight.Run(fx.Options()));
        Assert.Contains("BAR_BATCH_MAX_INPUT_TOKENS", ex.Message);
    }

    [Theory]
    [InlineData("duplicate")]
    [InlineData("outside")]
    [InlineData("rep")]
    [InlineData("unknown_task")]
    [InlineData("extra_field")]
    public async Task Invalid_plan_contents_refuse_even_with_a_matching_hash(string defect)
    {
        using var fx = new BatchFixture();
        switch (defect)
        {
            case "duplicate": fx.Events.Add((JsonObject)fx.Events[0].DeepClone()); break;
            case "outside": fx.Events[0]["bundle"] = "B_noState"; break;
            case "rep": fx.Events[0]["rep"] = 2; break;
            case "unknown_task": fx.Events[0]["task_id"] = "t_99"; break;
            case "extra_field": fx.Events[0]["temperature"] = 0.7; break;
        }
        fx.WritePlan();                                         // pin = this plan's own sha
        var c = new FakeCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
        Assert.Equal(0, c.Calls);
    }

    [Fact]
    public async Task Changed_observation_refuses_before_the_call_and_journals_nothing()
    {
        using var fx = new BatchFixture();
        var c = new FakeCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() =>
            fx.Run(c, new FakeExecutor { Observation = e => BatchFixture.ObsText(e) + "\r\n" }));
        Assert.Contains("observation sha256", ex.Message);
        Assert.Equal(0, c.Calls);
        Assert.Empty(fx.Journal());
        Assert.Empty(fx.Records());
    }

    [Fact]
    public async Task Changed_manifest_refuses()
    {
        using var fx = new BatchFixture();
        var o = fx.Options();
        File.AppendAllText(fx.ManifestPath, "page_02\tB_full\tF1\t3\t" + new string('a', 64) + "\n");
        var c = new FakeCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c, o: o));
        Assert.Equal(0, c.Calls);
    }

    // Entrypoint

    [Theory]
    [InlineData("AXIS_C")]
    [InlineData("LLM_SMOKE_TEST")]
    [InlineData("REVISION_BATCH")]
    [InlineData("BAR_PAGE_IDS")]
    [InlineData("BAR_BATCH_PLAN")]
    [InlineData("SENSITIVITY_CONSISTENT")]
    public void Conflicting_mode_flag_refuses_the_batch_entry(string flag)
    {
        var env = new Dictionary<string, string?> { [flag] = "1" };
        Assert.NotEmpty(BatchEntry.CheckFlags(k => env.GetValueOrDefault(k), Array.Empty<string>()));
    }

    [Fact]
    public void Batch_entry_accepts_only_its_own_arguments()
    {
        string? None(string _) => null;
        Assert.NotEmpty(BatchEntry.CheckFlags(None, Array.Empty<string>()));   // no mode given: refused
        Assert.Empty(BatchEntry.CheckFlags(None, new[] { "--preflight-only" }));
        Assert.NotEmpty(BatchEntry.CheckFlags(None, new[] { "--replay" }));
        Assert.NotEmpty(BatchEntry.CheckFlags(None, new[] { "--preflight-only", "--verify-observations" }));
    }

    [Fact]
    public void Batch_assembly_cannot_reach_the_matrix_or_axis_c()
    {
        var asm = typeof(RevisionBatchRunner).Assembly;
        Assert.DoesNotContain(asm.GetReferencedAssemblies(), a => a.Name == "Experiments");
        var types = asm.GetTypes().Select(t => t.Name).ToHashSet();
        foreach (var mode in new[] { "AxisCMode", "SummaryMode", "PerPageVerificationGate", "ConsistentSensitivityMode", "SmokeTests" })
        {
            Assert.DoesNotContain(mode, types);
        }
    }

    // Retries / budget

    [Fact]
    public async Task Rate_limit_is_retried_a_bounded_number_of_times()
    {
        using var fx = new BatchFixture(tasks: 1);
        var c = new FakeCaller("429", "429", "429", "ok");
        var s = await fx.Run(c);
        Assert.Equal(4, c.Calls);
        Assert.Equal((1, 3), (s.NewRecords, s.Rejected429));
        Assert.Equal(3, fx.Journal().Count(j => j["type"]!.GetValue<string>() == "rejected_429"));
        Assert.Equal(4, fx.Records()[0]["llm_attempts"]!.GetValue<int>());
    }

    [Fact]
    public async Task Persistent_rate_limit_stops_after_max_attempts_and_stays_callable()
    {
        using var fx = new BatchFixture(tasks: 1);
        var c1 = new FakeCaller("429", "429", "429", "429", "429");
        var ex = await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c1));
        Assert.Contains("429", ex.Message);
        Assert.Equal(4, c1.Calls);
        Assert.Empty(fx.Records());

        var c2 = new FakeCaller();
        await fx.Run(c2);
        Assert.Equal(1, c2.Calls);
    }

    [Fact]
    public async Task Input_token_cap_stops_before_the_call_and_persists_across_restarts()
    {
        using var fx = new BatchFixture(tasks: 3);
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = "10";             // below one prompt
        var c0 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c0));
        Assert.Equal(0, c0.Calls);
        Assert.Empty(fx.Journal());

        // One call fits (reservation R ≤ cap); after it spent = usage U = strings + 11, and U + R > cap.
        var strings = TokenCounter.CountTokens(GroundingRunner.SystemPrompt)
                      + TokenCounter.CountTokens(GroundingRunner.BuildUserPrompt("OBS page_01 B_full F1", "task t_01"));
        var reservation = strings + BatchBudget.FramingReserveTokens;
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = (reservation + strings + 11 - 1).ToString();
        var c1 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c1));
        Assert.Equal(1, c1.Calls);

        var c2 = new FakeCaller();                               // spent is read back from the journal
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c2));
        Assert.Equal(0, c2.Calls);
        Assert.Single(fx.Records());
    }

    [Fact]
    public async Task Records_carry_the_additive_fields_and_stay_in_the_output_directory()
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());
        var rec = Assert.Single(fx.Records());
        foreach (var f in BatchRecords.RecordFields)
        {
            Assert.True(rec.ContainsKey(f), f);
        }
        Assert.Equal(Hashing.Sha256Hex("OBS page_01 B_full F1"), rec["observation_sha256"]!.GetValue<string>());
        Assert.Equal("fp_fake", rec["system_fingerprint"]!.GetValue<string>());
        Assert.Equal(new[] { ".lock", "batch_1_gpt-4-1_page_01.jsonl", "journal.jsonl" },
                     Directory.GetFiles(fx.OutDir).Select(Path.GetFileName).Order(StringComparer.Ordinal));
    }

    [Fact]
    public void Output_directory_inside_p1_runs_refuses()
    {
        using var fx = new BatchFixture();
        var o = fx.Options() with { OutDir = Path.Combine(Testbed.RepoRoot, "experiments", "runs", "batch_runs") };
        Assert.Throws<BatchRefusedException>(() => BatchPreflight.Run(o));
        Assert.False(Directory.Exists(o.OutDir));
    }
}

/// <summary>
/// The production executor (python http.server + Playwright + GroundingRunner.RunOneStagedAsync)
/// with a fake model: observation bytes on this OS equal the committed dump (incl. F3 CRLF), and a
/// different expected hash refuses before the call.
/// </summary>
[Trait("Category", "Integration")]
public class RevisionBatchExecutorIntegrationTests
{
    private static int FreePort()
    {
        var l = new TcpListener(IPAddress.Loopback, 0);
        l.Start();
        var port = ((IPEndPoint)l.LocalEndpoint).Port;
        l.Stop();
        return port;
    }

    /// <summary>Plan: page_01 t_01 × {B_full×F1, B_noVolatile×F3}; manifest rows copied from the committed dump.</summary>
    private static (BatchFixture Fx, BatchOptions O) Setup(bool tamperF3)
    {
        var fx = new BatchFixture(tasks: 0);
        fx.Events.Add(BatchFixture.Ev("1", "gpt-4.1", "B_full", "F1", "page_01", "t_01", 0));
        fx.Events.Add(BatchFixture.Ev("1", "gpt-4.1", "B_noVolatile", "F3", "page_01", "t_01", 0));
        fx.WritePlan();
        var audited = File.ReadAllLines(
            Path.Combine(Testbed.RepoRoot, "experiments", "results", "revision1", "observations", "manifest.tsv"));
        var rows = audited.Where(l => l.StartsWith("page_01\tB_full\tF1\t") || l.StartsWith("page_01\tB_noVolatile\tF3\t"))
                          .Select(l => tamperF3 && l.Contains("\tF3\t") ? l[..^64] + new string('b', 64) : l)
                          .ToList();
        Assert.Equal(2, rows.Count);
        File.WriteAllText(fx.ManifestPath, audited[0] + "\n" + string.Join("\n", rows) + "\n");
        var o = fx.Options(new Dictionary<PlanCell, int>
        {
            [new("1", "gpt-4.1", "B_full", "F1", 1)] = 1,
            [new("1", "gpt-4.1", "B_noVolatile", "F3", 1)] = 1,
        });
        return (fx, o);
    }

    [Fact]
    public async Task Real_observations_match_the_audited_dump_and_one_call_per_event()
    {
        var (fx, o) = Setup(tamperF3: false);
        using (fx)
        {
            var c = new FakeCaller();
            var baseUrl = $"http://127.0.0.1:{FreePort()}";
            var s = await RevisionBatchRunner.RunAsync(o, () => new PlaywrightBatchExecutor(Testbed.RepoRoot, baseUrl), c,
                                                       log: _ => { });
            Assert.Equal((2, 2), (c.Calls, s.NewRecords));
            var shard = Path.Combine(fx.OutDir, "batch_1_gpt-4-1_page_01.jsonl");
            var recs = File.ReadAllLines(shard).Select(l => JsonNode.Parse(l)!.AsObject()).ToList();
            Assert.Equal(2, recs.Count);
            Assert.All(recs, r => Assert.Equal("full_page", r["regime"]!.GetValue<string>()));
            Assert.All(recs, r => Assert.True(r["observation_tokens"]!.GetValue<int>() > 1000));
        }
    }

    [Fact]
    public async Task A_different_audited_hash_refuses_before_the_call()
    {
        var (fx, o) = Setup(tamperF3: true);
        using (fx)
        {
            var c = new FakeCaller();
            var baseUrl = $"http://127.0.0.1:{FreePort()}";
            var ex = await Assert.ThrowsAsync<BatchRefusedException>(() =>
                RevisionBatchRunner.RunAsync(o, () => new PlaywrightBatchExecutor(Testbed.RepoRoot, baseUrl), c,
                                             log: _ => { }));
            Assert.Contains("observation sha256", ex.Message);
            Assert.Equal(1, c.Calls);                            // the B_full×F1 event ran; the F3 one was refused
        }
    }
}
