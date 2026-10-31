using BoundedAgents.Shared.Harness;

namespace BoundedAgents.Experiments.Batch;

/// <summary>
/// The batch apparatus, pinned. Every value is checked by the preflight before the first paid
/// call; a mismatch refuses the run. Changing a pin means a new plan, not a code fix.
/// </summary>
public static class BatchPins
{
    /// <summary>batch_plan.json (4 500 events).</summary>
    public const string PlanSha256 = "567c370855a29bf641a8d809a73fb433f217207b087fc62cb2c61ec70402353f";

    /// <summary>experiments/results/revision1/batch_observations/manifest.tsv (360 rows).</summary>
    public const string BatchObservationsManifestSha256 = "978778abea1f0d1e390cb48802c0a54652aa19f7065b3b7d006d9557ca8f78c0";

    /// <summary>experiments/results/revision1/observations/manifest.tsv (216 rows; holds NV×F3).</summary>
    public const string ObservationsManifestSha256 = "0afcebb2ec6d5b88ae618ef5a679967df0ebc14e22ac962fa94e7ab3904e1797";

    /// <summary>shared/testbed/pages/* (24 html + 24 truth.json), see <see cref="PagesDigest"/>.</summary>
    public const string PagesDigestSha256 = "9d75245edfd4769d6762e9b58f8ab63af7c653f4e19fbd067e15a3144d832d4e";

    /// <summary>Canonical SystemPrompt + user prompt template, see <see cref="PromptDigest"/>.</summary>
    public const string PromptDigestSha256 = "b5fff73a57a20c0fff1d8942a0629fa31f8e79f291017e2396751f4d21de1251";

    /// <summary>Model → deployment env slot the plan uses (o4-mini is slot 4, not 3).</summary>
    public static readonly IReadOnlyDictionary<string, string> ModelEnv = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["gpt-4.1"] = "BAR_MODEL_DEPLOYMENT_1",
        ["gpt-4.1-nano"] = "BAR_MODEL_DEPLOYMENT_2",
        ["o4-mini"] = "BAR_MODEL_DEPLOYMENT_4",
    };

    /// <summary>The 19 planned cells and their event counts; total 4 500.</summary>
    public static readonly IReadOnlyDictionary<PlanCell, int> AllowedCells = new Dictionary<PlanCell, int>
    {
        [new("1", "gpt-4.1", "B_full_minus_volClass", "F1", 1)] = 200,
        [new("1", "gpt-4.1", "B_full_minus_volId", "F1", 1)] = 220,
        [new("1", "gpt-4.1", "B_full_minus_aria", "F1", 1)] = 240,
        [new("2", "gpt-4.1", "B_full", "F2L", 1)] = 240,
        [new("2", "gpt-4.1", "B_noVolatile", "F2L", 1)] = 240,
        [new("2", "gpt-4.1-nano", "B_noVolatile", "F2L", 1)] = 240,
        [new("3", "gpt-4.1", "B_full", "F1", 2)] = 240,
        [new("3", "gpt-4.1", "B_full", "F1", 3)] = 240,
        [new("3", "gpt-4.1", "B_noVolatile", "F1", 2)] = 240,
        [new("3", "gpt-4.1", "B_noVolatile", "F1", 3)] = 240,
        [new("3", "gpt-4.1", "B_noVolatile", "F2", 2)] = 240,
        [new("3", "gpt-4.1", "B_noVolatile", "F2", 3)] = 240,
        [new("3", "gpt-4.1", "B_noVolatile", "F3", 2)] = 240,
        [new("3", "gpt-4.1", "B_noVolatile", "F3", 3)] = 240,
        [new("3", "gpt-4.1-nano", "B_noVolatile", "F1", 2)] = 240,
        [new("3", "gpt-4.1-nano", "B_noVolatile", "F1", 3)] = 240,
        [new("3", "gpt-4.1-nano", "B_noVolatile", "F2", 2)] = 240,
        [new("3", "gpt-4.1-nano", "B_noVolatile", "F2", 3)] = 240,
        [new("4", "o4-mini", "B_full", "F1", 1)] = 240,
    };

    /// <summary>
    /// sha256 over the sorted lines "name\tsha256(file)\n" of shared/testbed/pages/*, each file
    /// hashed with CRLF normalised to LF (as git stores it), so the pin does not depend on the
    /// checkout's core.autocrlf. The HTML parser normalises newlines itself; the served bytes
    /// are covered separately by the per-event observation hash.
    /// </summary>
    public static string PagesDigest(string repoRoot)
    {
        var dir = Path.Combine(repoRoot, "shared", "testbed", "pages");
        var lines = Directory.GetFiles(dir)
            .Select(Path.GetFileName)
            .OrderBy(n => n, StringComparer.Ordinal)
            .Select(n => $"{n}\t{Hashing.Sha256Hex(NormaliseEol(File.ReadAllBytes(Path.Combine(dir, n!))))}\n");
        return Hashing.Sha256Hex(string.Concat(lines));
    }

    private static byte[] NormaliseEol(byte[] b)
    {
        var o = new List<byte>(b.Length);
        for (int i = 0; i < b.Length; i++)
        {
            if (b[i] == (byte)'\r' && i + 1 < b.Length && b[i + 1] == (byte)'\n')
            {
                continue;
            }
            o.Add(b[i]);
        }
        return o.ToArray();
    }

    /// <summary>sha256(SystemPrompt + "\n\0\n" + user prompt template with placeholders).</summary>
    public static string PromptDigest() =>
        Hashing.Sha256Hex(GroundingRunner.SystemPrompt + "\n\0\n"
                          + GroundingRunner.BuildUserPrompt("{observation}", "{task}"));

    public static BatchOptions Production(string repoRoot)
    {
        var rev1 = Path.Combine(repoRoot, "experiments", "results", "revision1");
        return new BatchOptions
        {
            RepoRoot = repoRoot,
            PlanPath = Path.Combine(rev1, "batch_plan.json"),
            ExpectedPlanSha256 = PlanSha256,
            OutDir = Path.Combine(rev1, "batch_runs"),
            AllowedCells = AllowedCells,
            ModelEnv = ModelEnv,
            ObservationManifests = new[]
            {
                (Path.Combine(rev1, "batch_observations", "manifest.tsv"), BatchObservationsManifestSha256),
                (Path.Combine(rev1, "observations", "manifest.tsv"), ObservationsManifestSha256),
            },
            ExpectedPagesDigest = PagesDigestSha256,
            ExpectedPromptDigest = PromptDigestSha256,
            Env = Environment.GetEnvironmentVariable,
        };
    }
}
