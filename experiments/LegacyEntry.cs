namespace BoundedAgents.Experiments;

/// <summary>The modes of the legacy entrypoint (experiments/Program.cs), in its dispatch order.</summary>
public enum LegacyMode
{
    Smoke, LlmSmoke, PredicateControls, ValidateEncoding, AxisC, DumpObservations,
    SensitivityConsistent, DumpBatchObservations, RealPilot, Replay, Matrix,
}

/// <summary>
/// The one choke point of the legacy entrypoint: resolves the mode exactly as experiments/Program.cs
/// dispatches it and, for a mode that calls a model, requires the explicit "--execute" argument and env
/// BAR_LEGACY_CONFIRM=paid set in the process (a .env line naming it is refused). Zero-LLM modes need
/// neither. Runs before Config, any client or any network. Also compiled into Experiments.Tests.
/// </summary>
public static class LegacyEntry
{
    public const string ExecuteFlag = "--execute";
    public const string ConfirmEnv = "BAR_LEGACY_CONFIRM";
    public const string ConfirmValue = "paid";

    /// <summary>Modes that call a model (LlmClient via GroundingRunner.RunOneAsync or directly).</summary>
    public static readonly IReadOnlySet<LegacyMode> Paid = new HashSet<LegacyMode>
    {
        LegacyMode.LlmSmoke, LegacyMode.ValidateEncoding, LegacyMode.AxisC,
        LegacyMode.SensitivityConsistent, LegacyMode.Matrix,
    };

    public const string Usage =
        "legacy entrypoint: a mode that calls a model (the matrix [default], LLM_SMOKE_TEST, VALIDATE_ENCODING, AXIS_C,\n" +
        "SENSITIVITY_CONSISTENT) runs only as\n" +
        "  BAR_LEGACY_CONFIRM=paid dotnet run --project experiments -- --execute\n" +
        "with BAR_LEGACY_CONFIRM set in the process for that one run (never in .env). Zero-LLM modes\n" +
        "(SMOKE_TEST, PREDICATE_CONTROLS, DUMP_OBSERVATIONS, DUMP_BATCH_OBSERVATIONS, REAL_PILOT, --replay)\n" +
        "need neither. The Revision 1 batch runs only via experiments/batch.";

    /// <summary>The "=1" mode flags, in dispatch order (first match wins).</summary>
    public static readonly (string Env, LegacyMode Mode)[] FlagModes =
    {
        ("SMOKE_TEST", LegacyMode.Smoke), ("LLM_SMOKE_TEST", LegacyMode.LlmSmoke),
        ("PREDICATE_CONTROLS", LegacyMode.PredicateControls), ("VALIDATE_ENCODING", LegacyMode.ValidateEncoding),
        ("AXIS_C", LegacyMode.AxisC), ("DUMP_OBSERVATIONS", LegacyMode.DumpObservations),
        ("SENSITIVITY_CONSISTENT", LegacyMode.SensitivityConsistent),
        ("DUMP_BATCH_OBSERVATIONS", LegacyMode.DumpBatchObservations),
    };

    /// <summary>The mode experiments/Program.cs runs, with the same order and conditions as its dispatch.</summary>
    public static LegacyMode Resolve(Func<string, string?> env, IReadOnlyList<string> args)
    {
        foreach (var (name, mode) in FlagModes)
        {
            if (env(name) == "1")
            {
                return mode;
            }
        }
        if (env("REAL_PILOT") is { Length: > 0 })
        {
            return LegacyMode.RealPilot;
        }
        return args.Contains("--replay") ? LegacyMode.Replay : LegacyMode.Matrix;
    }

    /// <summary>The mode, and why it must not start (empty when it may).</summary>
    public static (LegacyMode Mode, IReadOnlyList<string> Problems) Gate(
        Func<string, string?> env, IReadOnlyList<string> args, string startDir)
    {
        var mode = Resolve(env, args);
        var problems = new List<string>(DotEnvConfirmProblems(startDir));
        var confirm = env(ConfirmEnv);
        if (Paid.Contains(mode))
        {
            if (!args.Contains(ExecuteFlag, StringComparer.Ordinal))
            {
                problems.Add($"mode {mode} calls a model and needs {ExecuteFlag}");
            }
            foreach (var a in args.Where(a => a != ExecuteFlag))
            {
                problems.Add($"unknown argument '{a}' for mode {mode} (only {ExecuteFlag})");
            }
            if (args.Count(a => a == ExecuteFlag) > 1)
            {
                problems.Add($"{ExecuteFlag} given more than once");
            }
            if (string.IsNullOrEmpty(confirm))
            {
                problems.Add($"mode {mode} calls a model and needs env {ConfirmEnv}={ConfirmValue} in the process");
            }
            else if (!string.Equals(confirm, ConfirmValue, StringComparison.Ordinal))
            {
                problems.Add($"env {ConfirmEnv} must be exactly '{ConfirmValue}'");
            }
        }
        else
        {
            if (args.Contains(ExecuteFlag, StringComparer.Ordinal))
            {
                problems.Add($"{ExecuteFlag} given to zero-LLM mode {mode}");
            }
            if (!string.IsNullOrEmpty(confirm))
            {
                problems.Add($"env {ConfirmEnv} is set for zero-LLM mode {mode} — unset it");
            }
        }
        return (mode, problems);
    }

    /// <summary>Lines of the .env Config would load that mention BAR_LEGACY_CONFIRM (any case).</summary>
    public static IReadOnlyList<string> DotEnvConfirmProblems(string startDir)
    {
        var path = LegacyBatchGuard.FindDotEnv(startDir);
        if (path is null)
        {
            return Array.Empty<string>();
        }
        var lines = File.ReadAllText(path).Split('\n');
        var problems = new List<string>();
        for (int i = 0; i < lines.Length; i++)
        {
            if (lines[i].Contains(ConfirmEnv, StringComparison.OrdinalIgnoreCase))
            {
                problems.Add($"{path}:{i + 1} mentions {ConfirmEnv} — set it in the process for one run, not in .env");
            }
        }
        return problems;
    }

    /// <summary>Gate, then <paramref name="run"/>(mode); refused → problems + usage on stderr, exit 2, no run.</summary>
    public static async Task<int> RunAsync(
        Func<string, string?> env, IReadOnlyList<string> args, string startDir, Func<LegacyMode, Task<int>> run)
    {
        var (mode, problems) = Gate(env, args, startDir);
        if (problems.Count > 0)
        {
            return Refuse(problems);
        }
        return await run(mode);
    }

    /// <summary>Prints the problems and the usage; exit code 2.</summary>
    public static int Refuse(IReadOnlyList<string> problems)
    {
        foreach (var p in problems)
        {
            Console.Error.WriteLine($"[experiments] REFUSED: {p}");
        }
        Console.Error.WriteLine(Usage);
        return 2;
    }
}
