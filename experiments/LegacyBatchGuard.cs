using DotNetEnv;

namespace BoundedAgents.Experiments;

/// <summary>
/// .env checks shared by the legacy entrypoint (experiments/Program.cs) and the batch executable
/// (experiments/batch/Program.cs). The file is read with the parser that actually loads it (DotNetEnv,
/// same options as shared/harness/Config, but nothing is written to the process environment) and
/// then scanned line by line, fail-closed:
///   - any line mentioning REVISION_BATCH (any case, any syntax, even commented) refuses;
///   - a line mentioning BAR_BATCH refuses unless the parser gave a non-empty value to a key
///     that appears on that line;
///   - a file the parser cannot read refuses.
/// Also compiled into Experiments.Batch, so the tests cover the one implementation.
/// </summary>
public static class LegacyBatchGuard
{
    public const string Flag = "REVISION_BATCH";

    /// <summary>Config loads with setEnvVars: true; everything else is identical.</summary>
    public static LoadOptions ReadOnlyOptions() => new(setEnvVars: false, clobberExistingVars: false);

    /// <summary>Legacy entrypoint: null when it may continue; otherwise why it must not.</summary>
    public static string? RefuseReason(Func<string, string?> env, IReadOnlyList<string> args, string startDir)
    {
        if (!string.IsNullOrEmpty(env(Flag)))
        {
            return $"{Flag} is set in the process environment";
        }
        if (args.Contains("--revision-batch"))
        {
            return "--revision-batch was passed";
        }
        return DotEnvProblems(startDir).FirstOrDefault();
    }

    /// <summary>Problems in the .env Config would load from <paramref name="startDir"/>; empty if none.</summary>
    public static IReadOnlyList<string> DotEnvProblems(string startDir)
    {
        var path = FindDotEnv(startDir);
        if (path is null)
        {
            return Array.Empty<string>();
        }

        Dictionary<string, List<string>> parsed;
        try
        {
            parsed = ReadDotEnv(path);
        }
        catch (Exception ex)
        {
            return new[] { $"{path} cannot be parsed by DotNetEnv ({ex.GetType().Name}: {ex.Message.Split('\n')[0]})" };
        }

        var problems = new List<string>();
        var lines = File.ReadAllText(path).Split('\n');          // ReadAllText drops a BOM
        for (int i = 0; i < lines.Length; i++)
        {
            var line = lines[i].TrimEnd('\r');
            if (line.Contains(Flag, StringComparison.OrdinalIgnoreCase))
            {
                problems.Add($"{path}:{i + 1} mentions {Flag} — the batch runs only via experiments/batch");
            }
            else if (line.Contains("BAR_BATCH", StringComparison.OrdinalIgnoreCase))
            {
                var recognised = parsed.Any(kv =>
                    kv.Key.Contains("BAR_BATCH", StringComparison.OrdinalIgnoreCase)
                    && line.Contains(kv.Key, StringComparison.Ordinal)
                    && kv.Value.Any(v => v.Length > 0));
                if (!recognised)
                {
                    problems.Add($"{path}:{i + 1} mentions BAR_BATCH but DotNetEnv does not set it — refusing");
                }
            }
        }
        return problems;
    }

    /// <summary>Every key → values the parser produced (in file order), without touching the environment.</summary>
    public static Dictionary<string, List<string>> ReadDotEnv(string path)
    {
        var d = new Dictionary<string, List<string>>(StringComparer.Ordinal);
        foreach (var kv in Env.Load(path, ReadOnlyOptions()))
        {
            if (!d.TryGetValue(kv.Key, out var list))
            {
                d[kv.Key] = list = new List<string>();
            }
            list.Add(kv.Value);
        }
        return d;
    }

    /// <summary>The .env Config would load: the first one walking up from <paramref name="startDir"/>
    /// (same search as Config.FindEnvFile; a test pins the equality).</summary>
    public static string? FindDotEnv(string startDir)
    {
        var dir = new DirectoryInfo(startDir);
        while (dir is not null)
        {
            var candidate = Path.Combine(dir.FullName, ".env");
            if (File.Exists(candidate))
            {
                return candidate;
            }
            dir = dir.Parent;
        }
        return null;
    }
}
