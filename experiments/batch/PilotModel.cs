namespace BoundedAgents.Experiments.Batch;

/// <summary>Everything the pilot profile needs; <see cref="PilotPins.Production"/> builds the pinned one.</summary>
public sealed record PilotOptions
{
    public required string RepoRoot { get; init; }
    public required string PlanPath { get; init; }
    public required string ExpectedPlanSha256 { get; init; }
    public required string ReuseMapPath { get; init; }
    public required string ExpectedReuseMapSha256 { get; init; }
    public required string TargetsPath { get; init; }
    public required string ExpectedTargetsSha256 { get; init; }
    public required string ManifestPath { get; init; }
    public required string ExpectedManifestSha256 { get; init; }
    public required string SitesPath { get; init; }
    public required string ExpectedSitesSha256 { get; init; }
    public required string ShimPath { get; init; }
    public required string ExpectedShimSha256 { get; init; }
    /// <summary>Directory of the decoded May HTML files named in pilot_sites.json (outside the repo).</summary>
    public required string HtmlDir { get; init; }
    public required string ExpectedPromptDigest { get; init; }
    public required string OutDir { get; init; }
    public required IReadOnlyDictionary<(string Bundle, string Encoding), int> AllowedCells { get; init; }
    public required IReadOnlyDictionary<string, string> ModelEnv { get; init; }
    public required int PlannedCalls { get; init; }
    public required long PlannedInputTokens { get; init; }
    public required int ReusedCount { get; init; }
    public required int SiteCount { get; init; }
    public required int TargetCount { get; init; }
    public required long CapMicroUsd { get; init; }
    public required long InputMicroUsdPerToken { get; init; }
    public required long OutputMicroUsdPerToken { get; init; }
    public required int MaxCompletionTokens { get; init; }
    public required Func<string, string?> Env { get; init; }
    public int MaxAttempts { get; init; } = 4;
}

/// <summary>One site of pilot_sites.json: what the offline loader is given.</summary>
public sealed record PilotSite(
    string Key, int Rank, string Domain, string Url, DateTime Timestamp, string HtmlPath, string HtmlSha256,
    IReadOnlySet<string> VolIds, IReadOnlySet<string> VolClasses);

/// <summary>One target of targets.json (the oracle marker is set on the element its XPath selects).</summary>
public sealed record PilotTarget(
    string Domain, int Rank, string Marker, string Xpath, string Task, string Stratum,
    IReadOnlyList<string> SignalAttrs, string Sha256Key);

/// <summary>A pilot event (called or reused) with its site and target.</summary>
public sealed record PilotEventInfo(PlanEvent Event, string Cell, PilotSite Site, PilotTarget Target, int InputTokens);

/// <summary>Outcome of a passed pilot preflight.</summary>
public sealed class PilotPlan
{
    /// <summary>Called events, in plan order (Tranco rank, target, encoding, cell).</summary>
    public required IReadOnlyList<PlanEvent> Events { get; init; }
    public required IReadOnlyDictionary<string, ReusedEvent> Reused { get; init; }
    /// <summary>Called and reused events by key.</summary>
    public required IReadOnlyDictionary<string, PilotEventInfo> Info { get; init; }
    /// <summary>Sites by key (the plan's page), in Tranco order.</summary>
    public required IReadOnlyList<PilotSite> Sites { get; init; }
    /// <summary>All targets of each site (every marker is set, as in the observation dump).</summary>
    public required IReadOnlyDictionary<string, IReadOnlyList<PilotTarget>> TargetsBySite { get; init; }
    public required IReadOnlyDictionary<(string Page, string Bundle, string Encoding), string> ObservationSha { get; init; }
    public required IReadOnlyDictionary<(string Page, string Bundle, string Encoding), int> ObservationTokens { get; init; }
    public required IReadOnlyDictionary<string, string> Deployments { get; init; }
    public required string ShimJs { get; init; }
    public required long PlannedInputTokens { get; init; }
    public required BatchExpectations Expectations { get; init; }
    public required BudgetModel Budget { get; init; }

    public PilotSite SiteOf(string page) => Sites.First(s => s.Key == page);
}
