using System.Diagnostics;
using System.Text.Json.Nodes;
using BoundedAgents.Experiments.Batch;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// Batch runner guards: the input-token cap is checked before the call, resume is strict and semantic,
/// and the legacy entrypoint refuses a batch flag set only in .env. Fake LLM client only, zero real
/// model calls.
/// </summary>
public class BatchBudgetAndResumeTests
{
    private const string Key1 = "gpt-4.1|B_full|F1|page_01|t_01|0";

    /// <summary>Framing reserve the runner adds to the counted prompt (BatchBudget.FramingReserveTokens).</summary>
    private const int Reserve = 64;

    /// <summary>tokens(SystemPrompt) + tokens(user prompt) for the fixture's t_01 event.</summary>
    private static int CountedPrompt()
    {
        var obs = "OBS page_01 B_full F1";
        return TokenCounter.CountTokens(GroundingRunner.SystemPrompt)
               + TokenCounter.CountTokens(GroundingRunner.BuildUserPrompt(obs, "task t_01"));
    }

    private static void RewriteJsonl(string path, Func<List<JsonObject>, IEnumerable<JsonObject>> edit)
    {
        var rows = File.ReadAllLines(path).Select(l => JsonNode.Parse(l)!.AsObject()).ToList();
        File.WriteAllText(path, string.Concat(edit(rows).Select(r => r.ToJsonString() + "\n")));
    }

    private static async Task AssertRefusedWithoutCall(BatchFixture fx, FakeExecutor? ex = null)
    {
        var c = new FakeCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c, ex));
        Assert.Equal(0, c.Calls);
    }

    // Input-token cap checked before the call, in the ledger's unit

    [Fact]
    public async Task B1_scenario_cap_equal_to_string_estimate_with_higher_usage_makes_no_call()
    {
        using var fx = new BatchFixture(tasks: 1);
        var est = CountedPrompt();
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = est.ToString();
        var c = new FakeCaller { PromptTokens = est + 7 };      // native usage above the string count
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c));
        Assert.Equal(0, c.Calls);
        Assert.Empty(fx.Journal());
    }

    [Fact]
    public async Task B1_boundary_spent_plus_reservation_equal_to_cap_calls()
    {
        using var fx = new BatchFixture(tasks: 1);
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = (CountedPrompt() + Reserve).ToString();
        var c = new FakeCaller { PromptTokens = CountedPrompt() + 11 };
        var s = await fx.Run(c);
        Assert.Equal((1, 1), (c.Calls, s.NewRecords));
    }

    [Fact]
    public async Task B1_boundary_one_token_over_cap_stops_without_call_or_pending()
    {
        using var fx = new BatchFixture(tasks: 1);
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = (CountedPrompt() + Reserve - 1).ToString();
        var c = new FakeCaller { PromptTokens = CountedPrompt() + 11 };
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c));
        Assert.Equal(0, c.Calls);
        Assert.Empty(fx.Journal());
    }

    [Fact]
    public async Task B1_usage_above_reservation_keeps_the_paid_record_and_stops()
    {
        using var fx = new BatchFixture(tasks: 2);
        var c = new FakeCaller { PromptTokens = CountedPrompt() + Reserve + 1 };
        var ex = await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c));
        Assert.Contains("reservation", ex.Message);
        Assert.Equal(1, c.Calls);
        Assert.Single(fx.Records());
    }

    [Theory]
    [InlineData("0")]
    [InlineData("-1")]
    [InlineData("1.5")]
    public void B1_cap_must_be_a_positive_integer(string cap)
    {
        using var fx = new BatchFixture(tasks: 1);
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = cap;
        Assert.Throws<BatchRefusedException>(() => BatchPreflight.Run(fx.Options()));
    }

    // Strict resume: incomplete journal, invalid record, foreign response, unreleased error

    [Fact]
    public async Task B2_case1_incomplete_journal_response_with_complete_shard_refuses()
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());
        RewriteJsonl(fx.JournalPath, rows => rows.Select(r =>
        {
            if (r["type"]!.GetValue<string>() == "response")
            {
                r.Remove("locator_raw");
                r.Remove("finish_reason");
                r.Remove("response_model");
            }
            return r;
        }));
        await AssertRefusedWithoutCall(fx);
    }

    [Theory]
    [InlineData("success_as_string")]
    [InlineData("negative_completion_tokens")]
    [InlineData("zero_observation_sha")]
    public async Task B2_case2_invalid_record_types_or_values_refuse(string defect)
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());
        RewriteJsonl(fx.ShardPath, rows => rows.Select(r =>
        {
            switch (defect)
            {
                case "success_as_string": r["success"] = "true"; break;
                case "negative_completion_tokens": r["completion_tokens"] = -7; break;
                case "zero_observation_sha": r["observation_sha256"] = new string('0', 64); break;
            }
            return r;
        }));
        await AssertRefusedWithoutCall(fx);
    }

    [Theory]
    [InlineData("deployment")]
    [InlineData("observation_sha256")]
    public async Task B2_case3_foreign_journal_response_is_not_replayed(string field)
    {
        using var fx = new BatchFixture(tasks: 1);
        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            fx.Run(new FakeCaller(), new FakeExecutor { ThrowAfterResponse = true }));
        Assert.Empty(fx.Records());
        RewriteJsonl(fx.JournalPath, rows => rows.Select(r =>
        {
            if (r["type"]!.GetValue<string>() == "response")
            {
                r[field] = field == "deployment" ? "gpt-4.1-nano" : new string('f', 64);
            }
            return r;
        }));
        await AssertRefusedWithoutCall(fx);
        Assert.Empty(fx.Records());
    }

    [Fact]
    public async Task B2_case4_error_followed_by_rejected_429_without_release_refuses()
    {
        using var fx = new BatchFixture(tasks: 1);
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(new FakeCaller("fail")));
        File.AppendAllText(fx.JournalPath, new JsonObject
        {
            ["type"] = "rejected_429", ["key"] = Key1, ["plan_sha256"] = Hashing.FileSha256(fx.PlanPath),
            ["ts"] = DateTimeOffset.UtcNow.ToString("O"), ["attempt"] = 1, ["retry_after_ms"] = 1,
        }.ToJsonString() + "\n");
        await AssertRefusedWithoutCall(fx);
    }

    // Strict resume: every other kind of record mismatch

    [Theory]
    // identity vs the plan
    [InlineData("event_key", "gpt-4.1|B_full|F1|page_01|t_02|0")]
    [InlineData("model", "gpt-4.1-nano")]
    [InlineData("bundle", "B_noVolatile")]
    [InlineData("encoding", "F2")]
    [InlineData("page", "pages/page_02.html")]
    [InlineData("task_id", "t_02")]
    [InlineData("rep", 2)]
    [InlineData("repetition", 1)]
    [InlineData("plan_sha256", "0000000000000000000000000000000000000000000000000000000000000000")]
    [InlineData("observation_sha256", "1111111111111111111111111111111111111111111111111111111111111111")]
    [InlineData("observation_tokens", 4)]
    [InlineData("tokenizer_version", "cl100k_base")]
    [InlineData("seed", 7)]
    // record vs its journaled response
    [InlineData("locator_raw", "css:#other")]
    [InlineData("prompt_tokens_total", 999)]
    [InlineData("completion_tokens", 8)]
    [InlineData("response_model_id", "gpt-4.1-2099-01-01")]
    [InlineData("finish_reason", "Length")]
    [InlineData("system_fingerprint", "fp_other")]
    [InlineData("llm_attempts", 2)]
    // score vs the score recomputed from the journaled locator
    [InlineData("locator_value", "#other")]
    [InlineData("success", false)]
    [InlineData("failure_mode", "model_grabbed_brittle_signal")]
    [InlineData("predicate_unique_match", false)]
    [InlineData("stable_signal_present_in_bundle", false)]
    public async Task B2_record_mismatch_refuses_the_whole_run(string field, object value)
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());
        RewriteJsonl(fx.ShardPath, rows => rows.Select(r =>
        {
            r[field] = JsonValue.Create(value);
            return r;
        }));
        await AssertRefusedWithoutCall(fx);
    }

    [Theory]
    [InlineData("response_without_pending")]
    [InlineData("response_attempt_mismatch")]
    [InlineData("pending_after_response")]
    [InlineData("first_pending_not_attempt_1")]
    public async Task B2_invalid_journal_transition_refuses(string defect)
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());
        RewriteJsonl(fx.JournalPath, rows =>
        {
            var pending = rows.First(r => r["type"]!.GetValue<string>() == "pending");
            var response = rows.First(r => r["type"]!.GetValue<string>() == "response");
            switch (defect)
            {
                case "response_without_pending": return new[] { response };
                case "response_attempt_mismatch": response["attempt"] = 2; return rows;
                case "pending_after_response": return rows.Append((JsonObject)pending.DeepClone());
                default: pending["attempt"] = 2; response["attempt"] = 2; return rows;
            }
        });
        await AssertRefusedWithoutCall(fx);
    }

    // Strict resume with the real executor: the score is recomputed from the DOM

    [Fact]
    [Trait("Category", "Integration")]
    public async Task B2_real_executor_flipped_success_is_caught_by_rescoring()
    {
        using var fx = new BatchFixture(tasks: 0);
        fx.Events.Add(BatchFixture.Ev("1", "gpt-4.1", "B_full", "F1", "page_01", "t_01", 0));
        fx.WritePlan();
        var audited = File.ReadAllLines(
            Path.Combine(Testbed.RepoRoot, "experiments", "results", "revision1", "observations", "manifest.tsv"));
        File.WriteAllText(fx.ManifestPath,
            audited[0] + "\n" + audited.Single(l => l.StartsWith("page_01\tB_full\tF1\t")) + "\n");
        var o = fx.Options();
        var l = new System.Net.Sockets.TcpListener(System.Net.IPAddress.Loopback, 0);
        l.Start();
        var baseUrl = $"http://127.0.0.1:{((System.Net.IPEndPoint)l.LocalEndpoint).Port}";
        l.Stop();

        var c1 = new FakeCaller();                               // "css:#fake" matches nothing → failure
        await RevisionBatchRunner.RunAsync(o, () => new PlaywrightBatchExecutor(Testbed.RepoRoot, baseUrl), c1,
                                           log: _ => { });
        Assert.Equal(1, c1.Calls);
        RewriteJsonl(fx.ShardPath, rows => rows.Select(r =>
        {
            Assert.False(r["success"]!.GetValue<bool>());
            // Internally consistent forgery: success + all five predicates true, no failure mode.
            r["success"] = true;
            r["failure_mode"] = null;
            foreach (var f in new[] { "predicate_unique_match", "predicate_matches_oracle", "predicate_non_volatile",
                                      "predicate_non_positional", "stable_signal_present_in_bundle" })
            {
                r[f] = true;
            }
            return r;
        }));

        var c2 = new FakeCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() =>
            RevisionBatchRunner.RunAsync(o, () => new PlaywrightBatchExecutor(Testbed.RepoRoot, baseUrl), c2,
                                         log: _ => { }));
        Assert.Contains("recomputed", ex.Message);
        Assert.Equal(0, c2.Calls);
    }

    [Fact]
    public async Task B2_consistent_record_and_journal_with_a_wrong_score_are_caught_by_rescoring()
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());
        // Same forged locator in the journal response and the record; record still claims success.
        RewriteJsonl(fx.JournalPath, rows => rows.Select(r =>
        {
            if (r["type"]!.GetValue<string>() == "response")
            {
                r["locator_raw"] = "css:#other";
            }
            return r;
        }));
        RewriteJsonl(fx.ShardPath, rows => rows.Select(r =>
        {
            r["locator_raw"] = "css:#other";
            r["locator_value"] = "#other";
            return r;
        }));
        var c = new FakeCaller();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
        Assert.Contains("recomputed", ex.Message);
        Assert.Equal(0, c.Calls);
    }

    // The legacy entrypoint must see REVISION_BATCH set only in .env

    private static readonly string[] ScrubPrefixes = { "BAR_", "AZURE", "OPENAI", "ANTHROPIC" };

    private static readonly string[] ModeFlags =
    {
        "SMOKE_TEST", "LLM_SMOKE_TEST", "PREDICATE_CONTROLS", "VALIDATE_ENCODING", "AXIS_C", "DUMP_OBSERVATIONS",
        "SENSITIVITY_CONSISTENT", "DUMP_BATCH_OBSERVATIONS", "REVISION_BATCH", "REAL_PILOT",
    };

    // The guard has no grammar of its own: every line that mentions the flag refuses, defined or not
    // (fail-closed).
    [Theory]
    [InlineData("REVISION_BATCH=1")]
    [InlineData("export REVISION_BATCH=1")]
    [InlineData("REVISION_BATCH = \"1\"")]
    [InlineData("REVISION_BATCH=1   # run it")]
    [InlineData("REVISION_BATCH=")]
    [InlineData("REVISION_BATCH=\"\"")]
    [InlineData("REVISION_BATCH=# nothing")]
    [InlineData("# REVISION_BATCH=1")]
    [InlineData("REVISION_BATCH_X=1")]
    public void M1_dotenv_line_mentioning_the_flag_refuses(string line)
    {
        var dir = Path.Combine(Path.GetTempPath(), "guard1_" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(dir);
        try
        {
            File.WriteAllText(Path.Combine(dir, ".env"), "A=b" + (char)10 + line + (char)10);
            Assert.NotEmpty(BoundedAgents.Experiments.LegacyBatchGuard.DotEnvProblems(dir));
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    [Fact]
    public void M1_guard_reads_the_nearest_dotenv_up_the_tree()
    {
        var root = Path.Combine(Path.GetTempPath(), "guard_" + Guid.NewGuid().ToString("N")[..8]);
        var deep = Path.Combine(root, "a", "b");
        Directory.CreateDirectory(deep);
        try
        {
            string? None(string _) => null;
            Assert.Null(BoundedAgents.Experiments.LegacyBatchGuard.RefuseReason(None, Array.Empty<string>(), deep));
            File.WriteAllText(Path.Combine(root, ".env"), "BAR_X=1\nREVISION_BATCH=1\n");
            Assert.NotNull(BoundedAgents.Experiments.LegacyBatchGuard.RefuseReason(None, Array.Empty<string>(), deep));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    [Fact]
    public void B1_test_reserve_matches_the_runner_constant() =>
        Assert.Equal(Reserve, BatchBudget.FramingReserveTokens);

    [Fact]
    public async Task M1_legacy_entrypoint_refuses_when_REVISION_BATCH_is_only_in_dotenv()
    {
        var bin = Path.Combine(Testbed.RepoRoot, "experiments", "bin", "Debug", "net10.0");
        Assert.True(File.Exists(Path.Combine(bin, "Experiments.dll")), "build Experiments first");
        var shadow = Path.Combine(Path.GetTempPath(), "shadow_" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(shadow);
        try
        {
            foreach (var f in Directory.GetFiles(bin))
            {
                File.Copy(f, Path.Combine(shadow, Path.GetFileName(f)));
            }
            // Fictitious .env next to the binary: only the batch flag. No deployment, endpoint or key.
            File.WriteAllText(Path.Combine(shadow, ".env"), "REVISION_BATCH=1\n");

            var psi = new ProcessStartInfo("dotnet", $"\"{Path.Combine(shadow, "Experiments.dll")}\"")
            {
                WorkingDirectory = shadow,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
            };
            foreach (var k in psi.Environment.Keys.ToList())
            {
                if (ScrubPrefixes.Any(p => k.StartsWith(p, StringComparison.OrdinalIgnoreCase)) || ModeFlags.Contains(k))
                {
                    psi.Environment.Remove(k);
                }
            }
            using var p = Process.Start(psi)!;
            var stdout = p.StandardOutput.ReadToEndAsync();
            var stderr = p.StandardError.ReadToEndAsync();
            await p.WaitForExitAsync().WaitAsync(TimeSpan.FromMinutes(2));
            var err = await stderr;
            await stdout;
            Assert.True(p.ExitCode == 2, $"exit {p.ExitCode}; stderr: {err}");
            Assert.Contains("REVISION_BATCH", err);
        }
        finally
        {
            try { Directory.Delete(shadow, recursive: true); } catch { }
        }
    }
}
