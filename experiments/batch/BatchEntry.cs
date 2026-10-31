namespace BoundedAgents.Experiments.Batch;

/// <summary>Which of the three modes a validated command line selects.</summary>
public enum BatchMode { PreflightOnly, VerifyObservations, Execute }

/// <summary>Fail-closed entry checks for the batch executable.</summary>
public static class BatchEntry
{
    /// <summary>Mode flags of the other entrypoints and the retired batch overrides.</summary>
    public static readonly string[] ConflictingEnv =
    {
        "SMOKE_TEST", "LLM_SMOKE_TEST", "PREDICATE_CONTROLS", "VALIDATE_ENCODING", "AXIS_C",
        "DUMP_OBSERVATIONS", "SENSITIVITY_CONSISTENT", "DUMP_BATCH_OBSERVATIONS", "REVISION_BATCH",
        "BAR_PAGE_IDS", "BAR_BATCH_PLAN",
    };

    public const string PreflightFlag = "--preflight-only";
    public const string VerifyFlag = "--verify-observations";
    /// <summary>The paid run: only with this flag and <see cref="ConfirmEnv"/>; there is no default mode.</summary>
    public const string ExecuteFlag = "--execute";
    public static readonly string[] AllowedArgs = { PreflightFlag, VerifyFlag, ExecuteFlag };

    /// <summary>Must equal the first <see cref="ConfirmLength"/> characters of the sha256 of the plan being executed.</summary>
    public const string ConfirmEnv = "BAR_BATCH_CONFIRM_PLAN";
    public const int ConfirmLength = 12;

    /// <summary>The second profile is selected only by these two adjacent arguments.</summary>
    public const string PlanFlag = "--plan";
    public const string PilotPlan = "pilot";

    public const string Usage =
        "usage: dotnet run --project experiments/batch -- [--plan pilot] <mode>\n" +
        "  --preflight-only        static checks, zero LLM\n" +
        "  --verify-observations   + every planned observation vs the pinned hashes (browser), zero LLM\n" +
        "  --execute               the PAID run; also needs env BAR_BATCH_CONFIRM_PLAN = the 12 characters\n" +
        "                          after 'plan' in the --preflight-only PASS line\n" +
        "There is no default mode: without arguments nothing runs (exit 2).";

    /// <summary>The value <see cref="ConfirmEnv"/> must have for the profile's pinned plan
    /// (preflight refuses unless the plan file's sha256 equals that pin).</summary>
    public static string ExpectedConfirm(bool pilot) =>
        (pilot ? PilotPins.PlanSha256 : BatchPins.PlanSha256)[..ConfirmLength];

    /// <summary>True only for exactly one adjacent "--plan pilot" (CheckFlags refuses every other use of --plan).</summary>
    public static bool IsPilot(IReadOnlyList<string> args)
    {
        var i = args.ToList().IndexOf(PlanFlag);
        return args.Count(a => a == PlanFlag) == 1 && i + 1 < args.Count && args[i + 1] == PilotPlan;
    }

    /// <summary>Empty when the batch may start; otherwise the reasons it must not.</summary>
    public static IReadOnlyList<string> CheckFlags(Func<string, string?> env, IReadOnlyList<string> args)
    {
        var problems = new List<string>();
        var pilot = false;
        if (args.Contains(PlanFlag, StringComparer.Ordinal))
        {
            if (!IsPilot(args))
            {
                problems.Add($"{PlanFlag} must appear once, followed by '{PilotPlan}'");
            }
            else
            {
                // Drop "--plan pilot"; the remaining arguments are checked as for the default profile.
                pilot = true;
                var i = args.ToList().IndexOf(PlanFlag);
                args = args.Where((_, j) => j != i && j != i + 1).ToList();
            }
        }
        foreach (var name in ConflictingEnv)
        {
            if (!string.IsNullOrEmpty(env(name)))
            {
                problems.Add($"env {name} is set — the batch runs alone");
            }
        }
        foreach (var a in args)
        {
            if (!AllowedArgs.Contains(a, StringComparer.Ordinal))
            {
                problems.Add($"unknown argument '{a}'");
            }
        }
        if (args.Count == 0)
        {
            problems.Add($"no mode given — pass {PreflightFlag}, {VerifyFlag} or {ExecuteFlag} (the paid run)");
        }
        var execute = args.Contains(ExecuteFlag, StringComparer.Ordinal);
        if (args.Count > 1)
        {
            problems.Add(execute
                ? $"{ExecuteFlag} cannot be combined with another argument"
                : $"at most one of {PreflightFlag} / {VerifyFlag}");
        }
        var confirm = env(ConfirmEnv);
        if (execute)
        {
            if (string.IsNullOrEmpty(confirm))
            {
                problems.Add($"{ExecuteFlag} needs env {ConfirmEnv} = the first {ConfirmLength} characters of the " +
                             $"plan's sha256 (shown by {PreflightFlag})");
            }
            else if (!string.Equals(confirm, ExpectedConfirm(pilot), StringComparison.Ordinal))
            {
                problems.Add($"env {ConfirmEnv} does not match the plan this run would execute");
            }
        }
        else if (!string.IsNullOrEmpty(confirm))
        {
            problems.Add($"env {ConfirmEnv} is set without {ExecuteFlag} — unset it (a lost argument must not run anything)");
        }
        return problems;
    }

    /// <summary>The mode of arguments that <see cref="CheckFlags"/> accepted.</summary>
    public static BatchMode Mode(IReadOnlyList<string> args) =>
        args.Contains(ExecuteFlag, StringComparer.Ordinal) ? BatchMode.Execute
        : args.Contains(VerifyFlag, StringComparer.Ordinal) ? BatchMode.VerifyObservations
        : args.Contains(PreflightFlag, StringComparer.Ordinal) ? BatchMode.PreflightOnly
        : throw new InvalidOperationException("Mode() on arguments CheckFlags did not accept");

    /// <summary>
    /// Lines of the .env Config would load that mention BAR_BATCH_CONFIRM (any case): the confirmation is
    /// typed per run in the process environment, never stored in a file.
    /// </summary>
    public static IReadOnlyList<string> DotEnvConfirmProblems(string startDir)
    {
        var path = BoundedAgents.Experiments.LegacyBatchGuard.FindDotEnv(startDir);
        if (path is null)
        {
            return Array.Empty<string>();
        }
        var lines = File.ReadAllText(path).Split('\n');
        var problems = new List<string>();
        for (int i = 0; i < lines.Length; i++)
        {
            if (lines[i].Contains("BAR_BATCH_CONFIRM", StringComparison.OrdinalIgnoreCase))
            {
                problems.Add($"{path}:{i + 1} mentions {ConfirmEnv} — set it in the process for one run, not in .env");
            }
        }
        return problems;
    }

    /// <summary>
    /// The only path from the command line to a mode: refused flags → every problem and the usage on stderr,
    /// exit 2, <paramref name="run"/> not called; otherwise <paramref name="run"/>(pilot, mode).
    /// </summary>
    public static async Task<int> RunAsync(
        Func<string, string?> env, IReadOnlyList<string> args, Func<bool, BatchMode, Task<int>> run)
    {
        var problems = CheckFlags(env, args);
        if (problems.Count > 0)
        {
            return Refuse(problems);
        }
        return await run(IsPilot(args), Mode(args));
    }

    /// <summary>Prints the problems and the usage; exit code 2.</summary>
    public static int Refuse(IReadOnlyList<string> problems)
    {
        foreach (var p in problems)
        {
            Console.Error.WriteLine($"[batch] REFUSED: {p}");
        }
        Console.Error.WriteLine(Usage);
        return 2;
    }
}
