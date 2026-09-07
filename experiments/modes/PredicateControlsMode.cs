using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

internal static class PredicateControlsMode
{
    // ---------------------------------------------------------------------------
    // Replays hand-labeled control locators through the full
    // 5-predicate conjunction and verifies success + failureMode against expected.
    // Zero LLM calls. Run with: PREDICATE_CONTROLS=1 dotnet run --project experiments/
    // ---------------------------------------------------------------------------

    public static async Task RunAsync()
    {
        Console.WriteLine("── Predicate control set (hand-labeled, zero LLM) ──────────────────────────");

        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var controlPath = Path.Combine(repoRoot, "experiments", "control", "predicate_controls.json");
        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var baseUrl = Config.TestbedBaseUrl.TrimEnd('/');
        var port = new Uri(baseUrl).Port;

        var controls = JsonSerializer.Deserialize<ControlRecord[]>(
            await File.ReadAllTextAsync(controlPath),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;

        using var server = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        await Task.Delay(1200);

        int total = 0, passed = 0;

        try
        {
            using var pw = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await pw.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                foreach (var grp in controls.GroupBy(c => c.PageId))
                {
                    var pageId = grp.Key;
                    var truthPath = Path.Combine(repoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json");
                    var truthFile = JsonSerializer.Deserialize<TruthFile>(
                        await File.ReadAllTextAsync(truthPath),
                        new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;

                    var volatileIds = new HashSet<string>(truthFile.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
                    var volatileClasses = new HashSet<string>(truthFile.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
                    var targetByOracle = truthFile.Targets.ToDictionary(t => t.Oracle, StringComparer.Ordinal);

                    var page = await browser.NewPageAsync();
                    await page.GotoAsync($"{baseUrl}/pages/{pageId}.html");
                    await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle);

                    // Build rawWithAnchors once per page (B_full keeps all attrs)
                    var (_, rawWithAnchors, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);

                    Console.WriteLine();
                    Console.WriteLine($"  ── {pageId} ({grp.Count()} controls) ──");

                    foreach (var ctrl in grp)
                    {
                        total++;

                        // Look up signal_attrs and expectedStableSignal from truth.json
                        targetByOracle.TryGetValue(ctrl.OracleId, out var tgt);
                        IReadOnlyList<string> signalAttrs = tgt?.SignalAttrs ?? [];
                        string? expectedStableSignal = tgt?.ExpectedStableSignal;

                        // Find oracle element in the live DOM
                        Microsoft.Playwright.IElementHandle? oracleEl = null;
                        try
                        {
                            oracleEl = await BoundedAgents.Shared.Oracle.Oracle.FindOracleElementAsync(
                                page, new OracleRef(ctrl.OracleId));
                        }
                        catch
                        {
                            Console.WriteLine($"    [SKIP] {ctrl.Label} — oracle '{ctrl.OracleId}' not found in DOM");
                            continue;
                        }

                        // Bundle-aware bundleContains: B_playwrightMCP exposes only the ARIA tree;
                        // all other records use B_full semantics (every attr in bundle).
                        Func<string, bool> bundleContains = ctrl.Bundle switch
                        {
                            "B_playwrightMCP" => attr =>
                                attr is "role" ||
                                attr.StartsWith("aria-", StringComparison.OrdinalIgnoreCase),
                            _ => _ => true,
                        };

                        // Run the full 5-predicate conjunction
                        var result = await BoundedAgents.Shared.Oracle.Oracle.EvaluateLocatorAsync(
                            page,
                            ctrl.LocatorType,
                            ctrl.LocatorValue,
                            oracleEl!,
                            rawWithAnchors,
                            ctrl.OracleId,
                            bundleContains,
                            expectedStableSignal,
                            volatileIds,
                            volatileClasses,
                            signalAttrs);

                        var exp = ctrl.Expected;
                        bool ok = result.Success == exp.Success
                               && result.FailureMode == exp.FailureMode
                               && result.PredicateNonVolatile == exp.NonVolatile
                               && result.PredicateNonPositional == exp.NonPositional
                               && result.StableSignalPresentInBundle == exp.StableSignalPresent;

                        if (ok)
                        {
                            passed++;
                        }

                        var tag = ok ? "PASS" : "FAIL";
                        Console.WriteLine($"    [{tag}] {ctrl.Label}");
                        if (!ok)
                        {
                            if (result.Success != exp.Success)
                            {
                                Console.WriteLine($"           success:  expected={exp.Success}  got={result.Success}");
                            }

                            if (result.FailureMode != exp.FailureMode)
                            {
                                Console.WriteLine($"           mode:     expected={exp.FailureMode ?? "null"}  got={result.FailureMode ?? "null"}");
                            }

                            if (result.PredicateNonVolatile != exp.NonVolatile)
                            {
                                Console.WriteLine($"           nonVol:   expected={exp.NonVolatile}  got={result.PredicateNonVolatile}");
                            }

                            if (result.PredicateNonPositional != exp.NonPositional)
                            {
                                Console.WriteLine($"           nonPos:   expected={exp.NonPositional}  got={result.PredicateNonPositional}");
                            }

                            if (result.StableSignalPresentInBundle != exp.StableSignalPresent)
                            {
                                Console.WriteLine($"           stable:   expected={exp.StableSignalPresent}  got={result.StableSignalPresentInBundle}");
                            }
                        }
                    }

                    await page.CloseAsync();
                }
            }
            finally { await browser.CloseAsync(); }
        }
        finally
        {
            try { server.Kill(entireProcessTree: true); } catch { }
        }

        Console.WriteLine();
        Console.WriteLine($"── Controls: {passed}/{total} passed ───────────────────────────────────────────");
        if (passed < total)
        {
            Console.WriteLine("── ONE OR MORE CONTROLS FAILED — review before trusting the corpus ────────");
        }
        else
        {
            Console.WriteLine("── All controls green — predicate validated across all three dimensions ───");
        }
    }
}
