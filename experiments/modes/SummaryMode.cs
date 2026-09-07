using System.Diagnostics;
using System.Text.Json;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Oracle;

internal static class SummaryMode
{
    /// <summary>
    /// Writes the per-run Markdown summary (per-page results tables and §8 gate outcomes) for the
    /// pages just processed to experiments/runs/summary_&lt;date&gt;.md. Called at the end of the matrix loop.
    /// </summary>
    public static async Task RunAsync(
        string runsDir,
        string[] pageIds,
        List<(string Bundle, string Encoding)> validPairs,
        DateTimeOffset startTime)
    {
        Console.WriteLine();
        Console.WriteLine("── Generating summary ────────────────────────────────────────────────");

        var allBundlesOrdered = new[] { "B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore", "B_playwrightMCP" };
        var allEncodingsOrdered = new[] { "F0", "F1", "F2", "F3", "F4" };
        var jsonReadOpts = new JsonSerializerOptions
        {
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
            PropertyNameCaseInsensitive = true,
        };

        var sb = new System.Text.StringBuilder();
        var runDate = DateTimeOffset.UtcNow.ToString("yyyy-MM-dd");
        sb.AppendLine($"# Run summary — {runDate}");
        sb.AppendLine();
        sb.AppendLine($"Generated: {DateTimeOffset.UtcNow:u}  |  Run duration: {Helpers.FormatDuration(DateTimeOffset.UtcNow - startTime)}");
        sb.AppendLine($"Pages: {string.Join(", ", pageIds)}");
        sb.AppendLine($"Model: {Config.Get("BAR_MODEL_DEPLOYMENT_1")}");
        sb.AppendLine();

        foreach (var pageId in pageIds)
        {
            var outputFile = Path.Combine(runsDir, $"matrix_{pageId}.jsonl");
            if (!File.Exists(outputFile))
            {
                sb.AppendLine($"## {pageId}  ⚠ no output file found");
                sb.AppendLine();
                continue;
            }

            var lines = await File.ReadAllLinesAsync(outputFile);
            var allFlat = lines
                .Where(l => !string.IsNullOrWhiteSpace(l))
                .Select(l => JsonSerializer.Deserialize<GroundingRecord>(l, jsonReadOpts)!)
                .ToList();
            var byPair = allFlat
                .GroupBy(r => (r.Bundle, r.Encoding))
                .ToDictionary(g => g.Key, g => g.ToList());

            // NONE-target detection: stable_signal_present_in_bundle=false in B_full
            // means no stable signal exists on the page at all for that target.
            var noneIds = allFlat
                .Where(r => r.Bundle == "B_full" && !r.StableSignalPresentInBundle)
                .Select(r => r.TaskId).Distinct().ToHashSet(StringComparer.Ordinal);

            sb.AppendLine($"## {pageId}");
            sb.AppendLine();

            // §8 gate (derived from records)
            var noneViolations = allFlat.Where(r => noneIds.Contains(r.TaskId) && r.Success).ToList();
            var leakers = allFlat.Where(r => r.LocatorValue.Contains("data-oracle-", StringComparison.OrdinalIgnoreCase)).ToList();
            var zeroTokBad = allFlat.Where(r => r.ObservationTokens == 0 && r.Bundle != "B_minimalCore").ToList();
            var xpathRecords = allFlat.Where(r => r.LocatorType == "xpath").ToList();

            sb.AppendLine("### §8 gate");
            sb.AppendLine($"- NONE-target invariant: {(noneViolations.Count == 0 ? "PASS" : $"FAIL — {noneViolations.Count} violation(s)")}");
            sb.AppendLine($"- Oracle-leak detector: {(leakers.Count == 0 ? "PASS" : $"FAIL — {leakers.Count} locator(s) reference data-oracle-*")}");
            sb.AppendLine($"- Zero-token anomalies: {(zeroTokBad.Count == 0 ? "PASS" : $"FAIL — {zeroTokBad.Count} unexpected zero-token records")}");
            sb.AppendLine($"- CSS-only compliance: {(xpathRecords.Count == 0 ? "PASS" : $"{xpathRecords.Count} xpath record(s) — model non-compliance with CSS-only instruction")}");
            sb.AppendLine();

            // Results table
            int nTargets = allFlat.Select(r => r.TaskId).Distinct().Count();
            sb.AppendLine($"### Results (success / {nTargets} targets)");
            sb.Append("| Bundle |");
            foreach (var enc in allEncodingsOrdered)
            {
                sb.Append($" {enc} |");
            }

            sb.AppendLine();
            sb.Append("|--------|");
            foreach (var _ in allEncodingsOrdered)
            {
                sb.Append("-----|");
            }

            sb.AppendLine();
            foreach (var bnd in allBundlesOrdered)
            {
                sb.Append($"| {bnd} |");
                foreach (var enc in allEncodingsOrdered)
                {
                    if (byPair.TryGetValue((bnd, enc), out var recs))
                    {
                        sb.Append($" {recs.Count(r => r.Success)}/{recs.Count} |");
                    }
                    else
                    {
                        sb.Append(" — |");
                    }
                }
                sb.AppendLine();
            }
            sb.AppendLine();

            // Prediction contradictions: success=true but stable_signal_present_in_bundle=false
            var contradictions = allFlat
                .Where(r => r.Success && !r.StableSignalPresentInBundle)
                .Select(r => $"{r.TaskId} {r.Bundle}×{r.Encoding}")
                .ToList();
            sb.AppendLine("### Prediction contradictions");
            if (contradictions.Count == 0)
            {
                sb.AppendLine("0 — none.");
            }
            else
            {
                sb.AppendLine($"{contradictions.Count} contradiction(s) (success=true but stable_signal_present_in_bundle=false — investigate):");
                foreach (var c in contradictions)
                {
                    sb.AppendLine($"- {c}");
                }
            }
            sb.AppendLine();

            // page_08 token cost table
            if (pageId == "page_08")
            {
                sb.AppendLine("### Token cost at Extreme tier (mean observation_tokens across targets)");
                var costBundles = new[] { "B_full", "B_noVolatile", "B_identityCore" };
                var costEncodings = new[] { "F0", "F1", "F3" };
                sb.Append("| Bundle |");
                foreach (var e in costEncodings)
                {
                    sb.Append($" {e} (mean tok) |");
                }

                sb.AppendLine();
                sb.Append("|--------|");
                foreach (var _ in costEncodings)
                {
                    sb.Append("-------------|");
                }

                sb.AppendLine();
                foreach (var bnd in costBundles)
                {
                    sb.Append($"| {bnd} |");
                    foreach (var enc in costEncodings)
                    {
                        if (byPair.TryGetValue((bnd, enc), out var recs) && recs.Count > 0)
                        {
                            sb.Append($" {(int)recs.Average(r => r.ObservationTokens):N0} |");
                        }
                        else
                        {
                            sb.Append(" N/A |");
                        }
                    }
                    sb.AppendLine();
                }
                sb.AppendLine();
            }

            // Assumption violations
            var assumptionViolations = new List<string>();
            if (noneViolations.Count > 0)
            {
                assumptionViolations.Add($"NONE-target succeeded: {string.Join(", ", noneViolations.Select(r => $"{r.TaskId}/{r.Bundle}×{r.Encoding}"))}");
            }

            if (xpathRecords.Count > 0)
            {
                assumptionViolations.Add($"XPath output despite CSS-only instruction: {xpathRecords.Count} record(s)");
            }

            var shadowXpathFails = allFlat.Where(r => r.FailureMode == "output_format_unreachable").ToList();
            if (shadowXpathFails.Count > 0)
            {
                assumptionViolations.Add($"output_format_unreachable (XPath on shadow target): {shadowXpathFails.Count} record(s)");
            }

            if (assumptionViolations.Count > 0)
            {
                sb.AppendLine("### ⚠ Assumption violations");
                foreach (var v in assumptionViolations)
                {
                    sb.AppendLine($"- {v}");
                }

                sb.AppendLine();
            }
        }

        var summaryTag = DateTimeOffset.UtcNow.ToString("yyyyMMdd");
        var summaryPath = Path.Combine(runsDir, $"summary_{summaryTag}.md");
        await File.WriteAllTextAsync(summaryPath, sb.ToString());
        Console.WriteLine($"  Summary written → experiments/runs/summary_{summaryTag}.md");
    }
}
