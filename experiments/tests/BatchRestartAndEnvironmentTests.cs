using System.Diagnostics;
using System.Text;
using System.Text.Json.Nodes;
using BoundedAgents.Experiments.Batch;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// Batch stops must survive a restart, and the legacy guard must read .env with the same parser as
/// Config (DotNetEnv). Fake LLM client only, zero real model calls.
/// </summary>
public class BatchRestartAndEnvironmentTests
{
    private const string Key1 = "gpt-4.1|B_full|F1|page_01|t_01|0";

    private static int Strings() =>
        TokenCounter.CountTokens(GroundingRunner.SystemPrompt)
        + TokenCounter.CountTokens(GroundingRunner.BuildUserPrompt("OBS page_01 B_full F1", "task t_01"));

    private static int Reservation() => Strings() + 64;

    private static List<string> JournalTypes(BatchFixture fx) =>
        fx.Journal().Select(j => j["type"]!.GetValue<string>()).ToList();

    // Usage over the reservation stops every later run until released

    [Fact]
    public async Task N1_overrun_stop_survives_restart_with_free_cap()
    {
        using var fx = new BatchFixture(tasks: 2);
        var c1 = new FakeCaller { PromptTokens = Reservation() + 1 };
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c1));
        Assert.Equal(1, c1.Calls);
        Assert.Single(fx.Records());

        var c2 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c2));
        Assert.Equal(0, c2.Calls);
        Assert.Single(fx.Records());
    }

    [Fact]
    public async Task N1_overrun_stop_survives_a_crash_between_response_and_record()
    {
        using var fx = new BatchFixture(tasks: 2);
        var c1 = new FakeCaller { PromptTokens = Reservation() + 1 };
        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            fx.Run(c1, new FakeExecutor { ThrowAfterResponse = true }));
        Assert.Equal(1, c1.Calls);
        Assert.Empty(fx.Records());

        var c2 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c2));
        Assert.Equal(0, c2.Calls);
        Assert.Empty(fx.Records());                             // no silent replay into a "successful" run
    }

    [Fact]
    public async Task N1_overrun_with_spent_over_cap_does_not_resume_as_success()
    {
        using var fx = new BatchFixture(tasks: 1);
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = Reservation().ToString();
        await Assert.ThrowsAsync<BatchStoppedException>(() =>
            fx.Run(new FakeCaller { PromptTokens = Reservation() + 1 }));

        var c2 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c2));
        Assert.Equal(0, c2.Calls);
    }

    [Fact]
    public async Task N1_explicit_release_then_the_run_continues()
    {
        using var fx = new BatchFixture(tasks: 2);
        await Assert.ThrowsAsync<BatchStoppedException>(() =>
            fx.Run(new FakeCaller { PromptTokens = Reservation() + 1 }));

        fx.Env["BAR_BATCH_RELEASE_OVERRUN"] = Key1;
        var c2 = new FakeCaller();
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c2));
        Assert.Equal(0, c2.Calls);
        Assert.Equal("overrun_released", JournalTypes(fx)[^1]);

        fx.Env.Remove("BAR_BATCH_RELEASE_OVERRUN");
        var c3 = new FakeCaller();
        var s3 = await fx.Run(c3);
        Assert.Equal((1, 1), (c3.Calls, s3.NewRecords));
        Assert.Equal(2, fx.Records().Count);
    }

    [Theory]
    [InlineData("budget_overrun_without_excess")]
    [InlineData("overrun_released_without_excess")]
    [InlineData("pending_after_response")]
    public async Task N1_invalid_overrun_transitions_refuse(string defect)
    {
        using var fx = new BatchFixture(tasks: 1);
        await fx.Run(new FakeCaller());                          // normal usage: no overrun
        var plan = Hashing.FileSha256(fx.PlanPath);
        var row = defect switch
        {
            "budget_overrun_without_excess" => new JsonObject { ["type"] = "budget_overrun", ["prompt_tokens"] = 1, ["reservation"] = 1 },
            "overrun_released_without_excess" => new JsonObject { ["type"] = "overrun_released", ["reason"] = "x" },
            _ => new JsonObject
            {
                ["type"] = "pending", ["deployment"] = "gpt-4.1", ["reservation"] = Reservation(),
                ["observation_sha256"] = Hashing.Sha256Hex("OBS page_01 B_full F1"),
            },
        };
        row["key"] = Key1;
        row["plan_sha256"] = plan;
        row["ts"] = DateTimeOffset.UtcNow.ToString("O");
        row["attempt"] = defect == "pending_after_response" ? 2 : 1;
        File.AppendAllText(fx.JournalPath, row.ToJsonString() + "\n");
        var c = new FakeCaller();
        await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
        Assert.Equal(0, c.Calls);
    }

    // Related stops: each one, then a plain restart

    [Fact]
    public async Task Stop_budget_before_call_holds_across_restarts()
    {
        using var fx = new BatchFixture(tasks: 1);
        fx.Env["BAR_BATCH_MAX_INPUT_TOKENS"] = (Reservation() - 1).ToString();
        foreach (var _ in Enumerable.Range(0, 2))
        {
            var c = new FakeCaller();
            await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c));
            Assert.Equal(0, c.Calls);
        }
        Assert.Empty(fx.Journal());
    }

    [Theory]
    [InlineData("timeout")]
    [InlineData("503")]
    [InlineData("fail")]
    public async Task Stop_possibly_billed_error_holds_across_restarts(string outcome)
    {
        using var fx = new BatchFixture(tasks: 1);
        var c1 = new FakeCaller(outcome);
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c1));
        Assert.Equal(1, c1.Calls);
        Assert.Equal("error", JournalTypes(fx)[^1]);
        foreach (var _ in Enumerable.Range(0, 2))
        {
            var c = new FakeCaller();
            await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c));
            Assert.Equal(0, c.Calls);
        }
    }

    [Fact]
    public async Task Stop_exhausted_429_is_not_persistent_by_design_and_pays_once_after_restart()
    {
        using var fx = new BatchFixture(tasks: 1);
        var c1 = new FakeCaller("429", "429", "429", "429");
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(c1));
        Assert.Equal(4, c1.Calls);
        Assert.Empty(fx.Records());

        var c2 = new FakeCaller();
        var s2 = await fx.Run(c2);
        Assert.Equal((1, 1), (c2.Calls, s2.NewRecords));
        Assert.Single(fx.Records());
        Assert.Single(fx.Journal(), j => j["type"]!.GetValue<string>() == "response");
    }

    [Fact]
    public async Task Stop_resume_mismatch_holds_across_restarts()
    {
        using var fx = new BatchFixture(tasks: 2);
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(new FakeCaller("ok", "fail")));
        fx.Env["BAR_BATCH_RELEASE"] = "gpt-4.1|B_full|F1|page_01|t_02|0";
        await Assert.ThrowsAsync<BatchStoppedException>(() => fx.Run(new FakeCaller()));
        fx.Env.Remove("BAR_BATCH_RELEASE");
        var shard = File.ReadAllLines(fx.ShardPath);
        var rec = JsonNode.Parse(shard[0])!.AsObject();
        rec["completion_tokens"] = 8;
        File.WriteAllText(fx.ShardPath, rec.ToJsonString() + "\n");
        foreach (var _ in Enumerable.Range(0, 2))
        {
            var c = new FakeCaller();
            await Assert.ThrowsAsync<BatchRefusedException>(() => fx.Run(c));
            Assert.Equal(0, c.Calls);
        }
    }

    [Fact]
    public async Task Stop_observation_mismatch_holds_across_restarts()
    {
        using var fx = new BatchFixture(tasks: 1);
        foreach (var _ in Enumerable.Range(0, 2))
        {
            var c = new FakeCaller();
            await Assert.ThrowsAsync<BatchRefusedException>(() =>
                fx.Run(c, new FakeExecutor { Observation = e => BatchFixture.ObsText(e) + " " }));
            Assert.Equal(0, c.Calls);
        }
        Assert.Empty(fx.Journal());
    }

    // The legacy guard reads .env exactly as Config's DotNetEnv does

    private static string? GuardWithDotEnv(byte[] content)
    {
        var root = Path.Combine(Path.GetTempPath(), "guard2_" + Guid.NewGuid().ToString("N")[..8]);
        var deep = Path.Combine(root, "bin");
        Directory.CreateDirectory(deep);
        try
        {
            File.WriteAllBytes(Path.Combine(root, ".env"), content);
            return BoundedAgents.Experiments.LegacyBatchGuard.RefuseReason(_ => null, Array.Empty<string>(), deep);
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static byte[] Utf8(string s) => Encoding.UTF8.GetBytes(s);

    [Theory]
    // valid DotNetEnv forms: tab after export, set / SET / set -x
    [InlineData("export\tREVISION_BATCH=1\n")]
    [InlineData("set REVISION_BATCH=1\n")]
    [InlineData("SET REVISION_BATCH=1\n")]
    [InlineData("set -x REVISION_BATCH=1\n")]
    // common assignment forms
    [InlineData("export REVISION_BATCH=1\n")]
    [InlineData("REVISION_BATCH='1'\n")]
    [InlineData("REVISION_BATCH=\"1\"\n")]
    [InlineData(" REVISION_BATCH = 1 \n")]
    [InlineData("REVISION_BATCH=1 # comment\n")]
    [InlineData("A=b\r\nREVISION_BATCH=1\r\n")]
    [InlineData("REVISION_BATCH=\n")]
    // fail-closed: any mention, parsed or not
    [InlineData("# REVISION_BATCH=1\n")]
    [InlineData("REVISION_BATCH:1\n")]
    [InlineData("revision_batch=1\n")]
    [InlineData("BAR_BATCH_BLOCKS 1\n")]
    [InlineData("export BAR_BATCH_BLOCKS\n")]
    public void N2_legacy_guard_refuses(string dotenv) => Assert.NotNull(GuardWithDotEnv(Utf8(dotenv)));

    [Fact]
    public void N2_legacy_guard_refuses_with_a_BOM() =>
        Assert.NotNull(GuardWithDotEnv(new byte[] { 0xEF, 0xBB, 0xBF }.Concat(Utf8("REVISION_BATCH=1\r\n")).ToArray()));

    [Theory]
    [InlineData("A=b\n")]
    [InlineData("BAR_BATCH_MAX_INPUT_TOKENS=5\n")]
    [InlineData("export BAR_BATCH_BLOCKS=1,2 # only these\n")]
    public void N2_legacy_guard_lets_valid_unrelated_dotenv_through(string dotenv) =>
        Assert.Null(GuardWithDotEnv(Utf8(dotenv)));

    [Fact]
    public void N2_guard_finds_the_same_dotenv_as_Config()
    {
        var configFind = typeof(Config).GetMethod("FindEnvFile",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static)!;
        Assert.Equal((string?)configFind.Invoke(null, null),
                     BoundedAgents.Experiments.LegacyBatchGuard.FindDotEnv(AppContext.BaseDirectory));
    }

    [Theory]
    [InlineData("export\tREVISION_BATCH=1\nset -x BAR_BATCH_BLOCKS='1,2' # c\r\nSET A = \"b\"\n")]
    [InlineData("BAR_BATCH_MAX_INPUT_TOKENS=5\nexport BAR_BATCH_RELEASE=k\n")]
    public void N2_guard_values_are_DotNetEnv_values(string dotenv)
    {
        var dir = Path.Combine(Path.GetTempPath(), "guard3_" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(dir);
        try
        {
            var path = Path.Combine(dir, ".env");
            File.WriteAllText(path, dotenv);
            var expected = DotNetEnv.Env.LoadContents(dotenv, new DotNetEnv.LoadOptions(setEnvVars: false))
                .Select(kv => (kv.Key, kv.Value)).ToList();
            var actual = BoundedAgents.Experiments.LegacyBatchGuard.ReadDotEnv(path)
                .SelectMany(kv => kv.Value.Select(v => (kv.Key, v))).ToList();
            Assert.Equal(expected.OrderBy(x => x.Key), actual.OrderBy(x => x.Key));
            Assert.Null(Environment.GetEnvironmentVariable("BAR_BATCH_RELEASE"));   // read, never loaded
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    // The same guard at process level: shadow copies of the two executables + a fictitious .env

    private static readonly string[] ScrubPrefixes = { "BAR_", "AZURE", "OPENAI", "ANTHROPIC" };

    private static readonly string[] ModeFlags =
    {
        "SMOKE_TEST", "LLM_SMOKE_TEST", "PREDICATE_CONTROLS", "VALIDATE_ENCODING", "AXIS_C", "DUMP_OBSERVATIONS",
        "SENSITIVITY_CONSISTENT", "DUMP_BATCH_OBSERVATIONS", "REVISION_BATCH", "REAL_PILOT",
    };

    internal static async Task<(int Exit, string Err)> RunShadow(
        string binDir, string dll, string dotenv, string args, IReadOnlyDictionary<string, string>? env = null)
    {
        Assert.True(File.Exists(Path.Combine(binDir, dll)), $"build {dll} first");
        var shadow = Path.Combine(Path.GetTempPath(), "shadow_" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(shadow);
        try
        {
            foreach (var f in Directory.GetFiles(binDir))
            {
                File.Copy(f, Path.Combine(shadow, Path.GetFileName(f)));
            }
            File.WriteAllText(Path.Combine(shadow, ".env"), dotenv);
            var psi = new ProcessStartInfo("dotnet", $"\"{Path.Combine(shadow, dll)}\" {args}")
            {
                WorkingDirectory = shadow, UseShellExecute = false,
                RedirectStandardOutput = true, RedirectStandardError = true,
            };
            foreach (var k in psi.Environment.Keys.ToList())
            {
                if (ScrubPrefixes.Any(p => k.StartsWith(p, StringComparison.OrdinalIgnoreCase)) || ModeFlags.Contains(k))
                {
                    psi.Environment.Remove(k);
                }
            }
            foreach (var (k, v) in env ?? new Dictionary<string, string>())
            {
                psi.Environment[k] = v;
            }
            using var p = Process.Start(psi)!;
            var stdout = p.StandardOutput.ReadToEndAsync();
            var stderr = p.StandardError.ReadToEndAsync();
            await p.WaitForExitAsync().WaitAsync(TimeSpan.FromMinutes(2));
            await stdout;
            return (p.ExitCode, await stderr);
        }
        finally
        {
            try { Directory.Delete(shadow, recursive: true); } catch { }
        }
    }

    [Theory]
    [InlineData("export\tREVISION_BATCH=1\n")]
    [InlineData("set REVISION_BATCH=1\n")]
    [InlineData("SET REVISION_BATCH=1\n")]
    [InlineData("set -x REVISION_BATCH=1\n")]
    public async Task N2_legacy_entrypoint_exits_2_for_dotenv_variants(string dotenv)
    {
        var (exit, err) = await RunShadow(Path.Combine(Testbed.RepoRoot, "experiments", "bin", "Debug", "net10.0"),
                                          "Experiments.dll", dotenv, "");
        Assert.True(exit == 2, $"exit {exit}; stderr: {err}");
    }

    [Fact]
    public async Task N2_batch_entrypoint_exits_2_for_an_unparsed_BAR_BATCH_line()
    {
        var env = new Dictionary<string, string>
        {
            ["BAR_MODEL_DEPLOYMENT_1"] = "gpt-4.1", ["BAR_MODEL_DEPLOYMENT_2"] = "gpt-4.1-nano",
            ["BAR_MODEL_DEPLOYMENT_4"] = "o4-mini", ["BAR_BATCH_MAX_INPUT_TOKENS"] = "120000000",
        };
        var (exit, err) = await RunShadow(Path.Combine(Testbed.RepoRoot, "experiments", "batch", "bin", "Debug", "net10.0"),
                                          "Experiments.Batch.dll", "BAR_BATCH_BLOCKS 1\n", "--preflight-only", env);
        Assert.True(exit == 2, $"exit {exit}; stderr: {err}");
    }
}
