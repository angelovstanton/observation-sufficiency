using BoundedAgents.Experiments.Batch;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// The paid run needs "--execute" and BAR_BATCH_CONFIRM_PLAN equal to the first 12 characters of the
/// executed plan's sha256; any other combination exits 2 before anything runs, so a lost or mangled
/// "--preflight-only" can never start a paid batch. The route passed to BatchEntry.RunAsync stands in for
/// Program.cs: Execute runs the real runner on a fixture with a fake client.
/// </summary>
public class ExecuteOptInTests
{
    private static readonly string BatchConfirm = BatchPins.PlanSha256[..12];
    private static readonly string PilotConfirm = PilotPins.PlanSha256[..12];

    private sealed class Route
    {
        public List<(bool Pilot, BatchMode Mode)> Calls { get; } = new();
        public FakeCaller Caller { get; } = new();
        private readonly BatchFixture _fx;

        public Route(BatchFixture fx) => _fx = fx;

        public async Task<int> Run(bool pilot, BatchMode mode)
        {
            Calls.Add((pilot, mode));
            if (mode == BatchMode.Execute)
            {
                await _fx.Run(Caller);
            }
            return 0;
        }
    }

    private static async Task<(int Exit, Route Route, BatchFixture Fx)> Start(string? confirm, params string[] args)
    {
        var fx = new BatchFixture();
        var route = new Route(fx);
        var env = new Dictionary<string, string?> { [BatchEntry.ConfirmEnv] = confirm };
        var exit = await BatchEntry.RunAsync(k => env.GetValueOrDefault(k), args, route.Run);
        return (exit, route, fx);
    }

    private static async Task AssertRefusedBeforeAnything(string? confirm, params string[] args)
    {
        var (exit, route, fx) = await Start(confirm, args);
        using (fx)
        {
            Assert.Equal(2, exit);
            Assert.Empty(route.Calls);
            Assert.Equal(0, route.Caller.Calls);
            Assert.False(Directory.Exists(fx.OutDir));          // no journal, no pending line, no records
        }
    }

    [Fact]
    public async Task No_arguments_exit_2_and_never_reach_the_client()
    {
        await AssertRefusedBeforeAnything(null);
        await AssertRefusedBeforeAnything(null, "--plan", "pilot");
    }

    [Fact]
    public async Task Execute_without_confirm_exits_2()
    {
        await AssertRefusedBeforeAnything(null, "--execute");
        await AssertRefusedBeforeAnything("", "--execute");
        await AssertRefusedBeforeAnything(null, "--plan", "pilot", "--execute");
    }

    [Fact]
    public async Task Execute_with_a_wrong_confirm_exits_2()
    {
        foreach (var wrong in new[]
                 {
                     PilotConfirm, BatchConfirm[..11], BatchConfirm.ToUpperInvariant(), " " + BatchConfirm,
                     BatchConfirm + " ", BatchPins.PlanSha256, BatchConfirm[..11] + "x",
                 })
        {
            await AssertRefusedBeforeAnything(wrong, "--execute");
        }
        // The pilot profile is confirmed only by the pilot plan's prefix.
        await AssertRefusedBeforeAnything(BatchConfirm, "--plan", "pilot", "--execute");
        await AssertRefusedBeforeAnything(PilotPins.PlanSha256, "--plan", "pilot", "--execute");
    }

    [Fact]
    public async Task Confirm_without_execute_exits_2()
    {
        await AssertRefusedBeforeAnything(BatchConfirm);
        await AssertRefusedBeforeAnything(BatchConfirm, "--preflight-only");
        await AssertRefusedBeforeAnything(BatchConfirm, "--verify-observations");
        await AssertRefusedBeforeAnything(PilotConfirm, "--plan", "pilot");
        await AssertRefusedBeforeAnything(PilotConfirm, "--plan", "pilot", "--preflight-only");
    }

    [Fact]
    public async Task Execute_cannot_be_combined_with_the_zero_llm_modes()
    {
        await AssertRefusedBeforeAnything(BatchConfirm, "--execute", "--preflight-only");
        await AssertRefusedBeforeAnything(BatchConfirm, "--verify-observations", "--execute");
        await AssertRefusedBeforeAnything(BatchConfirm, "--execute", "--execute");
        await AssertRefusedBeforeAnything(PilotConfirm, "--plan", "pilot", "--execute", "--preflight-only");
        Assert.Contains(BatchEntry.CheckFlags(k => k == BatchEntry.ConfirmEnv ? BatchConfirm : null,
                                              new[] { "--execute", "--preflight-only" }),
                        p => p.Contains("cannot be combined"));
    }

    [Fact]
    public async Task Execute_with_the_right_confirm_starts_the_paid_route()
    {
        var (exit, route, fx) = await Start(BatchConfirm, "--execute");
        using (fx)
        {
            Assert.Equal(0, exit);
            Assert.Equal(new[] { (false, BatchMode.Execute) }, route.Calls);
            Assert.Equal(3, route.Caller.Calls);
            Assert.Equal(3, fx.Records().Count);
        }

        var (pexit, proute, pfx) = await Start(PilotConfirm, "--plan", "pilot", "--execute");
        using (pfx)
        {
            Assert.Equal(0, pexit);
            Assert.Equal(new[] { (true, BatchMode.Execute) }, proute.Calls);
        }
    }

    [Theory]
    [InlineData("")]
    [InlineData(" ")]
    [InlineData("--PREFLIGHT-ONLY")]
    [InlineData("-preflight-only")]
    [InlineData("--preflight-only=")]
    [InlineData("--preflight-only ")]
    [InlineData("--preflight-only --plan pilot")]
    [InlineData("EXECUTE")]
    [InlineData("--Execute")]
    public async Task Lost_or_mangled_preflight_argument_never_reaches_the_client(string arg)
    {
        await AssertRefusedBeforeAnything(null, arg);
        await AssertRefusedBeforeAnything(BatchConfirm, arg);
        await AssertRefusedBeforeAnything(null, "--plan", "pilot", arg);
    }

    [Fact]
    public async Task Zero_llm_modes_route_as_such_and_never_as_execute()
    {
        foreach (var (args, expected) in new[]
                 {
                     (new[] { "--preflight-only" }, (false, BatchMode.PreflightOnly)),
                     (new[] { "--verify-observations" }, (false, BatchMode.VerifyObservations)),
                     (new[] { "--plan", "pilot", "--preflight-only" }, (true, BatchMode.PreflightOnly)),
                     (new[] { "--verify-observations", "--plan", "pilot" }, (true, BatchMode.VerifyObservations)),
                 })
        {
            var (exit, route, fx) = await Start(null, args);
            using (fx)
            {
                Assert.Equal(0, exit);
                Assert.Equal(new[] { expected }, route.Calls);
                Assert.Equal(0, route.Caller.Calls);
                Assert.False(Directory.Exists(fx.OutDir));
            }
        }
    }

    [Fact]
    public async Task Unknown_argument_exits_2()
    {
        await AssertRefusedBeforeAnything(null, "--replay");
        await AssertRefusedBeforeAnything(BatchConfirm, "--execute", "--replay");
    }

    [Theory]
    [InlineData("BAR_BATCH_CONFIRM_PLAN=567c370855a2")]
    [InlineData("export BAR_BATCH_CONFIRM_PLAN=567c370855a2")]
    [InlineData("bar_batch_confirm_plan=567c370855a2")]
    [InlineData("# BAR_BATCH_CONFIRM_PLAN=567c370855a2")]
    public void Confirm_in_dotenv_is_refused(string line)
    {
        var dir = Path.Combine(Path.GetTempPath(), "optin_" + Guid.NewGuid().ToString("N")[..10]);
        Directory.CreateDirectory(dir);
        try
        {
            File.WriteAllText(Path.Combine(dir, ".env"), "BAR_MODEL_DEPLOYMENT_1=gpt-4.1\n" + line + "\n");
            Assert.NotEmpty(BatchEntry.DotEnvConfirmProblems(dir));
            File.WriteAllText(Path.Combine(dir, ".env"), "BAR_MODEL_DEPLOYMENT_1=gpt-4.1\n");
            Assert.Empty(BatchEntry.DotEnvConfirmProblems(dir));
        }
        finally
        {
            Directory.Delete(dir, recursive: true);
        }
    }

    [Fact]
    public void Expected_confirm_is_the_pinned_plan_prefix_of_each_profile()
    {
        Assert.Equal(BatchPins.PlanSha256[..12], BatchEntry.ExpectedConfirm(pilot: false));
        Assert.Equal(PilotPins.PlanSha256[..12], BatchEntry.ExpectedConfirm(pilot: true));
        Assert.NotEqual(BatchEntry.ExpectedConfirm(false), BatchEntry.ExpectedConfirm(true));
    }
}
