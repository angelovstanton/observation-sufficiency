using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;

// ---------------------------------------------------------------------------
// Helpers — shared by the main driver loop and the run modes.
// ---------------------------------------------------------------------------

internal static class Helpers
{
    public static bool SignalAbsentInBundle(IReadOnlyList<string> signalAttrs, string bundle)
    {
        if (signalAttrs.Count == 0)
        {
            return true;
        }

        return signalAttrs.All(attr => IsAttrAbsentInBundle(attr, bundle));
    }

    // Derive absence from the single authoritative bundle definition rather than
    // re-encoding membership here (attribute sets use OrdinalIgnoreCase).
    public static bool IsAttrAbsentInBundle(string attr, string bundle) =>
        !AttributeBundles.ResolveBundleSetForSignalCheck(bundle).Contains(attr);

    /// <summary>
    /// Routes a deployment name to the correct SDK path and endpoint.
    ///   gpt-*, o{1,3,4}-*  → AzureOpenAI       (Azure OpenAI Service)
    ///   claude-*            → AnthropicMessages  (Anthropic Messages API via Azure AI Services)
    ///   everything else     → AzureInference     (Azure AI Foundry serverless)
    /// </summary>
    public static (LlmClientType clientType, string endpoint) RouteModel(string deployment)
    {
        if (deployment.StartsWith("gpt-", StringComparison.OrdinalIgnoreCase) ||
            deployment.StartsWith("o1", StringComparison.OrdinalIgnoreCase) ||
            deployment.StartsWith("o3", StringComparison.OrdinalIgnoreCase) ||
            deployment.StartsWith("o4", StringComparison.OrdinalIgnoreCase))
        {
            return (LlmClientType.AzureOpenAI, Config.AzureOpenAiEndpoint);
        }

        if (deployment.StartsWith("claude-", StringComparison.OrdinalIgnoreCase))
        {
            return (LlmClientType.AnthropicMessages, Config.AzureAnthropicEndpoint);
        }

        return (LlmClientType.AzureInference, Config.AzureInferenceEndpoint);
    }

    public static string TruncateEndpoint(string ep) =>
        ep.Length > 60 ? ep[..57] + "…" : ep;

    public static string Truncate(string s, int max) =>
        s.Length > max ? s[..max] + "…" : s;

    public static string FindRepoRoot(string start)
    {
        var dir = new DirectoryInfo(start);
        while (dir is not null)
        {
            if (File.Exists(Path.Combine(dir.FullName, "ObservationSufficiency.slnx")) ||
                File.Exists(Path.Combine(dir.FullName, "ObservationSufficiency.sln")))
            {
                return dir.FullName;
            }

            dir = dir.Parent!;
        }
        throw new DirectoryNotFoundException("Could not locate repo root (ObservationSufficiency.slnx not found).");
    }

    public static string FormatDuration(TimeSpan ts) =>
        ts.TotalHours >= 1
            ? $"{(int)ts.TotalHours}h{ts.Minutes:00}m"
            : $"{(int)ts.TotalMinutes}m";

    // ------------------------------------------------------------------------
    // LoadDoneSet — reads completed (bundle, encoding, task_id, rep) tuples from
    // an existing axisc_*.jsonl output file. Returns empty set if file is absent.
    // ------------------------------------------------------------------------
    public static HashSet<(string Bundle, string Encoding, string TaskId, int Rep)> LoadDoneSet(string outFile)
    {
        var set = new HashSet<(string, string, string, int)>();
        if (!File.Exists(outFile))
        {
            return set;
        }

        foreach (var line in File.ReadAllLines(outFile))
        {
            if (string.IsNullOrWhiteSpace(line))
            {
                continue;
            }

            try
            {
                using var doc = JsonDocument.Parse(line);
                var r = doc.RootElement;
                set.Add((
                    r.GetProperty("bundle").GetString()!,
                    r.GetProperty("encoding").GetString()!,
                    r.GetProperty("task_id").GetString()!,
                    r.GetProperty("repetition").GetInt32()
                ));
            }
            catch { /* skip malformed lines */ }
        }
        return set;
    }
}
