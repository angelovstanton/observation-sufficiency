using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

internal static class SmokeTests
{
    /// <summary>
    /// SMOKE_TEST: exercises the DOM walk, tokenizer, oracle resolution, encoders and the
    /// oracle-anchor strip end-to-end on each page in BAR_PAGE_IDS (default page_01), plus the
    /// per-page shadow-boundary sentinels. Zero LLM.
    /// </summary>
    public static async Task RunAsync()
    {
        var pageIds = (Environment.GetEnvironmentVariable("BAR_PAGE_IDS") ?? "page_01")
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

        Console.WriteLine($"── Smoke test (DOM walk + tokenizer, no LLM) — {string.Join(", ", pageIds)} ──");
        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var baseUrl = Config.TestbedBaseUrl.TrimEnd('/');
        var port = new Uri(baseUrl).Port;

        using var server = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        await Task.Delay(1200);

        try
        {
            using var pw = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await pw.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                foreach (var pageId in pageIds)
                {
                    Console.WriteLine();
                    Console.WriteLine($"  ── {pageId} ──");

                    var truthPath = Path.Combine(repoRoot, "shared", "testbed", "pages", $"{pageId}.truth.json");
                    var truthFile = JsonSerializer.Deserialize<TruthFile>(
                        await File.ReadAllTextAsync(truthPath),
                        new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
                    var volatileIds = new HashSet<string>(truthFile.VolatilityLabels.VolatileIds);
                    var volatileClasses = new HashSet<string>(truthFile.VolatilityLabels.VolatileClasses);

                    var page = await browser.NewPageAsync();
                    await page.GotoAsync($"{baseUrl}/pages/{pageId}.html");
                    await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle);

                    // Element count
                    var rawEls = await Observation.WalkDomAsync(page);
                    Console.WriteLine($"    DOM walk: {rawEls.Count} elements");

                    // Oracle resolution check
                    int oracleOk = 0, oracleFail = 0;
                    foreach (var t in truthFile.Targets)
                    {
                        var el = await Oracle.FindOracleElementAsync(page, new OracleRef(t.Oracle));
                        if (el is not null) { oracleOk++; } else { oracleFail++; Console.WriteLine($"    [oracle-miss] {t.Id}"); }
                    }
                    Console.WriteLine($"    Oracle resolution: {oracleOk}/{truthFile.Targets.Length} OK" + (oracleFail > 0 ? $", {oracleFail} MISS" : ""));

                    // DOM-walk encodings
                    foreach (var enc in new[] { "F0", "F1", "F2", "F3" })
                    {
                        var (obs, _, filtered) = await Observation.BuildObservationAsync(
                            page, "B_full", enc, volatileIds, volatileClasses);
                        int tok = BoundedAgents.Shared.Tokenizer.TokenCounter.CountTokens(obs);
                        bool hasLeak = obs.Contains("oracle", StringComparison.OrdinalIgnoreCase);
                        Console.WriteLine($"    B_full + {enc}: {filtered.Count} elements, {tok,7:N0} tokens — strip: {(hasLeak ? "LEAK!" : "OK")}");
                    }

                    // F4 ARIA
                    {
                        var (aria, _, leak) = await Observation.BuildAriaObservationAsync(page);
                        int tok = BoundedAgents.Shared.Tokenizer.TokenCounter.CountTokens(aria);
                        Console.WriteLine($"    B_playwrightMCP + F4 (ARIA): {tok,7:N0} tokens — oracle-leak: {(leak ? "LEAK!" : "none")}");

                        if (pageId == "page_10")
                        {
                            var (f1Obs, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool shadowInF1 = f1Obs.Contains("check_in", StringComparison.OrdinalIgnoreCase)
                                              || f1Obs.Contains("check_out", StringComparison.OrdinalIgnoreCase);
                            bool ariaHasShadow = aria.Contains("Check-in date", StringComparison.OrdinalIgnoreCase);
                            // F0–F3 pierce shadow, so F1 must now INCLUDE shadow elements
                            Console.WriteLine($"    Shadow F1-includes: {(shadowInF1 ? "PASS" : "FAIL")}   F4-includes: {(ariaHasShadow ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_21")
                        {
                            var (f1Obs21, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s2InF1 = f1Obs21.Contains("Play video", StringComparison.OrdinalIgnoreCase);
                            bool ariaHasS2 = aria.Contains("Play video", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('Play video'): {(s2InF1 ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('Play video'): {(ariaHasS2 ? "PASS" : "FAIL")}");
                            // Dump raw F4 ARIA YAML for depth-2 inspection
                            Console.WriteLine("    ── raw F4 ARIA YAML (page_21) ──────────────────────────────");
                            Console.WriteLine(aria);
                            Console.WriteLine("    ── end raw F4 ARIA YAML ─────────────────────────────────────");
                        }

                        if (pageId == "page_19")
                        {
                            var (f1Obs19s, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            // F1 sentinel: "quote-first-name" is the id attribute — DOM walk exposes ids, valid for F1.
                            // F4 sentinel: "First name" is the accessible name (aria-label) — what ARIA snapshots expose.
                            bool s2InF1_19s = f1Obs19s.Contains("quote-first-name", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas19s = aria.Contains("First name", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('quote-first-name' id): {(s2InF1_19s ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('First name' accessible name): {(ariaHas19s ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_13")
                        {
                            var (f1Obs13, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s1InF1_13 = f1Obs13.Contains("export-pdf-btn", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas13 = aria.Contains("Export dashboard as PDF", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    Shadow F1-includes: {(s1InF1_13 ? "PASS" : "FAIL")}   F4-includes: {(ariaHas13 ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_15")
                        {
                            var (f1Obs15, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s1InF1_15 = f1Obs15.Contains("apply-filters-btn", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas15 = aria.Contains("Apply selected filters", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    Shadow F1-includes: {(s1InF1_15 ? "PASS" : "FAIL")}   F4-includes: {(ariaHas15 ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_16")
                        {
                            var (f1Obs16, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s1InF1_16 = f1Obs16.Contains("chat-input", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas16 = aria.Contains("Type your support message", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    Shadow F1-includes: {(s1InF1_16 ? "PASS" : "FAIL")}   F4-includes: {(ariaHas16 ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_20")
                        {
                            var (f1Obs20, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s2InF1_20 = f1Obs20.Contains("Download current payslip as PDF", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas20 = aria.Contains("Download current payslip as PDF", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('Download current payslip as PDF'): {(s2InF1_20 ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('Download current payslip as PDF'): {(ariaHas20 ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_17")
                        {
                            var (f1Obs17s, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s2InF1_17s = f1Obs17s.Contains("Save user changes", StringComparison.OrdinalIgnoreCase);
                            bool ariaHasS2_17 = aria.Contains("Save user changes", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('Save user changes'): {(s2InF1_17s ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('Save user changes'): {(ariaHasS2_17 ? "PASS" : "FAIL")}");
                            Console.WriteLine("    ── raw F4 ARIA YAML (page_17) ──────────────────────────────");
                            Console.WriteLine(aria);
                            Console.WriteLine("    ── end raw F4 ARIA YAML ─────────────────────────────────────");
                        }

                        if (pageId == "page_18")
                        {
                            var (f1Obs18s, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s2InF1_18s = f1Obs18s.Contains("Save card changes", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas18s = aria.Contains("Save card changes", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('Save card changes'): {(s2InF1_18s ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('Save card changes'): {(ariaHas18s ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_22")
                        {
                            var (f1Obs22s, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s2InF1_22s = f1Obs22s.Contains("Save shipment update", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas22s = aria.Contains("Save shipment update", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('Save shipment update'): {(s2InF1_22s ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('Save shipment update'): {(ariaHas22s ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_23")
                        {
                            var (f1Obs23s, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s2InF1_23s = f1Obs23s.Contains("Pay and place order", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas23s = aria.Contains("Pay and place order", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('Pay and place order'): {(s2InF1_23s ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('Pay and place order'): {(ariaHas23s ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_24")
                        {
                            var (f1Obs24s, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s2InF1_24s = f1Obs24s.Contains("Save all preferences", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas24s = aria.Contains("Save all preferences", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    S2 F1-includes ('Save all preferences'): {(s2InF1_24s ? "PASS" : "FAIL")}");
                            Console.WriteLine($"    S2 F4-includes ('Save all preferences'): {(ariaHas24s ? "PASS" : "FAIL")}");
                        }

                        if (pageId == "page_09")
                        {
                            var (f1Obs09, _, _) = await Observation.BuildObservationAsync(
                                page, "B_full", "F1", volatileIds, volatileClasses);
                            bool s1InF1_09 = f1Obs09.Contains("book-appointment-btn", StringComparison.OrdinalIgnoreCase);
                            bool ariaHas09 = aria.Contains("Book appointment slot", StringComparison.OrdinalIgnoreCase);
                            Console.WriteLine($"    Shadow F1-includes: {(s1InF1_09 ? "PASS" : "FAIL")}   F4-includes: {(ariaHas09 ? "PASS" : "FAIL")}");
                        }
                    }

                    // F2 round-trip
                    {
                        var (_, _, filt) = await Observation.BuildObservationAsync(
                            page, "B_full", "F1", volatileIds, volatileClasses);
                        bool rt = ObservationEncoders.VerifyF2RoundTrip(
                            ObservationEncoders.EncodeF1Json(filt.ToList()),
                            ObservationEncoders.EncodeF2CompactJson(filt.ToList()));
                        Console.WriteLine($"    F2 round-trip: {(rt ? "PASS" : "FAIL")}");
                    }

                    // B_identityCore + B_noVolatile spot-check
                    {
                        var (obs, _, filt) = await Observation.BuildObservationAsync(page, "B_identityCore", "F1");
                        int tok = BoundedAgents.Shared.Tokenizer.TokenCounter.CountTokens(obs);
                        Console.WriteLine($"    B_identityCore + F1: {filt.Count} elements, {tok,7:N0} tokens");
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
        Console.WriteLine("── Smoke test done ──────────────────────────────────────────────────");
    }

    // ---------------------------------------------------------------------------
    // LLM_SMOKE_TEST=1 — connectivity + format check, one call per model
    //
    // Reads all 5 BAR_MODEL_DEPLOYMENT_{1..5} from .env.
    // Routing: gpt-* and o{1,3,4}-* → AzureOpenAI service.
    //          Everything else         → AzureInference (Foundry serverless).
    // Builds B_noVolatile×F3 observation from page_01 (the smallest page in the
    // corpus, ~13K tokens), uses task t_01. Reports per-model:
    //   • SDK path + endpoint used
    //   • Temperature sent (omitted for reasoning models)
    //   • Raw response text
    //   • Prompt and completion token counts from the API
    //   • Whether the response parses as a valid css: locator
    // ---------------------------------------------------------------------------

    public static async Task RunLlmAsync()
    {
        Console.OutputEncoding = System.Text.Encoding.UTF8;
        Console.WriteLine("══ LLM CONNECTIVITY SMOKE TEST ═════════════════════════════════════");
        Console.WriteLine("   5 calls (one per model) — B_noVolatile × F3, page_01, task t_01");
        Console.WriteLine("   NOT the run. Zero output files written.");
        Console.WriteLine();

        // ── Determine which deployments are configured ────────────────────────
        var deployments = new (int Slot, string Name)[]
        {
            (1, Config.Get("BAR_MODEL_DEPLOYMENT_1", required: false)),
            (2, Config.Get("BAR_MODEL_DEPLOYMENT_2", required: false)),
            (3, Config.Get("BAR_MODEL_DEPLOYMENT_3", required: false)),
            (4, Config.Get("BAR_MODEL_DEPLOYMENT_4", required: false)),
            (5, Config.Get("BAR_MODEL_DEPLOYMENT_5", required: false)),
        }.Where(d => !string.IsNullOrEmpty(d.Name)).ToArray();

        if (deployments.Length == 0)
        {
            throw new InvalidOperationException(
                "No BAR_MODEL_DEPLOYMENT_{1..5} env vars set. Fill in .env first.");
        }

        Console.WriteLine("Deployment roster:");
        foreach (var (slot, name) in deployments)
        {
            var (clientType, endpoint) = Helpers.RouteModel(name);
            var isReasoning = LlmClient.IsReasoningModel(name);
            Console.WriteLine(
                $"  [{slot}] {name,-28}  path={clientType,-16}  " +
                $"temp={(isReasoning ? "OMITTED (reasoning)" : "0")}");
            Console.WriteLine($"       endpoint={Helpers.TruncateEndpoint(endpoint)}");
        }
        Console.WriteLine();

        // ── Build one observation on page_01, B_noVolatile × F3 ─────────────
        var repoRoot = Helpers.FindRepoRoot(AppContext.BaseDirectory);
        var testbedDir = Path.Combine(repoRoot, "shared", "testbed");
        var port = new Uri(Config.TestbedBaseUrl).Port;

        var truthPath = Path.Combine(testbedDir, "pages", "page_01.truth.json");
        var truthFile = JsonSerializer.Deserialize<TruthFile>(
            await File.ReadAllTextAsync(truthPath),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })!;
        var volatileIds = new HashSet<string>(truthFile.VolatilityLabels.VolatileIds, StringComparer.Ordinal);
        var volatileClasses = new HashSet<string>(truthFile.VolatilityLabels.VolatileClasses, StringComparer.Ordinal);
        var smokeTarget = truthFile.Targets[0];   // t_01

        string obsText;
        int obsTok;

        using var server = Process.Start(new ProcessStartInfo
        {
            FileName = "python",
            Arguments = $"-m http.server {port} --directory \"{testbedDir}\"",
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        })!;
        await Task.Delay(1200);

        try
        {
            using var pw = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await pw.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                var page = await browser.NewPageAsync();
                await page.GotoAsync($"{Config.TestbedBaseUrl.TrimEnd('/')}/pages/page_01.html");
                await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle);
                (obsText, _, _) = await Observation.BuildObservationAsync(
                    page, "B_noVolatile", "F3", volatileIds, volatileClasses);
                obsTok = BoundedAgents.Shared.Tokenizer.TokenCounter.CountTokens(obsText);
                await browser.CloseAsync();
            }
            finally { }
        }
        finally
        {
            try { server.Kill(entireProcessTree: true); } catch { }
        }

        Console.WriteLine($"Observation built: page_01 × B_noVolatile × F3 = {obsTok:N0} obs tokens");
        Console.WriteLine($"Task: [{smokeTarget.Id}] {smokeTarget.Intent}");
        Console.WriteLine();

        var systemPrompt = GroundingRunner.SystemPrompt;
        var userPrompt = $"Page observation:\n{obsText}\n\nTask: {smokeTarget.Intent}\n\nLocator:";

        // ── Call each model once ─────────────────────────────────────────────
        var results = new List<(string Name, bool Ok, string Info, string RawResponse, int PtokApi, int CtokApi)>();

        foreach (var (slot, name) in deployments)
        {
            Console.WriteLine($"── [{slot}] {name} ──────────────────────────────────────────────");
            var (clientType, endpoint) = Helpers.RouteModel(name);
            var isReasoning = LlmClient.IsReasoningModel(name);

            Console.WriteLine($"   SDK path : {clientType}");
            Console.WriteLine($"   Endpoint : {Helpers.TruncateEndpoint(endpoint)}");
            Console.WriteLine($"   Temp     : {(isReasoning ? "OMITTED — reasoning model; temperature=0 not sent" : "0")}");
            Console.Write("   Calling... ");

            string rawResponse; int ptok; int ctok;
            bool ok;
            string info;
            try
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();
                var resp = await LlmClient.CallAsync(systemPrompt, userPrompt, name, endpoint, clientType);
                sw.Stop();
                rawResponse = resp.Content;
                ptok = resp.PromptTokens;
                ctok = resp.CompletionTokens;

                // Parse: does it start with a recognizable locator prefix?
                bool hasCss = rawResponse.TrimStart().StartsWith("css:", StringComparison.OrdinalIgnoreCase);
                bool hasXPath = rawResponse.TrimStart().StartsWith("xpath:", StringComparison.OrdinalIgnoreCase);
                string parseStatus = hasCss ? "css: OK" : hasXPath ? "xpath: OK (non-canonical)" : "NO PREFIX — parse fallback to css";

                Console.WriteLine($"OK ({sw.ElapsedMilliseconds} ms)");
                Console.WriteLine($"   Response : {Helpers.Truncate(rawResponse, 120)}");
                Console.WriteLine($"   Parse    : {parseStatus}");
                Console.WriteLine($"   API tok  : prompt={ptok:N0}  completion={ctok:N0}");
                Console.WriteLine($"   Obs tok  : {obsTok:N0} (fixed tokenizer, the cost metric)");

                if (isReasoning)
                {
                    // The completion count from the API includes reasoning tokens.
                    // We asked for max 4096; flag if the model used >80% of that budget.
                    int maxOut = 4096;
                    Console.WriteLine($"   Reasoning: completion {ctok} of {maxOut} max — " +
                                      (ctok > maxOut * 0.8 ? "WARN: close to limit, consider raising MaxReasoningTokens" : "headroom OK"));
                }

                ok = true;
                info = parseStatus;
            }
            catch (Exception ex)
            {
                rawResponse = "";
                ptok = ctok = 0;
                Console.WriteLine($"FAILED");
                Console.WriteLine($"   Error    : {ex.GetType().Name}: {ex.Message}");
                if (ex.InnerException is not null)
                {
                    Console.WriteLine($"   Inner    : {ex.InnerException.Message}");
                }

                ok = false;
                info = $"EXCEPTION: {ex.Message[..Math.Min(80, ex.Message.Length)]}";
            }

            results.Add((name, ok, info, rawResponse, ptok, ctok));
            Console.WriteLine();
        }

        // ── Summary ───────────────────────────────────────────────────────────
        Console.WriteLine("══ SUMMARY ══════════════════════════════════════════════════════════");
        Console.WriteLine($"  {"Model",-28}  {"Status",-8}  {"API prompt tok",14}  {"API compl tok",13}  Note");
        Console.WriteLine($"  {new string('─', 28)}  {new string('─', 8)}  {new string('─', 14)}  {new string('─', 13)}  ─────");
        foreach (var (name, ok, info, _, ptok, ctok) in results)
        {
            Console.WriteLine($"  {name,-28}  {(ok ? "OK" : "FAIL"),-8}  {ptok,14:N0}  {ctok,13:N0}  {info}");
        }

        Console.WriteLine();
        int passed = results.Count(r => r.Ok);
        Console.WriteLine($"  {passed}/{results.Count} models reachable");

        if (passed < results.Count)
        {
            Console.WriteLine();
            Console.WriteLine("  FAILED MODELS — check before running overnight batch:");
            foreach (var (name, ok, info, _, _, _) in results.Where(r => !r.Ok))
            {
                Console.WriteLine($"    {name}: {info}");
            }
        }
        Console.WriteLine("════════════════════════════════════════════════════════════════════");
    }
}
