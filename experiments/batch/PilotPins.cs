namespace BoundedAgents.Experiments.Batch;

/// <summary>
/// The real-site pilot's apparatus, pinned (selected only with <c>--plan pilot</c>). Every value is
/// checked by <see cref="PilotPreflight"/> before the first paid call; a mismatch refuses the run.
/// Pinned files (re-dump with a fresh load per cell): real_pilot/pilot_plan.json and
/// pilot_reuse_map.json (04ec3f0), targets.json and observations_manifest.tsv (83cdb27), pilot_sites.json
/// (7a61d6b). Cap rule: pilot_analysis_plan.md addendum 9f0bb2b (final figures: addendum of 4bcc9e8).
/// </summary>
public static class PilotPins
{
    public const string PlanSha256 = "b79364225b5e3a025067c87c89218beb60c3790c7ced58f247d098961f209a90";
    public const string ReuseMapSha256 = "41fddd0efcbe0e92acdff9343396e8e326735b384673c30a8b8d30c14f9c0364";
    public const string TargetsSha256 = "e890544fcfd19789f0587e564b17e9ebb62d7877f3ad99b4d8a3070e7b243fec";
    public const string ObservationsManifestSha256 = "4e7db7882daf0adffe6564ddf5bfe0f33a08590f0ee1c4d59768e7cc67512a50";
    public const string SitesSha256 = "15ab318758d54d820bd611628dc4c6efaf5378e5286624a5d388176444b4d0ba";

    /// <summary>rp_shim_random.js, hashed with CRLF normalised to LF (it has no -text attribute).</summary>
    public const string ShimSha256 = "33094c7070ab0d19172b50e760ae830c1ad6d49ddd01d7e292af4faac5c889f7";

    /// <summary>1,476 called events; Σ o200k input tokens (CountTokens(SystemPrompt) + CountTokens(user)).</summary>
    public const int PlannedCalls = 1476;
    public const long PlannedInputTokens = 50_435_050;
    /// <summary>class_only cells not called (observation byte-identical to B_noVolatile).</summary>
    public const int ReusedCount = 480;

    /// <summary>Sites of pilot_sites.json (= the plan's pages) and their targets in targets.json.</summary>
    public const int SiteCount = 33;
    public const int TargetCount = 326;

    /// <summary>Hard cap USD 114.34 (rule of addendum 9f0bb2b: upper bound + 10%), in µUSD; list price gpt-4.1 $2.00 / $8.00 per 1M tokens.</summary>
    public const long CapMicroUsd = 114_340_000;
    public const long InputMicroUsdPerToken = 2;
    public const long OutputMicroUsdPerToken = 8;

    /// <summary>
    /// Completion tokens reserved per call = the limit the request sends for gpt-4.1: LlmClient.MaxTokens
    /// (256), passed as MaxOutputTokenCount by LlmClientDetailed unless IsReasoningModel (false for gpt-4.1).
    /// </summary>
    public const int MaxCompletionTokens = 256;

    public static readonly IReadOnlyDictionary<string, string> ModelEnv = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["gpt-4.1"] = "BAR_MODEL_DEPLOYMENT_1",
    };

    /// <summary>(bundle, encoding) → called events.</summary>
    public static readonly IReadOnlyDictionary<(string Bundle, string Encoding), int> AllowedCells =
        new Dictionary<(string, string), int>
        {
            [("B_full", "F1")] = 326,
            [("B_noVolatileConsistent", "F1")] = 326,
            [("B_full_minus_volClass", "F1")] = 86,
            [("B_full", "F3")] = 326,
            [("B_noVolatileConsistent", "F3")] = 326,
            [("B_full_minus_volClass", "F3")] = 86,
        };

    public static PilotOptions Production(string repoRoot)
    {
        var rp = Path.Combine(repoRoot, "experiments", "results", "revision1", "real_pilot");
        return new PilotOptions
        {
            RepoRoot = repoRoot,
            PlanPath = Path.Combine(rp, "pilot_plan.json"),
            ExpectedPlanSha256 = PlanSha256,
            ReuseMapPath = Path.Combine(rp, "pilot_reuse_map.json"),
            ExpectedReuseMapSha256 = ReuseMapSha256,
            TargetsPath = Path.Combine(rp, "targets.json"),
            ExpectedTargetsSha256 = TargetsSha256,
            ManifestPath = Path.Combine(rp, "observations_manifest.tsv"),
            ExpectedManifestSha256 = ObservationsManifestSha256,
            SitesPath = Path.Combine(rp, "pilot_sites.json"),
            ExpectedSitesSha256 = SitesSha256,
            ShimPath = Path.Combine(rp, "rp_shim_random.js"),
            ExpectedShimSha256 = ShimSha256,
            HtmlDir = Path.GetFullPath(Path.Combine(repoRoot, "..", "_external", "cc_cache", "real_pilot", "html",
                                                    "CC-MAIN-2026-21")),
            ExpectedPromptDigest = BatchPins.PromptDigestSha256,
            OutDir = Path.Combine(repoRoot, "experiments", "results", "revision1", "batch_runs_pilot"),
            AllowedCells = AllowedCells,
            ModelEnv = ModelEnv,
            PlannedCalls = PlannedCalls,
            PlannedInputTokens = PlannedInputTokens,
            ReusedCount = ReusedCount,
            SiteCount = SiteCount,
            TargetCount = TargetCount,
            CapMicroUsd = CapMicroUsd,
            InputMicroUsdPerToken = InputMicroUsdPerToken,
            OutputMicroUsdPerToken = OutputMicroUsdPerToken,
            MaxCompletionTokens = MaxCompletionTokens,
            Env = Environment.GetEnvironmentVariable,
        };
    }
}
