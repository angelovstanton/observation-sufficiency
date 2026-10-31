using System.Text.RegularExpressions;
using BoundedAgents.Experiments;
using BoundedAgents.Experiments.Batch;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// LegacyEntry.Gate is the single choke point before every mode of the legacy entrypoint: a model-calling
/// mode needs "--execute" and BAR_LEGACY_CONFIRM=paid in the process environment; zero-LLM modes need
/// neither. The route passed to LegacyEntry.RunAsync stands in for experiments/Program.cs and counts the
/// clients a paid mode would create.
/// </summary>
public class LegacyOptInTests
{
    private const string Confirm = "BAR_LEGACY_CONFIRM";

    /// <summary>Selector env for each mode (Matrix: none — it is the default).</summary>
    private static readonly Dictionary<LegacyMode, (string? Env, string? Value, string[] Args)> Select = new()
    {
        [LegacyMode.Matrix] = (null, null, Array.Empty<string>()),
        [LegacyMode.LlmSmoke] = ("LLM_SMOKE_TEST", "1", Array.Empty<string>()),
        [LegacyMode.ValidateEncoding] = ("VALIDATE_ENCODING", "1", Array.Empty<string>()),
        [LegacyMode.AxisC] = ("AXIS_C", "1", Array.Empty<string>()),
        [LegacyMode.SensitivityConsistent] = ("SENSITIVITY_CONSISTENT", "1", Array.Empty<string>()),
        [LegacyMode.Smoke] = ("SMOKE_TEST", "1", Array.Empty<string>()),
        [LegacyMode.PredicateControls] = ("PREDICATE_CONTROLS", "1", Array.Empty<string>()),
        [LegacyMode.DumpObservations] = ("DUMP_OBSERVATIONS", "1", Array.Empty<string>()),
        [LegacyMode.DumpBatchObservations] = ("DUMP_BATCH_OBSERVATIONS", "1", Array.Empty<string>()),
        [LegacyMode.RealPilot] = ("REAL_PILOT", "dump", Array.Empty<string>()),
        [LegacyMode.Replay] = (null, null, new[] { "--replay" }),
    };

    public static readonly TheoryData<LegacyMode> PaidModes = new()
    {
        LegacyMode.Matrix, LegacyMode.LlmSmoke, LegacyMode.ValidateEncoding, LegacyMode.AxisC,
        LegacyMode.SensitivityConsistent,
    };

    public static readonly TheoryData<LegacyMode> ZeroLlmModes = new()
    {
        LegacyMode.Smoke, LegacyMode.PredicateControls, LegacyMode.DumpObservations,
        LegacyMode.DumpBatchObservations, LegacyMode.RealPilot, LegacyMode.Replay,
    };

    /// <summary>A temp start directory with an optional .env (the one Config would load from it).</summary>
    private sealed class Dir : IDisposable
    {
        public string Path { get; } = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "legacy_" + Guid.NewGuid().ToString("N")[..10]);

        public Dir(string? dotEnv = null)
        {
            Directory.CreateDirectory(Path);
            if (dotEnv is not null)
            {
                File.WriteAllText(System.IO.Path.Combine(Path, ".env"), dotEnv);
            }
        }

        public void Dispose()
        {
            try { Directory.Delete(Path, recursive: true); } catch { }
        }
    }

    private sealed class Route
    {
        public List<LegacyMode> Runs { get; } = new();
        /// <summary>What Program.cs would create for a paid mode: the model client (here, a counter).</summary>
        public int ClientsCreated { get; private set; }

        public Task<int> Run(LegacyMode mode)
        {
            Runs.Add(mode);
            if (LegacyEntry.Paid.Contains(mode))
            {
                ClientsCreated++;
            }
            return Task.FromResult(0);
        }
    }

    private static async Task<(int Exit, Route Route)> Start(
        LegacyMode mode, string? confirm, string[] extraArgs, string? dotEnv = null, Dictionary<string, string?>? more = null)
    {
        var (name, value, selArgs) = Select[mode];
        var env = new Dictionary<string, string?>(more ?? new());
        if (name is not null)
        {
            env[name] = value;
        }
        env[Confirm] = confirm;
        using var dir = new Dir(dotEnv);
        var route = new Route();
        var exit = await LegacyEntry.RunAsync(k => env.GetValueOrDefault(k), selArgs.Concat(extraArgs).ToArray(), dir.Path, route.Run);
        return (exit, route);
    }

    private static async Task AssertRefused(LegacyMode mode, string? confirm, string[] args, string? dotEnv = null,
                                            Dictionary<string, string?>? more = null)
    {
        var (exit, route) = await Start(mode, confirm, args, dotEnv, more);
        Assert.Equal(2, exit);
        Assert.Empty(route.Runs);
        Assert.Equal(0, route.ClientsCreated);
    }

    // Paid modes

    [Theory]
    [MemberData(nameof(PaidModes))]
    public async Task Paid_mode_without_flag_or_confirm_exits_2_with_no_client(LegacyMode mode)
    {
        await AssertRefused(mode, null, Array.Empty<string>());
    }

    [Theory]
    [MemberData(nameof(PaidModes))]
    public async Task Paid_mode_with_only_execute_exits_2(LegacyMode mode)
    {
        await AssertRefused(mode, null, new[] { "--execute" });
        await AssertRefused(mode, "", new[] { "--execute" });
    }

    [Theory]
    [MemberData(nameof(PaidModes))]
    public async Task Paid_mode_with_only_the_process_confirm_exits_2(LegacyMode mode)
    {
        await AssertRefused(mode, "paid", Array.Empty<string>());
    }

    [Theory]
    [MemberData(nameof(PaidModes))]
    public async Task Paid_mode_with_confirm_in_dotenv_exits_2_even_with_execute(LegacyMode mode)
    {
        foreach (var line in new[] { "BAR_LEGACY_CONFIRM=paid", "export BAR_LEGACY_CONFIRM=paid", "bar_legacy_confirm=paid", "# BAR_LEGACY_CONFIRM=paid" })
        {
            // Only in .env (the process lacks it) — and also alongside a correct process value.
            await AssertRefused(mode, null, new[] { "--execute" }, dotEnv: "BAR_MODEL_DEPLOYMENT_1=gpt-4.1\n" + line + "\n");
            await AssertRefused(mode, "paid", new[] { "--execute" }, dotEnv: line + "\n");
        }
    }

    [Theory]
    [MemberData(nameof(PaidModes))]
    public async Task Paid_mode_with_a_wrong_confirm_exits_2(LegacyMode mode)
    {
        foreach (var wrong in new[] { "PAID", " paid", "paid ", "1", "yes", "true", BatchEntry.ExpectedConfirm(false) })
        {
            await AssertRefused(mode, wrong, new[] { "--execute" });
        }
    }

    [Theory]
    [MemberData(nameof(PaidModes))]
    public async Task Paid_mode_with_execute_and_confirm_creates_the_client(LegacyMode mode)
    {
        var (exit, route) = await Start(mode, "paid", new[] { "--execute" });
        Assert.Equal(0, exit);
        Assert.Equal(new[] { mode }, route.Runs);
        Assert.Equal(1, route.ClientsCreated);
    }

    [Theory]
    [MemberData(nameof(PaidModes))]
    public async Task Paid_mode_refuses_any_other_argument(LegacyMode mode)
    {
        foreach (var extra in new[] { new[] { "--execute", "--execute" }, new[] { "--execute", "" }, new[] { "--execute", "--plan", "pilot" }, new[] { "--EXECUTE" }, new[] { "-execute" } })
        {
            await AssertRefused(mode, "paid", extra);
        }
    }

    // Argument, CONFIRM and .env combinations that must never reach a model call

    public static readonly TheoryData<string, string[], string?, string?> LegacyScenarios = new()
    {
        { "no arguments", Array.Empty<string>(), null, null },
        { "only --plan pilot", new[] { "--plan", "pilot" }, null, null },
        { "empty argument", new[] { "" }, null, null },
        { "only --execute", new[] { "--execute" }, null, null },
        { "only the process batch CONFIRM", Array.Empty<string>(), "567c370855a2", null },
        { "--execute + the batch CONFIRM", new[] { "--execute" }, "567c370855a2", null },
        { "--execute + a wrong batch CONFIRM", new[] { "--execute" }, "000000000000", null },
        { "batch CONFIRM in .env", new[] { "--execute" }, null, "BAR_BATCH_CONFIRM_PLAN=567c370855a2\n" },
        { "legacy CONFIRM in .env", new[] { "--execute" }, null, "BAR_LEGACY_CONFIRM=paid\n" },
        { "--preflight-only --execute", new[] { "--preflight-only", "--execute" }, "567c370855a2", null },
        { "--verify-observations --execute", new[] { "--verify-observations", "--execute" }, "567c370855a2", null },
        { "unknown argument", new[] { "--replay-out", "x" }, null, null },
        { "wrapper lost all arguments", Array.Empty<string>(), "567c370855a2", null },
    };

    [Theory]
    [MemberData(nameof(LegacyScenarios))]
    public async Task Legacy_scenario_exits_2_with_no_client(string scenario, string[] args, string? batchConfirm, string? dotEnv)
    {
        Assert.NotEmpty(scenario);
        var more = new Dictionary<string, string?> { ["BAR_BATCH_CONFIRM_PLAN"] = batchConfirm };
        await AssertRefused(LegacyMode.Matrix, null, args, dotEnv, more);
    }

    // Zero-LLM modes

    [Theory]
    [MemberData(nameof(ZeroLlmModes))]
    public async Task Zero_llm_mode_runs_as_before_without_flag(LegacyMode mode)
    {
        var (exit, route) = await Start(mode, null, Array.Empty<string>());
        Assert.Equal(0, exit);
        Assert.Equal(new[] { mode }, route.Runs);
        Assert.Equal(0, route.ClientsCreated);
        Assert.DoesNotContain(mode, LegacyEntry.Paid);
    }

    [Fact]
    public async Task Replay_with_its_own_arguments_runs_without_flag()
    {
        foreach (var args in new[]
                 {
                     new[] { "--replay", "experiments/runs/archive_20260615" },
                     new[] { "--replay", "in", "--replay-out", "out.jsonl" },
                     new[] { "--replay", "in", "--replay-out", "out.jsonl", "--dump-obs", "obs" },
                 })
        {
            var (exit, route) = await Start(LegacyMode.Matrix, null, args);
            Assert.Equal(0, exit);
            Assert.Equal(new[] { LegacyMode.Replay }, route.Runs);
            Assert.Equal(0, route.ClientsCreated);
        }
    }

    [Theory]
    [MemberData(nameof(ZeroLlmModes))]
    public async Task Zero_llm_mode_refuses_a_stray_execute_or_confirm(LegacyMode mode)
    {
        await AssertRefused(mode, null, new[] { "--execute" });
        await AssertRefused(mode, "paid", Array.Empty<string>());
        await AssertRefused(mode, null, Array.Empty<string>(), dotEnv: "BAR_LEGACY_CONFIRM=paid\n");
    }

    // Mode resolution keeps the precedence of the former dispatch chain

    [Fact]
    public void Resolve_keeps_the_former_precedence()
    {
        LegacyMode R(Dictionary<string, string?> env, params string[] args) => LegacyEntry.Resolve(k => env.GetValueOrDefault(k), args);
        Assert.Equal(LegacyMode.Matrix, R(new()));
        Assert.Equal(LegacyMode.Smoke, R(new() { ["SMOKE_TEST"] = "1", ["AXIS_C"] = "1" }));
        Assert.Equal(LegacyMode.LlmSmoke, R(new() { ["LLM_SMOKE_TEST"] = "1", ["AXIS_C"] = "1" }));
        Assert.Equal(LegacyMode.AxisC, R(new() { ["AXIS_C"] = "1", ["DUMP_OBSERVATIONS"] = "1" }, "--replay"));
        Assert.Equal(LegacyMode.RealPilot, R(new() { ["REAL_PILOT"] = "x" }, "--replay"));
        Assert.Equal(LegacyMode.Replay, R(new(), "--replay"));
        Assert.Equal(LegacyMode.Matrix, R(new() { ["AXIS_C"] = "true", ["SMOKE_TEST"] = "yes" }));   // only "1" selects
        Assert.Equal(LegacyMode.Matrix, R(new() { ["REAL_PILOT"] = "" }));
    }

    // Source guards: every model call is behind a paid mode, and Program.cs dispatches through the gate

    private static readonly Regex ModelCall = new(
        @"GroundingRunner\.RunOne(Staged)?Async\(|LlmClient\.Call\w*\(|CompleteChat|AzureOpenAIClient|ChatCompletionsClient|AnthropicClient|new\s+HttpClient",
        RegexOptions.Compiled);

    private static IEnumerable<string> LegacySources()
    {
        var expDir = Path.Combine(Testbed.RepoRoot, "experiments");
        return Directory.GetFiles(expDir, "*.cs")
            .Concat(Directory.GetFiles(Path.Combine(expDir, "modes"), "*.cs", SearchOption.AllDirectories))
            .Concat(Directory.GetFiles(Path.Combine(expDir, "verification"), "*.cs", SearchOption.AllDirectories))
            .Concat(Directory.GetFiles(Path.Combine(expDir, "models"), "*.cs", SearchOption.AllDirectories));
    }

    private static string CodeOnly(string path) => string.Join("\n",
        File.ReadAllLines(path).Select(l => l.TrimStart().StartsWith("//", StringComparison.Ordinal) ? "" : l));

    [Fact]
    public void Model_calls_exist_only_in_the_files_of_the_paid_modes()
    {
        var expDir = Path.Combine(Testbed.RepoRoot, "experiments");
        var withCalls = LegacySources()
            .Where(f => ModelCall.IsMatch(CodeOnly(f)))
            .Select(f => Path.GetRelativePath(expDir, f).Replace('\\', '/'))
            .OrderBy(f => f, StringComparer.Ordinal).ToList();
        Assert.Equal(new[]
        {
            "Program.cs",                         // Matrix
            "modes/AxisCMode.cs",                 // AxisC
            "modes/ConsistentSensitivityMode.cs", // SensitivityConsistent
            "modes/EncodingValidationMode.cs",    // ValidateEncoding
            "modes/SmokeTests.cs",                // LlmSmoke (RunLlmAsync only)
        }, withCalls);

        // In SmokeTests the zero-LLM RunAsync (SMOKE_TEST) comes first; every call is inside RunLlmAsync.
        var smoke = CodeOnly(Path.Combine(expDir, "modes", "SmokeTests.cs"));
        var llm = smoke.IndexOf("static async Task RunLlmAsync", StringComparison.Ordinal);
        Assert.True(llm > smoke.IndexOf("static async Task RunAsync", StringComparison.Ordinal));
        Assert.All(ModelCall.Matches(smoke), m => Assert.True(m.Index > llm, $"model call at {m.Index} outside RunLlmAsync"));
    }

    [Fact]
    public void Program_dispatches_only_by_the_gate()
    {
        var src = CodeOnly(Path.Combine(Testbed.RepoRoot, "experiments", "Program.cs"));
        var gate = src.IndexOf("LegacyEntry.Gate(", StringComparison.Ordinal);
        Assert.True(gate > 0);
        Assert.True(gate > src.IndexOf("LegacyBatchGuard.RefuseReason(", StringComparison.Ordinal));
        foreach (var later in new[] { "legacyMode ==", "Config.", "SmokeTests.", "AxisCMode.", "EncodingValidationMode.",
                                      "ConsistentSensitivityMode.", "GroundingRunner.", "ReplayMode.", "RealPilotMode." })
        {
            var i = src.IndexOf(later, StringComparison.Ordinal);
            Assert.True(i < 0 || i > gate, $"'{later}' before the gate");
        }
        // No mode is selected from the environment outside LegacyEntry.
        foreach (var (name, _) in LegacyEntry.FlagModes)
        {
            Assert.DoesNotContain($"GetEnvironmentVariable(\"{name}\")", src);
        }
        Assert.DoesNotContain("args.Contains(\"--replay\")", src);
        Assert.True(src.IndexOf("\"REAL_PILOT\"", StringComparison.Ordinal) > src.IndexOf("LegacyMode.RealPilot", StringComparison.Ordinal));
        // Each paid mode's branch is keyed by its LegacyMode, and the matrix only runs as Matrix.
        foreach (var m in new[] { "LlmSmoke", "ValidateEncoding", "AxisC", "SensitivityConsistent" })
        {
            Assert.Contains($"legacyMode == BoundedAgents.Experiments.LegacyMode.{m}", src);
        }
        Assert.True(src.IndexOf("legacyMode != BoundedAgents.Experiments.LegacyMode.Matrix", StringComparison.Ordinal)
                    < src.IndexOf("GroundingRunner.RunOneAsync(", StringComparison.Ordinal));
    }
}
