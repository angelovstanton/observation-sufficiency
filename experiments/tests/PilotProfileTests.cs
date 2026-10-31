using System.Reflection;
using System.Text.Json.Nodes;
using BoundedAgents.Models;
using BoundedAgents.Experiments.Batch;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;
using Xunit;

namespace Experiments.Tests;

/// <summary>Fake model for the pilot: scripted outcomes, configurable native usage. Never touches the network.</summary>
internal sealed class PilotCaller : ILlmCaller
{
    private readonly Queue<string> _script;
    public int Calls { get; private set; }
    /// <summary>Extra prompt tokens above the two strings (the API's chat framing).</summary>
    public int Framing { get; init; } = 11;
    public int CompletionTokens { get; init; } = 7;

    public PilotCaller(params string[] script) => _script = new Queue<string>(script);

    public Task<LlmCallDetail> CallAsync(string systemPrompt, string userPrompt, string deployment)
    {
        Calls++;
        var step = _script.Count > 0 ? _script.Dequeue() : "ok";
        return step switch
        {
            "429" => throw new LlmRateLimitedException(TimeSpan.FromMilliseconds(1), new Exception("fake 429")),
            "timeout" => throw new TaskCanceledException("fake client timeout after send", new TimeoutException()),
            "503" => throw new HttpRequestException("fake 503", null, System.Net.HttpStatusCode.ServiceUnavailable),
            _ => Task.FromResult(new LlmCallDetail(
                new LlmResponse("css:#fake",
                    TokenCounter.CountTokens(systemPrompt) + TokenCounter.CountTokens(userPrompt) + Framing,
                    CompletionTokens, deployment),
                ResponseModel: deployment + "-2025-04-14", FinishReason: "Stop", SystemFingerprint: "fp_fake")),
        };
    }
}

/// <summary>Fake pilot executor: fixed observation per cell, the target's task, FakeExecutor's deterministic score.</summary>
internal sealed class PilotFakeExecutor(PilotPlan p, Func<PlanEvent, string>? observation = null, Func<PlanEvent, string>? task = null)
    : IBatchExecutor, IScoringReport
{
    private readonly Func<PlanEvent, string> _obs = observation ?? (e => PilotFixture.ObsText(e.Page, e.Bundle, e.Encoding));
    private readonly Func<PlanEvent, string> _task = task ?? (e => p.Info[e.Key].Target.Task);

    /// <summary>As the real executor reports it: one load, no mutation in the window.</summary>
    public ScoringResult? LastScoring { get; private set; }

    public Task<BatchScore> RescoreAsync(PlanEvent e, string locatorRaw)
    {
        var sc = FakeExecutor.Score(_obs(e), locatorRaw);
        LastScoring = new ScoringResult(sc, 1, new[] { 0 }, 0);
        return Task.FromResult(sc);
    }

    public async Task<GroundingRecord> ExecuteAsync(PlanEvent e, string deployment, Func<string, string, Task<LlmResponse>> callModel)
    {
        var obs = _obs(e);
        var r = await callModel(obs, GroundingRunner.BuildUserPrompt(obs, _task(e)));
        var sc = FakeExecutor.Score(obs, r.Content);
        LastScoring = new ScoringResult(sc, 1, new[] { 0 }, 0);
        return new GroundingRecord(
            RunId: Guid.NewGuid().ToString(), TaskId: e.TaskId, Page: e.Page, Bundle: e.Bundle, Encoding: e.Encoding,
            Regime: "full_page", Model: deployment, Repetition: e.Repetition, ObservationTokens: sc.ObservationTokens,
            PromptTokensTotal: r.PromptTokens, CompletionTokens: r.CompletionTokens, LocatorRaw: r.Content,
            LocatorType: sc.LocatorType, LocatorValue: sc.LocatorValue, Success: sc.Success, FailureMode: sc.FailureMode,
            PredicateUniqueMatch: sc.PredicateUniqueMatch, PredicateMatchesOracle: sc.PredicateMatchesOracle,
            PredicateNonVolatile: sc.PredicateNonVolatile, PredicateNonPositional: sc.PredicateNonPositional,
            StableSignalPresentInBundle: sc.StableSignalPresentInBundle, ModelIdReturned: r.ModelId,
            TokenizerVersion: TokenCounter.TokenizerVersion(), SchemaVersion: GroundingRunner.SchemaVersion,
            TestbedPage: e.Page, TimestampUtc: DateTimeOffset.UtcNow.ToString("O"), Seed: Config.RandomSeed);
    }

    public ValueTask DisposeAsync() => ValueTask.CompletedTask;
}

/// <summary>
/// A miniature pilot in a temp directory, built like the real one: sites 0001_a.com and 0002_b.com
/// (2 targets each), excluded site x.com (in targets.json only). On a.com the class_only observation is
/// byte-identical to B_noVolatile (reused, 4 cells); on b.com it differs (called). 20 called events.
/// </summary>
internal sealed class PilotFixture : IDisposable
{
    public string Root { get; } = Path.Combine(Path.GetTempPath(), "pilot_" + Guid.NewGuid().ToString("N")[..10]);
    public string P(string name) => Path.Combine(Root, name);
    public string OutDir => P("out");
    public Dictionary<string, string?> Env { get; } = new() { ["BAR_MODEL_DEPLOYMENT_1"] = "gpt-4.1" };
    public long Cap { get; set; } = 1_000_000_000_000;

    public const string ClassOnly = "B_full_minus_volClass", Nvc = "B_noVolatileConsistent";
    public static readonly (int Rank, string Domain)[] Sites = { (1, "a.com"), (2, "b.com") };
    public static readonly string[] Cells = { "B_full", Nvc, ClassOnly };
    public static readonly string[] Encodings = { "F1", "F3" };

    public JsonObject Plan { get; }
    public JsonObject Reuse { get; }
    public JsonObject Targets { get; }
    public JsonObject SitesJson { get; }

    public static string Key(string bundle, string enc, string page, string task) => $"gpt-4.1|{bundle}|{enc}|{page}|{task}|0";

    /// <summary>a.com: class_only == B_noVolatile (reused); b.com: they differ (called).</summary>
    public static string ObsText(string page, string bundle, string enc) =>
        page.EndsWith("a.com") && bundle == ClassOnly ? $"OBS {page} {Nvc} {enc}" : $"OBS {page} {bundle} {enc}";

    public static string TaskText(string domain, string marker) => $"Click the link labelled '{domain} {marker}'";

    public static int InputTokens(string page, string bundle, string enc, string task) =>
        TokenCounter.CountTokens(GroundingRunner.SystemPrompt)
        + TokenCounter.CountTokens(GroundingRunner.BuildUserPrompt(ObsText(page, bundle, enc), task));

    public PilotFixture()
    {
        Directory.CreateDirectory(P("html"));
        var label = new Dictionary<string, string> { ["B_full"] = "B_full", [Nvc] = "B_noVolatile", [ClassOnly] = "class_only" };

        var items = new JsonArray();
        foreach (var (rank, domain) in Sites.Append((3, "x.com")))
        {
            foreach (var marker in new[] { "t_01", "t_02" })
            {
                var xpath = $"/html[1]/body[1]/a[{marker[^1]}]";
                items.Add(new JsonObject
                {
                    ["domain"] = domain, ["rank"] = rank, ["marker"] = marker, ["xpath"] = xpath, ["role"] = "link",
                    ["name"] = $"{domain} {marker}", ["task"] = TaskText(domain, marker), ["stratum"] = "has stable signal",
                    ["signal_attrs"] = new JsonArray("href"), ["sha256_key"] = Hashing.Sha256Hex($"{domain}|{xpath}"),
                });
            }
        }
        Targets = new JsonObject { ["items"] = items };

        var manifest = "domain\trank\tcell_bundle\tcode_bundle\tencoding\ttokens\tsha256\n";
        var sites = new JsonArray();
        foreach (var (rank, domain) in Sites.Append((3, "x.com")))
        {
            var page = $"{rank:D4}_{domain}";
            foreach (var enc in Encodings)
            {
                foreach (var b in Cells)
                {
                    manifest += $"{domain}\t{rank}\t{label[b]}\t{b}\t{enc}\t3\t{Hashing.Sha256Hex(ObsText(page, b, enc))}\n";
                }
            }
            if (domain == "x.com")
            {
                continue;
            }
            var html = System.Text.Encoding.UTF8.GetBytes($"<html><body><a href='/1'>1</a><a href='/2'>2</a> {domain}</body></html>");
            File.WriteAllBytes(P(Path.Combine("html", $"{page}.html")), html);
            sites.Add(new JsonObject
            {
                ["rank"] = rank, ["domain"] = domain, ["key"] = page, ["url"] = $"https://{domain}/",
                ["timestamp"] = "2026-05-21T17:39:04Z", ["html_file"] = $"{page}.html", ["html_bytes"] = html.Length,
                ["html_sha256"] = Hashing.Sha256Hex(html), ["vol_ids"] = new JsonArray(), ["vol_classes"] = new JsonArray("x-1"),
            });
        }
        File.WriteAllText(P("manifest.tsv"), manifest);
        SitesJson = new JsonObject { ["count"] = sites.Count, ["sites"] = sites };
        File.WriteAllText(P("shim.js"), "// fixed Math.random\n");

        var events = new JsonArray();
        var reuse = new JsonArray();
        foreach (var (rank, domain) in Sites)
        {
            var page = $"{rank:D4}_{domain}";
            foreach (var marker in new[] { "t_01", "t_02" })
            {
                foreach (var enc in Encodings)
                {
                    foreach (var b in Cells)
                    {
                        if (b == ClassOnly && domain == "a.com")
                        {
                            var sha = Hashing.Sha256Hex(ObsText(page, b, enc));
                            reuse.Add(new JsonObject
                            {
                                ["class_only_event_key"] = Key(b, enc, page, marker),
                                ["reused_event_key"] = Key(Nvc, enc, page, marker),
                                ["domain"] = domain, ["page"] = page, ["task_id"] = marker, ["encoding"] = enc,
                                ["class_only_observation_sha256"] = sha, ["b_novolatile_observation_sha256"] = sha,
                            });
                            continue;
                        }
                        var xpath = $"/html[1]/body[1]/a[{marker[^1]}]";
                        events.Add(new JsonObject
                        {
                            ["block"] = "pilot", ["model"] = "gpt-4.1", ["model_env"] = "BAR_MODEL_DEPLOYMENT_1",
                            ["bundle"] = b, ["encoding"] = enc, ["page"] = page, ["task_id"] = marker,
                            ["repetition"] = 0, ["rep"] = 1, ["event_key"] = Key(b, enc, page, marker), ["cell"] = label[b],
                            ["domain"] = domain, ["rank"] = rank, ["target_sha256_key"] = Hashing.Sha256Hex($"{domain}|{xpath}"),
                            ["xpath"] = xpath, ["task"] = TaskText(domain, marker), ["stratum"] = "has stable signal",
                            ["observation_sha256"] = Hashing.Sha256Hex(ObsText(page, b, enc)),
                            ["input_tokens"] = InputTokens(page, b, enc, TaskText(domain, marker)),
                        });
                    }
                }
            }
        }
        var perCell = new JsonObject();
        foreach (var b in Cells)
        {
            foreach (var enc in Encodings)
            {
                var sel = events.Where(e => e!["bundle"]!.GetValue<string>() == b && e["encoding"]!.GetValue<string>() == enc).ToList();
                perCell[$"{label[b]}|{enc}"] = new JsonObject
                {
                    ["calls"] = sel.Count, ["input_tokens"] = sel.Sum(e => (long)e!["input_tokens"]!.GetValue<int>()),
                };
            }
        }
        Plan = new JsonObject
        {
            ["settings"] = new JsonObject { ["model"] = "gpt-4.1", ["max_output_tokens"] = 256 },
            ["excluded_sites"] = new JsonArray(new JsonObject { ["domain"] = "x.com", ["reason"] = "test" }),
            ["counts"] = new JsonObject { ["pilot"] = events.Count },
            ["per_cell"] = perCell,
            ["class_only_not_called"] = reuse.Count,
            ["budget"] = new JsonObject
            {
                ["planned_calls"] = events.Count,
                ["planned_input_tokens"] = events.Sum(e => (long)e!["input_tokens"]!.GetValue<int>()),
                ["max_output_tokens"] = 256,
                ["price_usd_per_1M"] = new JsonObject { ["input"] = 2.0, ["output"] = 8.0 },
                ["hard_cap_usd"] = 109.12,
            },
            ["events"] = events,
        };
        WriteAll(planOnly: false);
        Reuse = new JsonObject { ["plan_sha256"] = Hashing.FileSha256(P("plan.json")), ["count"] = reuse.Count, ["reuse"] = reuse };
        Write("reuse.json", Reuse);
    }

    public void Write(string name, JsonObject o) => File.WriteAllText(P(name), o.ToJsonString());

    public void WriteAll(bool planOnly = true)
    {
        Write("plan.json", Plan);
        if (!planOnly)
        {
            Write("targets.json", Targets);
            Write("sites.json", SitesJson);
        }
    }

    public JsonArray Events => Plan["events"]!.AsArray();
    public int CalledCount => Events.Count;

    /// <summary>Options pinned to the files as they are now (call after any deliberate fixture edit).</summary>
    public PilotOptions Options()
    {
        // The plan's hard cap is the cap under test; the reuse map names the plan's current sha256.
        Plan["budget"]!["hard_cap_usd"] = Cap / 1_000_000m;
        Write("plan.json", Plan);
        if (Reuse is not null)
        {
            Reuse["plan_sha256"] = Hashing.FileSha256(P("plan.json"));
            Write("reuse.json", Reuse);
        }
        var events = Events.Select(e => e!.AsObject()).ToList();
        return new PilotOptions
        {
            RepoRoot = Testbed.RepoRoot,
            PlanPath = P("plan.json"), ExpectedPlanSha256 = Hashing.FileSha256(P("plan.json")),
            ReuseMapPath = P("reuse.json"), ExpectedReuseMapSha256 = Hashing.FileSha256(P("reuse.json")),
            TargetsPath = P("targets.json"), ExpectedTargetsSha256 = Hashing.FileSha256(P("targets.json")),
            ManifestPath = P("manifest.tsv"), ExpectedManifestSha256 = Hashing.FileSha256(P("manifest.tsv")),
            SitesPath = P("sites.json"), ExpectedSitesSha256 = Hashing.FileSha256(P("sites.json")),
            ShimPath = P("shim.js"),
            ExpectedShimSha256 = Hashing.Sha256Hex(File.ReadAllText(P("shim.js")).Replace("\r\n", "\n")),
            HtmlDir = P("html"),
            ExpectedPromptDigest = BatchPins.PromptDigestSha256,
            OutDir = OutDir,
            AllowedCells = events.GroupBy(e => (e["bundle"]!.GetValue<string>(), e["encoding"]!.GetValue<string>()))
                                 .ToDictionary(g => g.Key, g => g.Count()),
            ModelEnv = PilotPins.ModelEnv,
            PlannedCalls = events.Count,
            PlannedInputTokens = events.Sum(e => e["input_tokens"] is JsonValue v && v.TryGetValue<int>(out var i) ? (long)i : 0),
            ReusedCount = Reuse?["count"]?.GetValue<int>() ?? 4,
            SiteCount = Sites.Length,
            TargetCount = Sites.Length * 2,
            CapMicroUsd = Cap,
            InputMicroUsdPerToken = 2,
            OutputMicroUsdPerToken = 8,
            MaxCompletionTokens = 256,
            Env = k => Env.GetValueOrDefault(k),
        };
    }

    public Task<BatchRunSummary> Run(PilotOptions o, ILlmCaller caller, Func<PilotPlan, IBatchExecutor>? exec = null) =>
        PilotRunner.RunAsync(o, exec ?? (p => new PilotFakeExecutor(p)), caller, _ => Task.CompletedTask, _ => { });

    public List<JsonObject> Records() =>
        Directory.GetFiles(OutDir, "batch_*.jsonl").SelectMany(f => File.ReadAllLines(f))
                 .Select(l => JsonNode.Parse(l)!.AsObject()).ToList();

    public List<JsonObject> Journal() =>
        File.Exists(Path.Combine(OutDir, "journal.jsonl"))
            ? File.ReadAllLines(Path.Combine(OutDir, "journal.jsonl")).Select(l => JsonNode.Parse(l)!.AsObject()).ToList()
            : new List<JsonObject>();

    public void Dispose()
    {
        try { Directory.Delete(Root, recursive: true); } catch { }
    }
}

/// <summary>The pilot profile (--plan pilot): preflight (a)–(c), budget, persistent stops, resume, reuse.</summary>
public sealed class PilotProfileTests
{
    private static void Refused(PilotOptions o, string fragment)
    {
        var ex = Assert.Throws<BatchRefusedException>(() => PilotPreflight.Run(o));
        Assert.Contains(fragment, ex.Message);
    }

    // Happy path and reuse

    [Fact]
    public async Task Pilot_runs_called_events_and_writes_reused_cells_without_a_call()
    {
        using var f = new PilotFixture();
        var caller = new PilotCaller();
        var s = await f.Run(f.Options(), caller);

        Assert.Equal(20, f.CalledCount);
        Assert.Equal(20, caller.Calls);
        Assert.Equal(20, s.NewRecords);
        Assert.Equal(4, s.Reused);
        var recs = f.Records();
        Assert.Equal(24, recs.Count);
        var reused = recs.Where(r => r["reused"]!.GetValue<bool>()).ToList();
        Assert.Equal(4, reused.Count);
        foreach (var r in reused)
        {
            var key = r["event_key"]!.GetValue<string>();
            var src = r["reused_from_event_key"]!.GetValue<string>();
            Assert.Equal(PilotFixture.ClassOnly, r["bundle"]!.GetValue<string>());
            Assert.Equal(key.Replace(PilotFixture.ClassOnly, PilotFixture.Nvc), src);
            var source = recs.Single(x => x["event_key"]!.GetValue<string>() == src);
            foreach (var field in new[] { "locator_raw", "success", "failure_mode", "observation_sha256", "prompt_tokens_total",
                                          "predicate_unique_match", "stable_signal_present_in_bundle", "llm_attempts" })
            {
                Assert.Equal(source[field]?.ToJsonString(), r[field]?.ToJsonString());
            }
            Assert.False(r["replayed_from_journal"]!.GetValue<bool>());
        }
        Assert.All(recs.Where(r => !r["reused"]!.GetValue<bool>()), r => Assert.Null(r["reused_from_event_key"]));
        // No journal entry ever names a reused key.
        Assert.DoesNotContain(f.Journal(), j => j["key"]!.GetValue<string>().Contains(PilotFixture.ClassOnly)
                                                  && j["key"]!.GetValue<string>().Contains("a.com"));

        // Restart: everything re-scored, nothing called, nothing written.
        var again = new PilotCaller();
        var s2 = await f.Run(f.Options(), again);
        Assert.Equal(0, again.Calls);
        Assert.Equal(0, s2.NewRecords + s2.Reused);
    }

    [Fact]
    public async Task Pilot_stop_between_source_and_reused_record_is_completed_on_restart_without_a_call()
    {
        using var f = new PilotFixture();
        await f.Run(f.Options(), new PilotCaller());
        foreach (var shard in Directory.GetFiles(f.OutDir, "batch_*0001_a.com.jsonl"))
        {
            var keep = File.ReadAllLines(shard).Where(l => !l.Contains("\"reused\":true")).ToList();
            File.WriteAllText(shard, string.Join("\n", keep) + "\n");
        }
        Assert.Equal(20, f.Records().Count);

        var caller = new PilotCaller();
        var s = await f.Run(f.Options(), caller);
        Assert.Equal(0, caller.Calls);
        Assert.Equal(4, s.Reused);
        Assert.Equal(24, f.Records().Count);
    }

    [Fact]
    public async Task Pilot_journal_line_for_a_reused_key_refuses()
    {
        using var f = new PilotFixture();
        await f.Run(f.Options(), new PilotCaller());
        var reusedKey = PilotFixture.Key(PilotFixture.ClassOnly, "F1", "0001_a.com", "t_01");
        File.AppendAllText(Path.Combine(f.OutDir, "journal.jsonl"), new JsonObject
        {
            ["type"] = "pending", ["key"] = reusedKey, ["plan_sha256"] = f.Options().ExpectedPlanSha256,
            ["ts"] = "2026-10-12T00:00:00Z", ["attempt"] = 1, ["deployment"] = "gpt-4.1",
            ["observation_sha256"] = Hashing.Sha256Hex(PilotFixture.ObsText("0001_a.com", PilotFixture.Nvc, "F1")),
            ["reservation"] = 100,
        }.ToJsonString() + "\n");
        var caller = new PilotCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => f.Run(f.Options(), caller));
        Assert.Contains("not in the plan", ex.Message);
        Assert.Equal(0, caller.Calls);
    }

    [Fact]
    public async Task Pilot_reused_record_with_a_wrong_marker_refuses_on_resume()
    {
        using var f = new PilotFixture();
        await f.Run(f.Options(), new PilotCaller());
        var shard = Directory.GetFiles(f.OutDir, "batch_*0001_a.com.jsonl").Single();
        File.WriteAllText(shard, File.ReadAllText(shard).Replace("\"reused\":true", "\"reused\":false"));
        var caller = new PilotCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => f.Run(f.Options(), caller));
        Assert.Equal(0, caller.Calls);
    }

    // Pinned files

    [Theory]
    [InlineData("plan.json")]
    [InlineData("reuse.json")]
    [InlineData("manifest.tsv")]
    [InlineData("targets.json")]
    [InlineData("sites.json")]
    [InlineData("shim.js")]
    [InlineData("html/0002_b.com.html")]
    public async Task Pilot_changed_pinned_file_refuses_before_any_call(string file)
    {
        using var f = new PilotFixture();
        var pinned = f.Options();
        File.AppendAllText(f.P(file), file.EndsWith(".json") ? " " : "\n");
        var caller = new PilotCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => f.Run(pinned, caller));
        Assert.Contains("sha256", ex.Message);
        Assert.Equal(0, caller.Calls);
        Assert.False(Directory.Exists(f.OutDir));
    }

    [Theory]
    [InlineData("sites")]
    [InlineData("targets")]
    public async Task Pilot_site_or_target_count_other_than_pinned_is_refused(string which)
    {
        using var f = new PilotFixture();
        var o = f.Options();
        o = which == "sites" ? o with { SiteCount = o.SiteCount + 1 } : o with { TargetCount = o.TargetCount - 1 };
        var caller = new PilotCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => f.Run(o, caller));
        Assert.Contains("pinned", ex.Message);
        Assert.Equal(0, caller.Calls);
        Assert.False(Directory.Exists(f.OutDir));
    }

    [Fact]
    public void Pilot_production_counts_equal_the_committed_plan()
    {
        var o = PilotPins.Production(Testbed.RepoRoot);
        var plan = JsonNode.Parse(File.ReadAllText(o.PlanPath))!;
        var events = plan["events"]!.AsArray().Select(e => e!).ToList();
        Assert.Equal(PilotPins.PlannedCalls, events.Count);
        Assert.Equal(PilotPins.PlannedInputTokens, events.Sum(e => (long)e["input_tokens"]!.GetValue<int>()));
        Assert.Equal(PilotPins.ReusedCount, JsonNode.Parse(File.ReadAllText(o.ReuseMapPath))!["count"]!.GetValue<int>());
        Assert.Equal(PilotPins.CapMicroUsd, (long)(plan["budget"]!["hard_cap_usd"]!.GetValue<decimal>() * 1_000_000m));
        foreach (var ((bundle, enc), n) in PilotPins.AllowedCells)
        {
            Assert.Equal(n, events.Count(e => e["bundle"]!.GetValue<string>() == bundle && e["encoding"]!.GetValue<string>() == enc));
        }
        var pages = events.Select(e => e["page"]!.GetValue<string>()).ToHashSet();
        Assert.Equal(PilotPins.SiteCount, pages.Count);
        Assert.Equal(PilotPins.SiteCount, JsonNode.Parse(File.ReadAllText(o.SitesPath))!["sites"]!.AsArray().Count);
        var targets = JsonNode.Parse(File.ReadAllText(o.TargetsPath))!["items"]!.AsArray();
        Assert.Equal(PilotPins.TargetCount,
                     targets.Count(t => pages.Contains($"{t!["rank"]!.GetValue<int>():D4}_{t["domain"]!.GetValue<string>()}")));
    }

    [Fact]
    public void Pilot_production_pins_equal_the_committed_files()
    {
        var o = PilotPins.Production(Testbed.RepoRoot);
        Assert.Equal(PilotPins.PlanSha256, Hashing.FileSha256(o.PlanPath));
        Assert.Equal(PilotPins.ReuseMapSha256, Hashing.FileSha256(o.ReuseMapPath));
        Assert.Equal(PilotPins.TargetsSha256, Hashing.FileSha256(o.TargetsPath));
        Assert.Equal(PilotPins.ObservationsManifestSha256, Hashing.FileSha256(o.ManifestPath));
        Assert.Equal(PilotPins.SitesSha256, Hashing.FileSha256(o.SitesPath));
        Assert.Equal(PilotPins.ShimSha256, Hashing.Sha256Hex(File.ReadAllText(o.ShimPath).Replace("\r\n", "\n")));
        Assert.Equal(BatchPins.PromptDigestSha256, o.ExpectedPromptDigest);
        Assert.NotEqual(Path.GetFullPath(BatchPins.Production(Testbed.RepoRoot).OutDir), Path.GetFullPath(o.OutDir));
    }

    [Fact]
    public void Pilot_completion_reserve_is_the_limit_the_request_sends()
    {
        var maxTokens = typeof(LlmClient).GetField("MaxTokens", BindingFlags.NonPublic | BindingFlags.Static)!;
        Assert.Equal(PilotPins.MaxCompletionTokens, (int)maxTokens.GetRawConstantValue()!);
        Assert.False(LlmClient.IsReasoningModel("gpt-4.1"));
        Assert.Equal(64, BatchBudget.FramingReserveTokens);
    }

    // Preflight (a) fields, (b) pages/tasks, (c) event_key

    [Theory]
    [InlineData("extra")]
    [InlineData("missing")]
    [InlineData("rank_as_string")]
    [InlineData("input_tokens_as_string")]
    public void Pilot_a_event_fields_are_exactly_the_19_typed(string variant)
    {
        using var f = new PilotFixture();
        var e = f.Events[3]!.AsObject();
        switch (variant)
        {
            case "extra": e["note"] = "x"; break;
            case "missing": e.Remove("stratum"); break;
            case "rank_as_string": e["rank"] = "2"; break;
            case "input_tokens_as_string": e["input_tokens"] = "5"; break;
        }
        f.WriteAll();
        Refused(f.Options(), variant.StartsWith("extra") || variant == "missing" ? "fields" : "is not an integer");
    }

    [Fact]
    public void Batch_profile_still_refuses_a_plan_with_the_pilot_fields()
    {
        using var f = new BatchFixture();
        foreach (var e in f.Events)
        {
            e["event_key"] = "gpt-4.1|B_full|F1|page_01|t_01|0";
            e["observation_sha256"] = new string('a', 64);
        }
        f.WritePlan();
        var ex = Assert.Throws<BatchRefusedException>(() => BatchPreflight.Run(f.Options()));
        Assert.Contains("fields", ex.Message);
    }

    [Fact]
    public void Pilot_c_event_key_must_follow_the_PlanEvent_formula()
    {
        using var f = new PilotFixture();
        f.Events[0]!["event_key"] = "gpt-4.1|B_full|F1|0001_a.com|t_01|1";
        f.WriteAll();
        Refused(f.Options(), "event_key");
    }

    [Theory]
    [InlineData("task_not_in_targets", "not in targets.json")]
    [InlineData("page_not_a_site", "pilot_sites.json")]
    [InlineData("observation_not_manifest", "observations_manifest.tsv")]
    [InlineData("xpath_differs", "differ from targets.json")]
    [InlineData("excluded_site", "pilot_sites.json")]
    public void Pilot_b_pages_and_tasks_are_checked_against_targets_and_manifest(string variant, string fragment)
    {
        using var f = new PilotFixture();
        var e = f.Events[0]!.AsObject();
        void Rekey() => e["event_key"] = PilotFixture.Key(e["bundle"]!.GetValue<string>(), e["encoding"]!.GetValue<string>(),
                                                           e["page"]!.GetValue<string>(), e["task_id"]!.GetValue<string>());
        switch (variant)
        {
            case "task_not_in_targets": e["task_id"] = "t_09"; Rekey(); break;
            case "page_not_a_site": e["page"] = "page_01"; Rekey(); break;
            case "observation_not_manifest": e["observation_sha256"] = new string('b', 64); break;
            case "xpath_differs": e["xpath"] = "/html[1]"; break;
            case "excluded_site": e["page"] = "0003_x.com"; e["domain"] = "x.com"; e["rank"] = 3; Rekey(); break;
        }
        f.WriteAll();
        Refused(f.Options(), fragment);
    }

    [Theory]
    [InlineData("source_not_nvc", "is not a called")]
    [InlineData("reused_key_is_called", "neither")]
    [InlineData("unequal_observations", "byte-identical")]
    public void Pilot_reuse_map_entries_are_checked(string variant, string fragment)
    {
        using var f = new PilotFixture();
        var r = f.Reuse["reuse"]![0]!.AsObject();
        switch (variant)
        {
            case "source_not_nvc":
                r["reused_event_key"] = r["reused_event_key"]!.GetValue<string>().Replace(PilotFixture.Nvc, "B_full");
                break;
            case "reused_key_is_called":
                // Drop the entry: its class_only cell is then neither called nor reused.
                f.Reuse["reuse"]!.AsArray().RemoveAt(0);
                f.Reuse["count"] = 3;
                f.Plan["class_only_not_called"] = 3;
                break;
            case "unequal_observations":
                r["class_only_observation_sha256"] = new string('c', 64);
                break;
        }
        f.WriteAll();
        f.Reuse["plan_sha256"] = Hashing.FileSha256(f.P("plan.json"));
        f.Write("reuse.json", f.Reuse);
        Refused(f.Options(), fragment);
    }

    [Theory]
    [InlineData("BAR_BATCH_MAX_INPUT_TOKENS")]
    [InlineData("BAR_BATCH_BLOCKS")]
    public void Pilot_refuses_the_batch_budget_and_block_knobs(string name)
    {
        using var f = new PilotFixture();
        f.Env[name] = "1";
        Refused(f.Options(), name);
    }

    [Fact]
    public void Pilot_refuses_a_deployment_slot_that_is_not_the_plan_model()
    {
        using var f = new PilotFixture();
        f.Env["BAR_MODEL_DEPLOYMENT_1"] = "gpt-4.1-nano";
        Refused(f.Options(), "BAR_MODEL_DEPLOYMENT_1");
    }

    // Budget (µUSD) and persistent stops

    private static long FirstBound(PilotFixture f)
    {
        var e = f.Events[0]!;
        var tokens = e["input_tokens"]!.GetValue<int>();
        return 2 * (tokens + BatchBudget.FramingReserveTokens) + 8 * 256;
    }

    [Fact]
    public async Task Pilot_budget_exactly_at_the_cap_calls_then_the_next_event_stops()
    {
        using var f = new PilotFixture();
        f.Cap = FirstBound(f);
        var caller = new PilotCaller();
        var ex = await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), caller));
        Assert.Equal(1, caller.Calls);
        Assert.Contains("pilot cost cap", ex.Message);
        Assert.Single(f.Records());
    }

    [Fact]
    public async Task Pilot_budget_one_microdollar_short_stops_before_any_call_and_again_after_restart()
    {
        using var f = new PilotFixture();
        f.Cap = FirstBound(f) - 1;
        for (int run = 0; run < 2; run++)
        {
            var caller = new PilotCaller();
            var ex = await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), caller));
            Assert.Equal(0, caller.Calls);
            Assert.Contains("no call made", ex.Message);
        }
        Assert.DoesNotContain(f.Journal(), j => j["type"]!.GetValue<string>() == "pending");
    }

    [Theory]
    [InlineData("prompt")]
    [InlineData("completion")]
    public async Task Pilot_overrun_is_persistent_until_released(string which)
    {
        using var f = new PilotFixture();
        var over = which == "prompt" ? new PilotCaller { Framing = 65 } : new PilotCaller { CompletionTokens = 257 };
        var ex = await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), over));
        Assert.Equal(1, over.Calls);
        Assert.Contains("budget model no longer bounds", ex.Message);

        for (int run = 0; run < 2; run++)
        {
            var again = new PilotCaller();
            var stop = await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), again));
            Assert.Equal(0, again.Calls);
            Assert.Contains("overrun", stop.Message);
        }

        var key = f.Events[0]!["event_key"]!.GetValue<string>();
        f.Env["BAR_BATCH_RELEASE_OVERRUN"] = key;
        var rel = new PilotCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), rel));
        Assert.Equal(0, rel.Calls);
        f.Env.Remove("BAR_BATCH_RELEASE_OVERRUN");

        // The overrun's usage is known and already counted with its response: the release restates it, and adds
        // no liability on top (no double count).
        var released = f.Journal()[^1];
        Assert.Equal("overrun_released", released["type"]!.GetValue<string>());
        var response = f.Journal().Single(j => j["type"]!.GetValue<string>() == "response");
        Assert.Equal(response["prompt_tokens"]!.GetValue<long>(), released["prompt_tokens"]!.GetValue<long>());
        Assert.Equal(response["completion_tokens"]!.GetValue<long>(), released["completion_tokens"]!.GetValue<long>());
        Assert.Equal(f.Journal().Single(j => j["type"]!.GetValue<string>() == "pending")["reservation"]!.GetValue<long>(),
                     released["reservation"]!.GetValue<long>());
        var (p, j) = Ledger(f);
        Assert.Empty(j.ReleasedReservations);
        Assert.Equal(p.Budget.Spent(j), p.Budget.Liability(j));

        var rest = new PilotCaller();
        await f.Run(f.Options(), rest);
        Assert.Equal(19, rest.Calls);
        Assert.Equal(24, f.Records().Count);
    }

    private static (PilotPlan P, BatchJournal J) Ledger(PilotFixture f)
    {
        var p = PilotPreflight.Run(f.Options());
        return (p, BatchJournal.Load(f.OutDir, p.Expectations));
    }

    /// <summary>
    /// Release liability (real_pilot/pilot_addendum_scoring.md (б)): pending → error → released keeps the attempt's
    /// reservation bound as spent; the retry reserves on its own; the cap holds liability + reservation.
    /// slack 0: liability + the retry's bound == cap → the retry is called; slack −1: stopped before it, no call.
    /// </summary>
    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    public async Task Pilot_released_unknown_request_stays_a_budget_liability_and_the_retry_reserves_again(int slack)
    {
        using var f = new PilotFixture();
        var bound = FirstBound(f);
        f.Cap = 2 * bound + slack;
        var key = f.Events[0]!["event_key"]!.GetValue<string>();

        var c1 = new PilotCaller("timeout");
        await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), c1));
        Assert.Equal(1, c1.Calls);
        var reservation = f.Journal().Single(x => x["type"]!.GetValue<string>() == "pending")["reservation"]!.GetValue<long>();

        f.Env["BAR_BATCH_RELEASE"] = key;
        var rel = new PilotCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), rel));
        Assert.Equal(0, rel.Calls);
        f.Env.Remove("BAR_BATCH_RELEASE");
        var released = f.Journal()[^1];
        Assert.Equal("released", released["type"]!.GetValue<string>());
        Assert.Equal(reservation, released["reservation"]!.GetValue<long>());

        var (p, j) = Ledger(f);
        Assert.Equal(new[] { reservation }, j.ReleasedReservations);
        Assert.Equal(0, p.Budget.Spent(j));
        Assert.Equal(bound, p.Budget.Bound(reservation));
        Assert.Equal(bound, p.Budget.Liability(j));

        var c2 = new PilotCaller();
        var stop = await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), c2));
        Assert.Contains("pilot cost cap", stop.Message);
        Assert.Contains("released liability", stop.Message);
        var pendings = f.Journal().Where(x => x["type"]!.GetValue<string>() == "pending" && x["key"]!.GetValue<string>() == key).ToList();
        if (slack < 0)
        {
            Assert.Equal(0, c2.Calls);
            Assert.Contains($"stopped before {key}", stop.Message);
            Assert.Single(pendings);
            Assert.Empty(f.Records());
        }
        else
        {
            // The retry: attempt 2, its own pending and reservation; the next event no longer fits.
            Assert.Equal(1, c2.Calls);
            Assert.Equal(new[] { 1, 2 }, pendings.Select(x => x["attempt"]!.GetValue<int>()));
            Assert.All(pendings, x => Assert.Equal(reservation, x["reservation"]!.GetValue<long>()));
            Assert.Single(f.Records());
            var (p2, j2) = Ledger(f);
            Assert.True(p2.Budget.Spent(j2) > 0);
            Assert.Equal(p2.Budget.Spent(j2) + bound, p2.Budget.Liability(j2));
        }
    }

    [Theory]
    [InlineData("timeout")]
    [InlineData("503")]
    public async Task Pilot_possibly_billed_error_stops_and_restart_refuses_without_a_call(string outcome)
    {
        using var f = new PilotFixture();
        var caller = new PilotCaller(outcome);
        await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), caller));
        Assert.Equal(1, caller.Calls);
        for (int run = 0; run < 2; run++)
        {
            var again = new PilotCaller();
            var ex = await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), again));
            Assert.Equal(0, again.Calls);
            Assert.Contains("unknown outcome", ex.Message);
        }
    }

    // Resume, observation and input-token gates

    [Fact]
    public async Task Pilot_resume_with_an_invalid_journal_line_refuses()
    {
        using var f = new PilotFixture();
        await Assert.ThrowsAsync<BatchStoppedException>(() => f.Run(f.Options(), new PilotCaller("503")));
        File.AppendAllText(Path.Combine(f.OutDir, "journal.jsonl"), "{\"type\":\"response\"}\n");
        var caller = new PilotCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => f.Run(f.Options(), caller));
        Assert.Equal(0, caller.Calls);
    }

    [Fact]
    public async Task Pilot_resume_with_an_inconsistent_record_refuses()
    {
        using var f = new PilotFixture();
        await f.Run(f.Options(), new PilotCaller());
        var shard = Directory.GetFiles(f.OutDir, "batch_*0002_b.com.jsonl").Single();
        File.WriteAllText(shard, File.ReadAllText(shard).Replace("\"page\":\"0002_b.com\"", "\"page\":\"pages/page_02.html\""));
        var caller = new PilotCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => f.Run(f.Options(), caller));
        Assert.Equal(0, caller.Calls);
    }

    [Fact]
    public async Task Pilot_observation_mismatch_stops_without_a_call_or_pending()
    {
        using var f = new PilotFixture();
        var caller = new PilotCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() =>
            f.Run(f.Options(), caller, p => new PilotFakeExecutor(p, e => "OBS changed " + e.Key)));
        Assert.Contains("observation sha256", ex.Message);
        Assert.Equal(0, caller.Calls);
        Assert.Empty(f.Journal());
    }

    [Fact]
    public async Task Pilot_input_tokens_other_than_planned_refuse_without_a_call()
    {
        using var f = new PilotFixture();
        var caller = new PilotCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() =>
            f.Run(f.Options(), caller, p => new PilotFakeExecutor(p, task: e => "a different task text, longer")));
        Assert.Contains("input tokens", ex.Message);
        Assert.Equal(0, caller.Calls);
        Assert.Empty(f.Journal());
    }

    // verify-observations: the run path, one fresh observation per cell

    private static Func<PlanEvent, Task<(string, IReadOnlyDictionary<string, bool>?)>> Observer(
        PilotPlan p, Dictionary<(string, string, string), int> calls, (string Page, string Bundle, string Enc)? changed = null) =>
        e =>
        {
            var cell = (e.Page, e.Bundle, e.Encoding);
            calls[cell] = calls.GetValueOrDefault(cell) + 1;
            var text = PilotFixture.ObsText(e.Page, e.Bundle, e.Encoding) + (cell == changed ? " (timer fired)" : "");
            IReadOnlyDictionary<string, bool>? c5 = e.Bundle == "B_full"
                ? p.TargetsBySite[e.Page].ToDictionary(t => t.Marker, _ => true)
                : null;
            return Task.FromResult((text, c5));
        };

    [Fact]
    public async Task Pilot_verify_observes_every_used_cell_once_through_the_given_run_path()
    {
        using var f = new PilotFixture();
        var p = PilotPreflight.Run(f.Options());
        var calls = new Dictionary<(string, string, string), int>();
        var r = await PilotVerify.RunAsync(p, Observer(p, calls), _ => { });

        Assert.True(r.Pass);
        Assert.Equal(12, r.Cells);              // 2 sites × 6 cells (called + reused)
        Assert.Equal(12, r.Observations);       // one fresh observation per cell, none shared
        Assert.Equal(12, calls.Count);
        Assert.All(calls.Values, n => Assert.Equal(1, n));
        Assert.Equal(20, r.Tokens);
        Assert.Equal(4, r.Cond5);
    }

    [Fact]
    public async Task Pilot_verify_result_is_identical_over_five_repetitions_and_names_the_changed_cell()
    {
        using var f = new PilotFixture();
        var p = PilotPreflight.Run(f.Options());
        var changed = ("0002_b.com", PilotFixture.Nvc, "F1");
        var reports = new List<PilotVerifyReport>();
        for (int i = 0; i < 5; i++)
        {
            reports.Add(await PilotVerify.RunAsync(p, Observer(p, new(), changed), _ => { }));
        }

        var first = reports[0];
        Assert.False(first.Pass);
        Assert.Equal(11, first.CellsOk);
        Assert.Equal(18, first.TokensOk);       // the 2 called events of that cell
        Assert.Single(first.Mismatches);
        Assert.StartsWith("0002_b.com B_noVolatileConsistent×F1 ", first.Mismatches[0]);
        Assert.All(reports, r =>
        {
            Assert.Equal((first.Cells, first.CellsOk, first.Tokens, first.TokensOk, first.Cond5, first.Cond5Ok),
                         (r.Cells, r.CellsOk, r.Tokens, r.TokensOk, r.Cond5, r.Cond5Ok));
            Assert.Equal(first.Mismatches, r.Mismatches);
        });
    }

    // Flags

    private static string? None(string _) => null;

    [Fact]
    public void Plan_flag_selects_the_pilot_only_in_its_exact_form()
    {
        Assert.NotEmpty(BatchEntry.CheckFlags(None, new[] { "--plan", "pilot" }));   // no mode given: refused
        Assert.Empty(BatchEntry.CheckFlags(None, new[] { "--plan", "pilot", "--preflight-only" }));
        Assert.Empty(BatchEntry.CheckFlags(None, new[] { "--verify-observations", "--plan", "pilot" }));
        Assert.True(BatchEntry.IsPilot(new[] { "--preflight-only", "--plan", "pilot" }));

        foreach (var bad in new[]
                 {
                     new[] { "--plan" }, new[] { "--plan", "batch" }, new[] { "pilot" }, new[] { "--plan", "pilot", "--plan", "pilot" },
                     new[] { "pilot", "--plan" }, new[] { "--plan", "pilot", "pilot" }, new[] { "--plan", "PILOT" },
                     new[] { "--plan", "pilot", "--preflight-only", "--verify-observations" }, new[] { "--plan=pilot" },
                 })
        {
            Assert.NotEmpty(BatchEntry.CheckFlags(None, bad));
        }
        Assert.False(BatchEntry.IsPilot(Array.Empty<string>()));
        Assert.False(BatchEntry.IsPilot(new[] { "--preflight-only" }));
    }

    [Fact]
    public void Without_plan_flag_CheckFlags_answers_as_before()
    {
        Assert.NotEmpty(BatchEntry.CheckFlags(None, Array.Empty<string>()));   // no mode given: refused
        Assert.Empty(BatchEntry.CheckFlags(None, new[] { "--preflight-only" }));
        Assert.Empty(BatchEntry.CheckFlags(None, new[] { "--verify-observations" }));
        Assert.Single(BatchEntry.CheckFlags(None, new[] { "--replay" }));
        Assert.Single(BatchEntry.CheckFlags(None, new[] { "--preflight-only", "--verify-observations" }));
        Assert.Single(BatchEntry.CheckFlags(k => k == "AXIS_C" ? "1" : null, new[] { "--preflight-only" }));
        // The pilot is still refused alongside the conflicting env flags.
        Assert.NotEmpty(BatchEntry.CheckFlags(k => k == "BAR_BATCH_PLAN" ? "pilot" : null, new[] { "--plan", "pilot" }));
    }
}
