using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;
using BoundedAgents.Shared.Tokenizer;
using BoundedAgents.Experiments;
using Microsoft.Playwright;

namespace BoundedAgents.Experiments.Batch;

/// <summary>
/// Pilot executor. Each event loads the site's May page offline with the adapter's loader
/// (experiments/RealPilotOffline.cs: cached HTML fulfilled, everything else aborted, shims on, clock at the
/// record's timestamp), sets every target marker by XPath as the observation dump did, then runs the
/// steps of GroundingRunner.RunOneStagedAsync in the same order. Resolution only.
/// A locator is never scored on the page its observation came from, nor on a page kept open: every
/// evaluation (Execute, Rescore, reuse) is <see cref="ScoreOnFreshLoadAsync"/> on a new fresh load with the
/// page clock paused, inside a mutation window (real_pilot/pilot_addendum_scoring.md (а), _a2.md (а′),
/// _a3.md (а″), _a4.md (а‴)). At most one browser context is open at a time.
/// </summary>
public sealed class PilotBatchExecutor : IBatchExecutor, IScoringReport
{
    private readonly PilotPlan _p;
    private readonly int _seed;
    private readonly Dictionary<string, byte[]> _html = new(StringComparer.Ordinal);
    private IPlaywright? _pw;
    private IBrowser? _browser;
    private int _openContexts;

    public PilotBatchExecutor(PilotPlan p)
    {
        _p = p;
        _seed = Config.RandomSeed;
    }

    /// <summary>Fresh offline loads made so far (observation and scoring).</summary>
    public int Loads { get; private set; }

    /// <summary>Warm-up loads (one after every browser start; not counted in <see cref="Loads"/>).</summary>
    public int WarmUpLoads { get; private set; }

    /// <summary>Browser contexts open now.</summary>
    public int OpenContexts => _openContexts;

    /// <summary>The most browser contexts ever open at the same time (must stay 1).</summary>
    public int MaxOpenContexts { get; private set; }

    public async Task<GroundingRecord> ExecuteAsync(
        PlanEvent e, string deployment, Func<string, string, Task<LlmResponse>> callModel)
    {
        var info = _p.Info[e.Key];
        var site = info.Site;
        var t = info.Target;
        var timestamp = DateTimeOffset.UtcNow.ToString("O");
        string obsText;
        var (ctx, _, text, _) = await ObserveAsync(site, e.Bundle, e.Encoding);
        try
        {
            obsText = text;
        }
        finally
        {
            // The observation's page is closed before the model is called: it is never scored.
            await CloseAsync(ctx);
        }

        int observationTokens = TokenCounter.CountTokens(obsText);
        var userPrompt = GroundingRunner.BuildUserPrompt(obsText, t.Task);
        var llmResp = await callModel(obsText, userPrompt);
        var s = await ScoreOnFreshLoadAsync(e, llmResp.Content);

        return new GroundingRecord(
            RunId: Guid.NewGuid().ToString(), TaskId: e.TaskId, Page: e.Page, Bundle: e.Bundle,
            Encoding: e.Encoding, Regime: "full_page", Model: deployment, Repetition: e.Repetition,
            ObservationTokens: observationTokens, PromptTokensTotal: llmResp.PromptTokens,
            CompletionTokens: llmResp.CompletionTokens, LocatorRaw: llmResp.Content,
            LocatorType: s.LocatorType, LocatorValue: s.LocatorValue, Success: s.Success,
            FailureMode: s.FailureMode, PredicateUniqueMatch: s.PredicateUniqueMatch,
            PredicateMatchesOracle: s.PredicateMatchesOracle, PredicateNonVolatile: s.PredicateNonVolatile,
            PredicateNonPositional: s.PredicateNonPositional,
            StableSignalPresentInBundle: s.StableSignalPresentInBundle, ModelIdReturned: llmResp.ModelId,
            TokenizerVersion: TokenCounter.TokenizerVersion(), SchemaVersion: GroundingRunner.SchemaVersion,
            TestbedPage: e.Page, TimestampUtc: timestamp, Seed: _seed);
    }

    public Task<BatchScore> RescoreAsync(PlanEvent e, string locatorRaw) => ScoreOnFreshLoadAsync(e, locatorRaw);

    /// <summary>The scoring checkpoint of the latest evaluation (Execute, Rescore or reuse): attempts, window counts, ms.</summary>
    public ScoringResult? LastScoring { get; private set; }

    /// <summary>
    /// The scoring checkpoint (real_pilot/pilot_addendum_scoring_a2.md (а′)): a fresh load of the cell
    /// (<see cref="ObserveAsync"/>) with the mutation window opened after the markers and before the first walk;
    /// observation sha256 == pinned; the Oracle evaluation immediately; then, synchronously, the window's count must
    /// be 0. Otherwise new loads, at most <see cref="ScoringCheckpoint.MaxLoads"/> in all, then a refusal (exit 3).
    /// </summary>
    private async Task<BatchScore> ScoreOnFreshLoadAsync(PlanEvent e, string locatorRaw)
    {
        var info = _p.Info[e.Key];
        var site = info.Site;
        var t = info.Target;
        var pinned = _p.ObservationSha[(e.Page, e.Bundle, e.Encoding)];
        LastScoring = null;
        var result = await ScoringCheckpoint.RunAsync(e.Key, pinned, async () =>
        {
            var clock = System.Diagnostics.Stopwatch.StartNew();
            var (ctx, page, obsText, raw) = await ObserveAsync(site, e.Bundle, e.Encoding, scoring: true);
            try
            {
                var before = Hashing.Sha256Hex(obsText);
                BatchScore? score = null;
                if (before == pinned)
                {
                    // Same calls, in the same order, as GroundingRunner.RunOneStagedAsync after the model call.
                    var bundleSet = AttributeBundles.ResolveBundleSetForSignalCheck(e.Bundle);
                    var (locatorType, locatorValue) = GroundingRunner.ParseLocatorForReplay(locatorRaw);
                    var oracleRef = new OracleRef(t.Marker);
                    var oracleEl = await Oracle.FindOracleElementAsync(page, oracleRef);
                    var ev = await Oracle.EvaluateLocatorAsync(
                        page, locatorType, locatorValue, oracleEl,
                        raw, oracleRef.OracleId, attr => bundleSet.Contains(attr),
                        null, site.VolIds, site.VolClasses, t.SignalAttrs);
                    score = new BatchScore(before, TokenCounter.CountTokens(obsText), locatorType, locatorValue,
                        ev.Success, ev.FailureMode, ev.PredicateUniqueMatch, ev.PredicateMatchesOracle,
                        ev.PredicateNonVolatile, ev.PredicateNonPositional, ev.StableSignalPresentInBundle);
                }
                var mutations = await MutationWindow.CloseAsync(page);
                return new ScoringAttempt(before, mutations, score, clock.ElapsedMilliseconds);
            }
            finally
            {
                await CloseAsync(ctx);
            }
        });
        LastScoring = result;
        return result.Score;
    }

    /// <summary>
    /// The run path's observation of one cell — the only way this executor builds one: a fresh
    /// offline load, every marker of the site, then this cell's observation as the first walk of
    /// that load. ExecuteAsync, the scoring checkpoint and verify-observations all go through here, so the
    /// verification checks exactly what the paid run will send. The caller closes it (<see cref="CloseAsync"/>).
    /// </summary>
    private async Task<(IBrowserContext Ctx, IPage Page, string ObsText, IReadOnlyList<ElementData> Raw)> ObserveAsync(
        PilotSite site, string bundle, string encoding, bool scoring = false)
    {
        if (!_html.TryGetValue(site.Key, out var body))
        {
            body = await File.ReadAllBytesAsync(site.HtmlPath);
            if (Hashing.Sha256Hex(body) != site.HtmlSha256)
            {
                throw new BatchRefusedException($"{site.HtmlPath}: sha256 != pinned {site.HtmlSha256}");
            }
            _html[site.Key] = body;
        }
        _pw ??= await Playwright.CreateAsync();
        var markers = _p.TargetsBySite[site.Key];
        if (_browser is null)
        {
            // Addendum (а″): after every browser start, one warm-up load of this cell — not evaluated, not recorded.
            _browser = await RealPilotOffline.LaunchAsync(_pw);
            WarmUpLoads++;
            var (wctx, _, _, _, _, _) = await RealPilotOffline.ObserveCellAsync(
                _browser, site.Url, body, site.Timestamp, _p.ShimJs, markers.Select(m => (m.Marker, m.Xpath)),
                bundle, encoding, site.VolIds, site.VolClasses);
            await wctx.CloseAsync();
        }
        Loads++;
        var (ctx, page, _, _, obsText, rawWithAnchors) = await RealPilotOffline.ObserveCellAsync(
            _browser, site.Url, body, site.Timestamp, _p.ShimJs, markers.Select(m => (m.Marker, m.Xpath)),
            bundle, encoding, site.VolIds, site.VolClasses,
            (stats, set) =>
            {
                if (stats.Fulfilled != 1 || set != markers.Count)
                {
                    throw new BatchRefusedException(
                        $"{site.Key}: offline load fulfilled {stats.Fulfilled}/1, markers set {set}/{markers.Count}");
                }
            },
            // Scoring loads only (addenda (а‴), (а′)): page clock paused at its current time, then the mutation window
            // opened — both after the markers and before the first walk. The observation path does neither.
            scoring
                ? async page =>
                {
                    await RealPilotOffline.PauseClockAsync(page, site.Timestamp);
                    await MutationWindow.OpenAsync(page);
                }
                : null);
        _openContexts++;
        MaxOpenContexts = Math.Max(MaxOpenContexts, _openContexts);
        return (ctx, page, obsText, rawWithAnchors);
    }

    private async Task CloseAsync(IBrowserContext ctx)
    {
        _openContexts--;
        await ctx.CloseAsync();
    }

    /// <summary>
    /// Zero-LLM (verify-observations): the cell's observation by the run path (<see cref="ObserveAsync"/>),
    /// and, for B_full, condition 5 of every target of the site on that load (as the dump computed it).
    /// </summary>
    public async Task<(string ObsText, IReadOnlyDictionary<string, bool>? Cond5)> ObserveCellAsync(PlanEvent e)
    {
        var site = _p.Info[e.Key].Site;
        var (ctx, _, obsText, raw) = await ObserveAsync(site, e.Bundle, e.Encoding);
        try
        {
            if (e.Bundle != "B_full")
            {
                return (obsText, null);
            }
            var fullSet = AttributeBundles.ResolveBundleSetForSignalCheck("B_full");
            var cond5 = new Dictionary<string, bool>(StringComparer.Ordinal);
            foreach (var t in _p.TargetsBySite[site.Key])
            {
                var el = raw.FirstOrDefault(x => x.Attrs.TryGetValue("data-oracle-id", out var v) && v == t.Marker);
                cond5[t.Marker] = el is not null && Oracle.ComputeStableSignalPresence(
                    t.SignalAttrs, a => fullSet.Contains(a), el, site.VolIds, site.VolClasses);
            }
            return (obsText, cond5);
        }
        finally
        {
            await CloseAsync(ctx);
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_browser is not null)
        {
            try { await _browser.CloseAsync(); } catch { }
        }
        _pw?.Dispose();
    }
}

/// <summary>
/// One scoring attempt: observation sha256 of the first walk, the mutation window's count (from the first walk to the
/// end of the evaluation), the score (null: not evaluated, the pre-hash differed) and ms from the start of the load to
/// the end of the evaluation.
/// </summary>
public sealed record ScoringAttempt(string BeforeSha256, int Mutations, BatchScore? Score, long Ms);

/// <summary>The accepted evaluation and how it was reached (recorded in pilot records; addendum (а′) point 4).</summary>
public sealed record ScoringResult(BatchScore Score, int Attempts, IReadOnlyList<int> Mutations, long Ms);

/// <summary>
/// Retry rule of the scoring checkpoint (real_pilot/pilot_addendum_scoring_a2.md (а′), _a3.md (а″)): an attempt counts
/// only if the observation sha256 equals the pinned one and the mutation window counted 0; otherwise a new fresh load,
/// at most <see cref="MaxLoads"/> loads in all. If none counts: refusal (exit 3), no record.
/// </summary>
public static class ScoringCheckpoint
{
    public const int MaxLoads = 5;

    public static async Task<ScoringResult> RunAsync(string key, string pinnedSha256, Func<Task<ScoringAttempt>> attempt)
    {
        var seen = new List<string>();
        var counts = new List<int>();
        for (int n = 1; n <= MaxLoads; n++)
        {
            var a = await attempt();
            counts.Add(a.Mutations);
            if (a.BeforeSha256 == pinnedSha256 && a.Mutations == 0 && a.Score is not null)
            {
                return new ScoringResult(a.Score, n, counts, a.Ms);
            }
            seen.Add($"load {n}: observation {Short(a.BeforeSha256)}, {a.Mutations} mutation(s) in the window");
        }
        throw new BatchRefusedException(
            $"{key}: scoring checkpoint failed on {MaxLoads} fresh loads (pinned observation {Short(pinnedSha256)}: " +
            $"{string.Join("; ", seen)}) — not scored, no record written");
    }

    private static string Short(string? sha) => sha is null ? "-" : sha[..Math.Min(12, sha.Length)] + "…";
}
