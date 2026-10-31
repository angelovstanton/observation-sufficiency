using BoundedAgents.Models;
using BoundedAgents.Experiments.Batch;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// The scoring checkpoint (real_pilot/pilot_addendum_scoring.md (а)) on the real pinned May page, through the
/// production PilotBatchExecutor and a fake model (no network, no LLM). wikipedia.org sets a &lt;body&gt; class from
/// a ~1 s timer, so an ancestor-state locator scored after the model's latency, or on an aged page, can flip between
/// evaluations; every evaluation must give the same result. Needs the decoded May HTML next to the repo
/// (PilotPins.HtmlDir); skipped if it is missing.
/// </summary>
[Trait("Category", "RealPilot")]
public sealed class PilotScoringTimingTests
{
    private const string Key = "gpt-4.1|B_full|F1|0031_wikipedia.org|t_03|0";
    private const string AncestorStateLocator = """css:body:not(.jsl10n-visible) [href="//ht.wikipedia.org/"]""";

    private static PilotPlan Plan()
    {
        var o = PilotPins.Production(Testbed.RepoRoot) with
        {
            Env = name => name == "BAR_MODEL_DEPLOYMENT_1" ? "gpt-4.1" : null,
        };
        Assert.True(Directory.Exists(o.HtmlDir), $"pinned May HTML missing: {o.HtmlDir} (copy the real_pilot cache next to the repo)");
        return PilotPreflight.Run(o);
    }

    public static TheoryData<int, int> Delays => new()
    {
        { 2_000, 1 }, { 2_000, 2 }, { 2_000, 3 },
        { 10_000, 1 },
        { 30_000, 1 },
    };

    [RealPilotTheory]
    [MemberData(nameof(Delays))]
    public async Task Execute_and_rescore_give_the_same_score_whatever_the_model_latency(int delayMs, int repeat)
    {
        var p = Plan();
        var e = p.Events.Single(x => x.Key == Key);
        TokenCounter.CountTokens("warm-up");

        await using var ex = new PilotBatchExecutor(p);
        var record = await ex.ExecuteAsync(e, "gpt-4.1", async (obs, _) =>
        {
            Assert.Equal(p.ObservationSha[(e.Page, e.Bundle, e.Encoding)], Hashing.Sha256Hex(obs));
            await Task.Delay(delayMs);
            return new LlmResponse(AncestorStateLocator, p.Info[e.Key].InputTokens, 0, "gpt-4.1");
        });
        var fresh = await ex.RescoreAsync(e, AncestorStateLocator);
        await Task.Delay(1_500);
        var aged = await ex.RescoreAsync(e, AncestorStateLocator);

        var executed = (record.Success, record.PredicateUniqueMatch, record.PredicateMatchesOracle, record.FailureMode);
        Assert.True(executed == (fresh.Success, fresh.PredicateUniqueMatch, fresh.PredicateMatchesOracle, fresh.FailureMode),
                    $"repeat {repeat}: execute {executed} != fresh rescore {fresh}");
        Assert.Equal(fresh, aged);
        Assert.Equal(1, ex.MaxOpenContexts);
        Assert.Equal(0, ex.OpenContexts);
        // Observation + three scorings, each on its own fresh load (+ checkpoint reloads, at most 3 per scoring).
        Assert.InRange(ex.Loads, 4, 1 + 3 * ScoringCheckpoint.MaxLoads);
    }
}

/// <summary>The retry rule of the scoring checkpoint, without a browser.</summary>
public sealed class ScoringCheckpointTests
{
    private const string Pinned = "aaaaaaaaaaaaaaaaaaaaaaaa";
    private static readonly BatchScore Score = new(Pinned, 1, "css", "#x", true, null, true, true, true, true, true);

    private static Func<Task<ScoringAttempt>> Script(List<ScoringAttempt> attempts, Counter n) => () =>
    {
        n.Value++;
        return Task.FromResult(attempts[n.Value - 1]);
    };

    private sealed class Counter { public int Value; }

    [Theory]
    [InlineData(1)]
    [InlineData(2)]
    [InlineData(3)]
    [InlineData(4)]
    [InlineData(5)]
    public async Task A_failed_attempt_is_retried_on_a_new_load_up_to_five_loads(int okOn)
    {
        // Failures alternate: the first walk differs from the pin (not scored), or the DOM moved in the window.
        var attempts = Enumerable.Range(1, ScoringCheckpoint.MaxLoads)
            .Select(i => i == okOn ? new ScoringAttempt(Pinned, 0, Score, 900)
                       : i % 2 == 1 ? new ScoringAttempt("bbbbbbbbbbbbbbbb", 0, null, 800)
                       : new ScoringAttempt(Pinned, 2, Score with { Success = false }, 1000))
            .ToList();
        var n = new Counter();
        var s = await ScoringCheckpoint.RunAsync("k", Pinned, Script(attempts, n));
        Assert.Equal(Score, s.Score);
        Assert.Equal(okOn, n.Value);
        Assert.Equal(okOn, s.Attempts);
        Assert.Equal(attempts.Take(okOn).Select(a => a.Mutations), s.Mutations);
        Assert.Equal(0, s.Mutations[^1]);
        Assert.Equal(900, s.Ms);
    }

    [Fact]
    public async Task Five_mismatching_loads_refuse_without_a_score()
    {
        var attempts = Enumerable.Range(0, ScoringCheckpoint.MaxLoads)
            .Select(i => new ScoringAttempt(Pinned, i == 0 ? -1 : 1, Score, 1000)).ToList();   // −1: window never opened
        var n = new Counter();
        var ex = await Assert.ThrowsAsync<BatchRefusedException>(() => ScoringCheckpoint.RunAsync("k", Pinned, Script(attempts, n)));
        Assert.Equal(5, n.Value);
        Assert.Contains("scoring checkpoint failed on 5 fresh loads", ex.Message);
        Assert.Contains("no record written", ex.Message);
    }
}
