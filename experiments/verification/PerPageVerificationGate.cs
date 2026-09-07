using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

/// <summary>
/// Implements the per-page verification gate specified in TESTBED_SPEC §8: oracle-anchor
/// strip checks across encodings, the per-page shadow-boundary sentinels, the locator leak
/// detector, and the NONE-target invariant. Runs once per page before the results table.
/// </summary>
internal static class PerPageVerificationGate
{
    public static async Task RunAsync(
        string pageId,
        string[] domWalkEncodings,
        IReadOnlySet<string> volatileIds,
        IReadOnlySet<string> volatileClasses,
        IReadOnlySet<string> noneTargetIds,
        List<GroundingRecord> allFlat,
        Dictionary<(string, string), List<GroundingRecord>> allRecords,
        Func<Task<Process>> startFreshServer)
    {
        // ── §8 Verification gate ──────────────────────────────────────────────
        Console.WriteLine($"── {pageId} §8 Verification ──────────────────────────────────────────");
        Console.WriteLine();

        Process? server2 = null;
        bool allVerificationsPass = true;
        try
        {
            server2 = await startFreshServer();

            using var pw = await Microsoft.Playwright.Playwright.CreateAsync();
            var browser = await pw.Chromium.LaunchAsync(new() { Headless = true });
            try
            {
                var page = await browser.NewPageAsync();
                var pageUrl = $"{Config.TestbedBaseUrl.TrimEnd('/')}/pages/{pageId}.html";
                await page.GotoAsync(pageUrl);
                await page.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle);

                // ── Strip check ──────────────────────────────────────────────
                Console.WriteLine("  Strip check (oracle anchors absent from each encoding):");
                foreach (var enc in domWalkEncodings)
                {
                    var (obsText, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", enc, volatileIds, volatileClasses);
                    bool pass = !obsText.Contains("oracle", StringComparison.OrdinalIgnoreCase);
                    if (!pass)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    {enc} oracle-free: {(pass ? "PASS" : "FAIL — 'oracle' found in observation!")}");
                }

                var (ariaYaml, _, ariaLeak) = await Observation.BuildAriaObservationAsync(page);
                if (ariaLeak)
                {
                    allVerificationsPass = false;
                }

                Console.WriteLine($"    F4 ARIA oracle-free: {(ariaLeak ? "FAIL — 'oracle' found in ARIA YAML!" : "PASS")}");

                var rawElements = await Observation.WalkDomAsync(page);
                var stripped = AttributeBundles.StripOracleAnchors(rawElements);
                bool stripWorks = rawElements.Any(e => e.Attrs.ContainsKey("data-oracle-id"))
                               && !stripped.Any(e => e.Attrs.ContainsKey("data-oracle-id"));
                if (!stripWorks)
                {
                    allVerificationsPass = false;
                }

                Console.WriteLine($"    Oracle-strip removes data-oracle-id: {(stripWorks ? "PASS" : "FAIL")}");

                // ── page_10 shadow DOM boundary check ────────────────────────
                // F0–F3 now pierce shadow roots, so shadow elements must appear in F1.
                // Both DOM-walk and ARIA paths should include shadow content.
                if (pageId == "page_10")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_10):");

                    var (f1Obs, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool shadowInF1 = f1Obs.Contains("check_in", StringComparison.OrdinalIgnoreCase)
                                    || f1Obs.Contains("check_out", StringComparison.OrdinalIgnoreCase);
                    bool f1ShadowPass = shadowInF1;  // MUST be present — F0–F3 now pierce shadow
                    if (!f1ShadowPass)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes shadow attrs (check_in/check_out present): {(f1ShadowPass ? "PASS" : "FAIL — shadow elements absent from F1!")}");

                    bool ariaHasShadow = ariaYaml.Contains("Check-in date", StringComparison.OrdinalIgnoreCase);
                    bool f4ShadowPass = ariaHasShadow;
                    if (!f4ShadowPass)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F4 includes shadow content ('Check-in date' present): {(f4ShadowPass ? "PASS" : "FAIL — shadow content absent from F4 ARIA YAML!")}");
                }

                if (pageId == "page_21")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_21, S2 — video-player-shell → player-control-bar):");

                    var (f1Obs21, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    // "Play video" is aria-label on t_06 — lives in the level-2 (player-control-bar) shadow root.
                    bool s2InF1 = f1Obs21.Contains("Play video", StringComparison.OrdinalIgnoreCase);
                    bool ariaHasS2 = ariaYaml.Contains("Play video", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHasS2)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('Play video'): {(s2InF1 ? "PASS" : "FAIL — depth-2 shadow elements absent from F1!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('Play video'): {(ariaHasS2 ? "PASS" : "FAIL — depth-2 shadow absent from ARIA!")}");
                }

                if (pageId == "page_11")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_11, S1):");

                    var (f1Obs11, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s1InF1_11 = f1Obs11.Contains("Select Basic plan", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas11 = ariaYaml.Contains("Select Basic plan", StringComparison.OrdinalIgnoreCase);
                    if (!s1InF1_11)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas11)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes S1 shadow ('Select Basic plan'): {(s1InF1_11 ? "PASS" : "FAIL")}");
                    Console.WriteLine($"    F4 includes S1 shadow ('Select Basic plan'): {(ariaHas11 ? "PASS" : "FAIL")}");
                }

                if (pageId == "page_12")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_12, S1):");

                    var (f1Obs12, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s1InF1_12 = f1Obs12.Contains("Play lesson video", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas12 = ariaYaml.Contains("Play lesson video", StringComparison.OrdinalIgnoreCase);
                    if (!s1InF1_12)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas12)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes S1 shadow ('Play lesson video'): {(s1InF1_12 ? "PASS" : "FAIL")}");
                    Console.WriteLine($"    F4 includes S1 shadow ('Play lesson video'): {(ariaHas12 ? "PASS" : "FAIL")}");
                }

                if (pageId == "page_14")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_14, S1):");

                    var (f1Obs14, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s1InF1_14 = f1Obs14.Contains("Proceed to checkout", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas14 = ariaYaml.Contains("Proceed to checkout", StringComparison.OrdinalIgnoreCase);
                    if (!s1InF1_14)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas14)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes S1 shadow ('Proceed to checkout'): {(s1InF1_14 ? "PASS" : "FAIL")}");
                    Console.WriteLine($"    F4 includes S1 shadow ('Proceed to checkout'): {(ariaHas14 ? "PASS" : "FAIL")}");
                }

                if (pageId == "page_19")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_19, S2 — level-2 form-section shadow):");

                    var (f1Obs19, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    // F1 checks for the id attribute "quote-first-name" — DOM walk exposes id, so this is valid for F1.
                    // F4 checks for "First name" — the ACTUAL accessible name of the input (aria-label="First name").
                    // ARIA snapshots never expose HTML id values; checking for "quote-first-name" in F4 is a bug.
                    bool s2InF1_19 = f1Obs19.Contains("quote-first-name", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas19 = ariaYaml.Contains("First name", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1_19)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas19)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('quote-first-name' id): {(s2InF1_19 ? "PASS" : "FAIL — depth-2 form-section shadow absent!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('First name' accessible name): {(ariaHas19 ? "PASS" : "FAIL — depth-2 absent in ARIA snapshot")}");
                }

                if (pageId == "page_13")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_13, S1 — analytics-filter shadow):");
                    var (f1Obs13, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s1InF1_13 = f1Obs13.Contains("export-pdf-btn", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas13 = ariaYaml.Contains("Export dashboard as PDF", StringComparison.OrdinalIgnoreCase);
                    if (!s1InF1_13)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas13)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes S1 shadow ('export-pdf-btn'): {(s1InF1_13 ? "PASS" : "FAIL")}");
                    Console.WriteLine($"    F4 includes S1 shadow ('Export dashboard as PDF'): {(ariaHas13 ? "PASS" : "FAIL")}");
                }

                if (pageId == "page_15")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_15, S1 — filter-sidebar shadow):");
                    var (f1Obs15, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s1InF1_15 = f1Obs15.Contains("apply-filters-btn", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas15 = ariaYaml.Contains("Apply selected filters", StringComparison.OrdinalIgnoreCase);
                    if (!s1InF1_15)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas15)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes S1 shadow ('apply-filters-btn'): {(s1InF1_15 ? "PASS" : "FAIL")}");
                    Console.WriteLine($"    F4 includes S1 shadow ('Apply selected filters'): {(ariaHas15 ? "PASS" : "FAIL")}");
                }

                if (pageId == "page_16")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_16, S1 — chat-widget shadow):");
                    var (f1Obs16, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s1InF1_16 = f1Obs16.Contains("chat-input", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas16 = ariaYaml.Contains("Type your support message", StringComparison.OrdinalIgnoreCase);
                    if (!s1InF1_16)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas16)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes S1 shadow ('chat-input'): {(s1InF1_16 ? "PASS" : "FAIL")}");
                    Console.WriteLine($"    F4 includes S1 shadow ('Type your support message'): {(ariaHas16 ? "PASS" : "FAIL")}");
                }

                if (pageId == "page_20")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_20, S2 — hr-portal → payslip-viewer):");
                    var (f1Obs20, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s2InF1_20 = f1Obs20.Contains("Download current payslip as PDF", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas20 = ariaYaml.Contains("Download current payslip as PDF", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1_20)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas20)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('Download current payslip as PDF'): {(s2InF1_20 ? "PASS" : "FAIL — depth-2 shadow elements absent from F1!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('Download current payslip as PDF'): {(ariaHas20 ? "PASS" : "FAIL — depth-2 shadow absent from ARIA!")}");
                }

                if (pageId == "page_17")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_17, S2 — admin-console-shell → user-detail-panel):");
                    var (f1Obs17, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    // "Save user changes" is aria-label on t_10 — lives in level-2 (user-detail-panel) shadow.
                    // Playwright AriaSnapshotAsync pierces all open shadow roots, so F4 must ALSO include it.
                    bool s2InF1_17 = f1Obs17.Contains("Save user changes", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas17 = ariaYaml.Contains("Save user changes", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1_17)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas17)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('Save user changes'): {(s2InF1_17 ? "PASS" : "FAIL — depth-2 shadow elements absent from F1!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('Save user changes'): {(ariaHas17 ? "PASS" : "FAIL — depth-2 shadow absent from ARIA!")}");
                }

                if (pageId == "page_18")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_18, S2 — kanban-shell → card-editor):");
                    var (f1Obs18, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s2InF1_18 = f1Obs18.Contains("Save card changes", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas18 = ariaYaml.Contains("Save card changes", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1_18)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas18)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('Save card changes'): {(s2InF1_18 ? "PASS" : "FAIL — depth-2 shadow elements absent from F1!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('Save card changes'): {(ariaHas18 ? "PASS" : "FAIL — depth-2 shadow absent from ARIA!")}");
                }

                if (pageId == "page_22")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_22, S2 — tracking-shell → shipment-editor):");
                    var (f1Obs22, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s2InF1_22 = f1Obs22.Contains("Save shipment update", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas22 = ariaYaml.Contains("Save shipment update", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1_22)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas22)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('Save shipment update'): {(s2InF1_22 ? "PASS" : "FAIL — depth-2 shadow elements absent from F1!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('Save shipment update'): {(ariaHas22 ? "PASS" : "FAIL — depth-2 shadow absent from ARIA!")}");
                }

                if (pageId == "page_23")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_23, S2 — payment-shell → payment-widget):");
                    var (f1Obs23, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s2InF1_23 = f1Obs23.Contains("Pay and place order", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas23 = ariaYaml.Contains("Pay and place order", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1_23)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas23)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('Pay and place order'): {(s2InF1_23 ? "PASS" : "FAIL — depth-2 shadow elements absent from F1!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('Pay and place order'): {(ariaHas23 ? "PASS" : "FAIL — depth-2 shadow absent from ARIA!")}");
                }

                if (pageId == "page_24")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_24, S2 — settings-shell → preferences-panel):");
                    var (f1Obs24, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s2InF1_24 = f1Obs24.Contains("Save all preferences", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas24 = ariaYaml.Contains("Save all preferences", StringComparison.OrdinalIgnoreCase);
                    if (!s2InF1_24)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas24)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes level-2 shadow ('Save all preferences'): {(s2InF1_24 ? "PASS" : "FAIL — depth-2 shadow elements absent from F1!")}");
                    Console.WriteLine($"    F4 includes level-2 shadow ('Save all preferences'): {(ariaHas24 ? "PASS" : "FAIL — depth-2 shadow absent from ARIA!")}");
                }

                if (pageId == "page_09")
                {
                    Console.WriteLine();
                    Console.WriteLine("  Shadow boundary (page_09, S1 — calendar-widget shadow):");
                    var (f1Obs09, _, _) = await Observation.BuildObservationAsync(
                        page, "B_full", "F1", volatileIds, volatileClasses);
                    bool s1InF1_09 = f1Obs09.Contains("book-appointment-btn", StringComparison.OrdinalIgnoreCase);
                    bool ariaHas09 = ariaYaml.Contains("Book appointment slot", StringComparison.OrdinalIgnoreCase);
                    if (!s1InF1_09)
                    {
                        allVerificationsPass = false;
                    }

                    if (!ariaHas09)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    F1 includes S1 shadow ('book-appointment-btn'): {(s1InF1_09 ? "PASS" : "FAIL")}");
                    Console.WriteLine($"    F4 includes S1 shadow ('Book appointment slot'): {(ariaHas09 ? "PASS" : "FAIL")}");
                }

                await browser.CloseAsync();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"    Strip check ERROR: {ex.Message}");
                allVerificationsPass = false;
            }
            Console.WriteLine();

            // ── F2 round-trip check ──────────────────────────────────────────
            Console.WriteLine("  F2 round-trip (de-minify → field-compare vs F1):");
            if (!allRecords.ContainsKey(("B_full", "F2")))
            {
                Console.WriteLine("    SKIP — no B_full × F2 records found");
            }
            else
            {
                var pw2 = await Microsoft.Playwright.Playwright.CreateAsync();
                var b2 = await pw2.Chromium.LaunchAsync(new() { Headless = true });
                try
                {
                    var pg2 = await b2.NewPageAsync();
                    await pg2.GotoAsync($"{Config.TestbedBaseUrl.TrimEnd('/')}/pages/{pageId}.html");
                    await pg2.WaitForLoadStateAsync(Microsoft.Playwright.LoadState.NetworkIdle);
                    var (_, _, filt) = await Observation.BuildObservationAsync(pg2, "B_full", "F1", volatileIds, volatileClasses);
                    var f1rt = ObservationEncoders.EncodeF1Json(filt.ToList());
                    var f2rt = ObservationEncoders.EncodeF2CompactJson(filt.ToList());
                    bool rtPass = ObservationEncoders.VerifyF2RoundTrip(f1rt, f2rt);
                    if (!rtPass)
                    {
                        allVerificationsPass = false;
                    }

                    Console.WriteLine($"    B_full × F2 round-trip: {(rtPass ? "PASS" : "FAIL — field mismatch after key expansion")}");
                    await b2.CloseAsync();
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"    Round-trip ERROR: {ex.Message}");
                    allVerificationsPass = false;
                }
            }
            Console.WriteLine();
        }
        finally
        {
            try { server2?.Kill(entireProcessTree: true); } catch { }
        }

        // ── observation_tokens anomalies ─────────────────────────────────────
        var zeroTokRecs = allFlat.Where(r => r.ObservationTokens == 0).ToList();
        bool unexpectedZero = zeroTokRecs.Any(r => r.Bundle != "B_minimalCore");
        if (unexpectedZero)
        {
            allVerificationsPass = false;
        }

        string tokNote = zeroTokRecs.Count == 0
            ? "PASS — all records have tokens > 0"
            : unexpectedZero
                ? $"FAIL — unexpected 0-token records: {string.Join(", ", zeroTokRecs.Where(r => r.Bundle != "B_minimalCore").Select(r => $"{r.Bundle}/{r.TaskId}"))}"
                : $"NOTE — {zeroTokRecs.Count} B_minimalCore records at 0 tokens (expected)";
        Console.WriteLine($"  observation_tokens check: {tokNote}");

        // ── Leak detector ────────────────────────────────────────────────────
        var leakers = allFlat
            .Where(r => r.LocatorValue.Contains("data-oracle-", StringComparison.OrdinalIgnoreCase))
            .ToList();
        bool leakOk = leakers.Count == 0;
        if (!leakOk)
        {
            allVerificationsPass = false;
        }

        Console.WriteLine($"  Leak detector (no locator references data-oracle-*): {(leakOk ? "PASS" : $"FAIL — {leakers.Count} locator(s)")}");
        foreach (var l in leakers)
        {
            Console.WriteLine($"    {l.Bundle}×{l.Encoding} {l.TaskId}: {l.LocatorValue}");
        }

        // ── NONE-target invariant (dynamic from signal_attrs) ─────────────────
        var noneViolations = allFlat.Where(r => noneTargetIds.Contains(r.TaskId) && r.Success).ToList();
        if (noneViolations.Count > 0)
        {
            allVerificationsPass = false;
            Console.WriteLine($"  NONE-target invariant ({string.Join(", ", noneTargetIds.OrderBy(x => x))} always fail): FAIL — {noneViolations.Count} false-pass record(s):");
            foreach (var v in noneViolations)
            {
                Console.WriteLine($"    {v.TaskId} {v.Bundle}×{v.Encoding}: {v.LocatorValue}");
            }
        }
        else
        {
            Console.WriteLine($"  NONE-target invariant ({string.Join(", ", noneTargetIds.OrderBy(x => x))} always fail): PASS");
        }

        Console.WriteLine();
        Console.WriteLine($"  §8 overall: {(allVerificationsPass ? "ALL PASS" : "FAILURES ABOVE — investigate before scaling")}");
        Console.WriteLine();
    }
}
