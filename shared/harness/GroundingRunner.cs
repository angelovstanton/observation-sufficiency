using BoundedAgents.Models;
using BoundedAgents.Shared.Oracle;
using BoundedAgents.Shared.Tokenizer;
using Microsoft.Playwright;

namespace BoundedAgents.Shared.Harness;

// ---------------------------------------------------------------------------
// GroundingRunner
// ---------------------------------------------------------------------------

public static class GroundingRunner
{
    public const string SchemaVersion = "1.0";

    // Canonical system prompt — no strategy coaching (§6): no attribute hints,
    // no few-shot examples naming attributes, no failedSelectors retry channel.
    //
    // CSS-only output: Playwright's CSS engine pierces shadow DOM (XPath cannot).
    // XPath's main added power is axis/relational navigation, which is positional
    // and rejected by the non-positional predicate — so fixing to CSS removes an
    // uncontrolled variable without losing any predicate-valid success path.
    public const string SystemPrompt =
        "You are a web UI element locator. Given a structured observation of a web page " +
        "and a natural-language task, return a single locator that uniquely identifies " +
        "the target element.\n\n" +
        "Return ONLY the locator on one line, prefixed with 'css:'.\n" +
        "Format: css:<selector>\n" +
        "No explanation. No markdown. The locator only.";

    private static string UserPrompt(string observation, string taskDescription) =>
        $"Page observation:\n{observation}\n\nTask: {taskDescription}\n\nLocator:";

    private static (string type, string value) ParseLocator(string raw)
    {
        raw = raw.Trim();
        if (raw.StartsWith("xpath:", StringComparison.OrdinalIgnoreCase))
        {
            return ("xpath", raw["xpath:".Length..]);
        }

        if (raw.StartsWith("css:", StringComparison.OrdinalIgnoreCase))
        {
            return ("css", raw["css:".Length..]);
        }

        return ("css", raw); // output is CSS-only; treat any un-prefixed response as CSS
    }

    /// <summary>
    /// Re-evaluate a stored locator against the live DOM. Zero LLM calls.
    /// Accepts an already-open IPage (caller manages Playwright lifecycle).
    /// Observation is re-encoded to recompute token counts; no network call.
    /// </summary>
    public static async Task<GroundingRecord> ReplayOneAsync(
        IPage page,
        string taskId,
        OracleRef oracleRef,
        string pagePath,
        string bundle,
        string encoding,
        string locatorRaw,
        string? expectedStableSignal = null,
        IReadOnlySet<string>? volatileIds = null,
        IReadOnlySet<string>? volatileClasses = null,
        IReadOnlyList<string>? signalAttrs = null)
    {
        var runId = Guid.NewGuid().ToString();
        var timestamp = DateTimeOffset.UtcNow.ToString("O");

        string obsText;
        IReadOnlyList<ElementData> rawWithAnchors;

        if (encoding.Equals("F4", StringComparison.OrdinalIgnoreCase))
        {
            var (ariaYaml, raw, _) = await Observation.BuildAriaObservationAsync(page);
            obsText = ariaYaml;
            rawWithAnchors = raw;
        }
        else
        {
            (obsText, rawWithAnchors, _) = await Observation.BuildObservationAsync(
                page, bundle, encoding, volatileIds, volatileClasses);
        }

        var bundleSet = AttributeBundles.ResolveBundleSetForSignalCheck(bundle);

        int observationTokens = TokenCounter.CountTokens(obsText);

        var (locatorType, locatorValue) = ParseLocator(locatorRaw);
        var oracleEl = await Oracle.Oracle.FindOracleElementAsync(page, oracleRef);
        var evalResult = await Oracle.Oracle.EvaluateLocatorAsync(
            page, locatorType, locatorValue, oracleEl,
            rawWithAnchors, oracleRef.OracleId, attr => bundleSet.Contains(attr),
            expectedStableSignal, volatileIds, volatileClasses, signalAttrs);

        return new GroundingRecord(
            RunId: runId,
            TaskId: taskId,
            Page: pagePath,
            Bundle: bundle,
            Encoding: encoding,
            Regime: "replay",
            Model: "replay",
            Repetition: 0,
            ObservationTokens: observationTokens,
            PromptTokensTotal: 0,
            CompletionTokens: 0,
            LocatorRaw: locatorRaw,
            LocatorType: locatorType,
            LocatorValue: locatorValue,
            Success: evalResult.Success,
            FailureMode: evalResult.FailureMode,
            PredicateUniqueMatch: evalResult.PredicateUniqueMatch,
            PredicateMatchesOracle: evalResult.PredicateMatchesOracle,
            PredicateNonVolatile: evalResult.PredicateNonVolatile,
            PredicateNonPositional: evalResult.PredicateNonPositional,
            StableSignalPresentInBundle: evalResult.StableSignalPresentInBundle,
            ModelIdReturned: "replay",
            TokenizerVersion: TokenCounter.TokenizerVersion(),
            SchemaVersion: SchemaVersion,
            TestbedPage: pagePath,
            TimestampUtc: timestamp,
            Seed: 0
        );
    }

    /// <summary>
    /// Execute one grounding event and return a complete GroundingRecord.
    /// Maps to: task × bundle × encoding × regime × model × repetition → JSONL record (§6).
    /// </summary>
    public static async Task<GroundingRecord> RunOneAsync(
        string taskId,
        string taskDescription,
        OracleRef oracleRef,
        string pagePath,
        string bundle,
        string encoding,
        string regime,
        string model,
        string endpoint,
        LlmClientType clientType,
        int repetition,
        string? expectedStableSignal = null,
        IReadOnlySet<string>? volatileIds = null,
        IReadOnlySet<string>? volatileClasses = null,
        IReadOnlyList<string>? signalAttrs = null,
        int? seed = null)
    {
        seed ??= Config.RandomSeed;
        var baseUrl = Config.TestbedBaseUrl.TrimEnd('/');
        var pageUrl = $"{baseUrl}/{pagePath}";
        var runId = Guid.NewGuid().ToString();
        var timestamp = DateTimeOffset.UtcNow.ToString("O");

        using var playwright = await Playwright.CreateAsync();
        var browser = await playwright.Chromium.LaunchAsync(new() { Headless = true });
        try
        {
            var page = await browser.NewPageAsync();
            // 90 s budget: page_08 F2 hit the default 30 s limit on the prior run;
            // data was correct once the server restarted, the gate was just too tight.
            await page.GotoAsync(pageUrl, new() { Timeout = 90_000 });
            await page.WaitForLoadStateAsync(LoadState.NetworkIdle, new() { Timeout = 90_000 });

            // D → O: two paths — ARIA snapshot (F4/B_playwrightMCP) or DOM walk (F0–F3)
            string obsText;
            IReadOnlyList<ElementData> rawWithAnchors;
            IReadOnlyList<ElementData> filtered;

            if (encoding.Equals("F4", StringComparison.OrdinalIgnoreCase))
            {
                var (ariaYaml, raw, leak) = await Observation.BuildAriaObservationAsync(page);
                obsText = ariaYaml;
                rawWithAnchors = raw;
                filtered = Array.Empty<ElementData>();
                if (leak)
                {
                    Console.Error.WriteLine($"[WARN] F4 oracle leak detected on {taskId}");
                }
            }
            else
            {
                // rawWithAnchors retains data-oracle-* for oracle evaluation
                (obsText, rawWithAnchors, filtered) = await Observation.BuildObservationAsync(
                    page, bundle, encoding, volatileIds, volatileClasses);
            }

            var bundleSet = AttributeBundles.ResolveBundleSetForSignalCheck(bundle);

            int observationTokens = TokenCounter.CountTokens(obsText);

            // LLM call
            var userPrompt = UserPrompt(obsText, taskDescription);
            var llmResp = await LlmClient.CallAsync(SystemPrompt, userPrompt, model, endpoint, clientType);

            // Parse locator
            var (locatorType, locatorValue) = ParseLocator(llmResp.Content);

            // Oracle evaluation
            var oracleEl = await Oracle.Oracle.FindOracleElementAsync(page, oracleRef);
            var evalResult = await Oracle.Oracle.EvaluateLocatorAsync(
                page, locatorType, locatorValue, oracleEl,
                rawWithAnchors, oracleRef.OracleId, attr => bundleSet.Contains(attr),
                expectedStableSignal, volatileIds, volatileClasses, signalAttrs);

            return new GroundingRecord(
                RunId: runId,
                TaskId: taskId,
                Page: pagePath,
                Bundle: bundle,
                Encoding: encoding,
                Regime: regime,
                Model: model,
                Repetition: repetition,
                ObservationTokens: observationTokens,
                PromptTokensTotal: llmResp.PromptTokens,
                CompletionTokens: llmResp.CompletionTokens,
                LocatorRaw: llmResp.Content,
                LocatorType: locatorType,
                LocatorValue: locatorValue,
                Success: evalResult.Success,
                FailureMode: evalResult.FailureMode,
                PredicateUniqueMatch: evalResult.PredicateUniqueMatch,
                PredicateMatchesOracle: evalResult.PredicateMatchesOracle,
                PredicateNonVolatile: evalResult.PredicateNonVolatile,
                PredicateNonPositional: evalResult.PredicateNonPositional,
                StableSignalPresentInBundle: evalResult.StableSignalPresentInBundle,
                ModelIdReturned: llmResp.ModelId,
                TokenizerVersion: TokenCounter.TokenizerVersion(),
                SchemaVersion: SchemaVersion,
                TestbedPage: pagePath,
                TimestampUtc: timestamp,
                Seed: seed.Value
            );
        }
        finally
        {
            await browser.CloseAsync();
        }
    }
}
