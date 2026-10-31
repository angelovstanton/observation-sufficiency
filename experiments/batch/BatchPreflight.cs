using System.Text.Json;

namespace BoundedAgents.Experiments.Batch;

/// <summary>Outcome of a passed preflight: the events to run and what each observation must hash to.</summary>
public sealed class PreflightResult
{
    public required IReadOnlyList<PlanEvent> AllEvents { get; init; }
    public required IReadOnlyList<PlanEvent> Selected { get; init; }
    public required IReadOnlySet<string> Blocks { get; init; }
    public required IReadOnlyDictionary<(string Page, string Bundle, string Encoding), string> ExpectedObservationSha { get; init; }
    public required IReadOnlyDictionary<(string Page, string Bundle, string Encoding), int> ExpectedObservationTokens { get; init; }
    public required IReadOnlyDictionary<string, string> Deployments { get; init; }
    public required long MaxInputTokens { get; init; }
}

/// <summary>
/// Static checks before the lock and before any paid call. The first mismatch throws
/// <see cref="BatchRefusedException"/>; nothing is called, nothing is written.
/// </summary>
public static class BatchPreflight
{
    private static readonly string[] EventFields =
        { "block", "model", "model_env", "bundle", "encoding", "page", "task_id", "repetition", "rep" };

    private static readonly HashSet<string> KnownBlocks = new(StringComparer.Ordinal) { "1", "2", "3", "4" };

    public static PreflightResult Run(BatchOptions o)
    {
        // 1. The plan is the pinned one.
        if (!File.Exists(o.PlanPath))
        {
            throw new BatchRefusedException($"plan not found: {o.PlanPath}");
        }
        var planBytes = File.ReadAllBytes(o.PlanPath);
        var planSha = Hashing.Sha256Hex(planBytes);
        if (planSha != o.ExpectedPlanSha256)
        {
            throw new BatchRefusedException($"plan sha256 {planSha} != audited {o.ExpectedPlanSha256}");
        }

        // 2. Strict parse.
        var events = ParseEvents(planBytes);

        // 3. Unique event keys (block excluded from the key on purpose).
        var dup = events.GroupBy(e => e.Key).FirstOrDefault(g => g.Count() > 1);
        if (dup is not null)
        {
            throw new BatchRefusedException($"duplicate event key in plan: {dup.Key} ×{dup.Count()}");
        }

        // 4. Allowed cells, exact counts, rep numbering, pages and tasks.
        var truth = new Dictionary<string, TruthFile>(StringComparer.Ordinal);
        foreach (var e in events)
        {
            var cell = new PlanCell(e.Block, e.Model, e.Bundle, e.Encoding, e.Rep);
            if (!o.AllowedCells.ContainsKey(cell))
            {
                throw new BatchRefusedException($"event outside the audited cells: {cell} ({e.Key})");
            }
            if (e.Rep != e.Repetition + 1)
            {
                throw new BatchRefusedException($"rep {e.Rep} != repetition {e.Repetition} + 1 ({e.Key})");
            }
            if (!IsTestbedPage(e.Page))
            {
                throw new BatchRefusedException($"page outside page_01..page_24: {e.Page}");
            }
            if (!truth.TryGetValue(e.Page, out var tf))
            {
                tf = LoadTruth(o.RepoRoot, e.Page);
                truth[e.Page] = tf;
            }
            if (!tf.Targets.Any(t => t.Id == e.TaskId))
            {
                throw new BatchRefusedException($"task {e.TaskId} not in {e.Page}.truth.json");
            }
        }
        var counts = events.GroupBy(e => new PlanCell(e.Block, e.Model, e.Bundle, e.Encoding, e.Rep))
                           .ToDictionary(g => g.Key, g => g.Count());
        foreach (var (cell, expected) in o.AllowedCells)
        {
            var actual = counts.GetValueOrDefault(cell);
            if (actual != expected)
            {
                throw new BatchRefusedException($"cell {cell}: {actual} events, audited {expected}");
            }
        }

        // 5. Model → env slot → effective deployment == the event's model; Azure OpenAI route.
        var deployments = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var e in events)
        {
            if (!o.ModelEnv.TryGetValue(e.Model, out var slot) || slot != e.ModelEnv)
            {
                throw new BatchRefusedException($"model {e.Model} uses {e.ModelEnv}; audited slot is {slot ?? "none"}");
            }
            if (deployments.ContainsKey(e.Model))
            {
                continue;
            }
            var effective = o.Env(slot);
            if (effective != e.Model)
            {
                throw new BatchRefusedException(
                    $"{slot} = '{effective ?? "<unset>"}', but the plan runs '{e.Model}' on it");
            }
            if (!IsAzureOpenAiDeployment(effective))
            {
                throw new BatchRefusedException($"{effective} does not route to Azure OpenAI");
            }
            deployments[e.Model] = effective;
        }

        // 6. Pages/truth, prompt, observation manifests.
        var pages = BatchPins.PagesDigest(o.RepoRoot);
        if (pages != o.ExpectedPagesDigest)
        {
            throw new BatchRefusedException($"testbed pages/truth digest {pages} != audited {o.ExpectedPagesDigest}");
        }
        var prompt = BatchPins.PromptDigest();
        if (prompt != o.ExpectedPromptDigest)
        {
            throw new BatchRefusedException($"prompt digest {prompt} != audited {o.ExpectedPromptDigest}");
        }
        var expectedObs = new Dictionary<(string, string, string), string>();
        var expectedTok = new Dictionary<(string, string, string), int>();
        foreach (var (path, pinned) in o.ObservationManifests)
        {
            if (!File.Exists(path))
            {
                throw new BatchRefusedException($"observation manifest missing: {path}");
            }
            var sha = Hashing.FileSha256(path);
            if (sha != pinned)
            {
                throw new BatchRefusedException($"manifest {path} sha256 {sha} != audited {pinned}");
            }
            foreach (var (k, v, tok) in ParseManifest(path))
            {
                if ((expectedObs.TryGetValue(k, out var other) && other != v)
                    || (expectedTok.TryGetValue(k, out var otherTok) && otherTok != tok))
                {
                    throw new BatchRefusedException($"manifests disagree on {k}: {other} vs {v}");
                }
                expectedObs[k] = v;
                expectedTok[k] = tok;
            }
        }

        // 7. Every planned cell has a pinned observation hash.
        var needed = new Dictionary<(string, string, string), string>();
        var neededTok = new Dictionary<(string, string, string), int>();
        foreach (var e in events)
        {
            var k = (e.Page, e.Bundle, e.Encoding);
            if (!expectedObs.TryGetValue(k, out var sha))
            {
                throw new BatchRefusedException($"no audited observation hash for {k}");
            }
            needed[k] = sha;
            neededTok[k] = expectedTok[k];
        }

        // 8. Mandatory input-token ceiling.
        var capRaw = o.Env("BAR_BATCH_MAX_INPUT_TOKENS");
        if (!long.TryParse(capRaw, out var cap) || cap <= 0)
        {
            throw new BatchRefusedException(
                $"BAR_BATCH_MAX_INPUT_TOKENS must be a positive integer (got '{capRaw ?? "<unset>"}')");
        }

        // 9. Output stays out of experiments/runs.
        var outFull = Path.GetFullPath(o.OutDir).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var runsFull = Path.GetFullPath(Path.Combine(o.RepoRoot, "experiments", "runs")).TrimEnd(Path.DirectorySeparatorChar)
                       + Path.DirectorySeparatorChar;
        if (outFull.StartsWith(runsFull, StringComparison.OrdinalIgnoreCase))
        {
            throw new BatchRefusedException($"output directory {o.OutDir} is inside experiments/runs");
        }

        // Block filter (subset only).
        var blocksRaw = o.Env("BAR_BATCH_BLOCKS");
        var blocks = string.IsNullOrWhiteSpace(blocksRaw)
            ? KnownBlocks.ToHashSet(StringComparer.Ordinal)
            : blocksRaw.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                       .ToHashSet(StringComparer.Ordinal);
        if (blocks.Count == 0 || !blocks.IsSubsetOf(KnownBlocks))
        {
            throw new BatchRefusedException($"BAR_BATCH_BLOCKS '{blocksRaw}' is not a subset of 1,2,3,4");
        }

        return new PreflightResult
        {
            AllEvents = events,
            Selected = events.Where(e => blocks.Contains(e.Block)).ToList(),
            Blocks = blocks,
            ExpectedObservationSha = needed,
            ExpectedObservationTokens = neededTok,
            Deployments = deployments,
            MaxInputTokens = cap,
        };
    }

    public static bool IsAzureOpenAiDeployment(string deployment) =>
        deployment.StartsWith("gpt-", StringComparison.OrdinalIgnoreCase) ||
        deployment.StartsWith("o4", StringComparison.OrdinalIgnoreCase);

    private static bool IsTestbedPage(string page) =>
        page.Length == 7 && page.StartsWith("page_", StringComparison.Ordinal)
        && int.TryParse(page[5..], out var n) && n is >= 1 and <= 24 && page == $"page_{n:D2}";

    internal static TruthFile LoadTruth(string repoRoot, string page) =>
        JsonSerializer.Deserialize<TruthFile>(
            File.ReadAllText(Path.Combine(repoRoot, "shared", "testbed", "pages", $"{page}.truth.json")),
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true })
        ?? throw new BatchRefusedException($"cannot read {page}.truth.json");

    private static List<PlanEvent> ParseEvents(byte[] planBytes)
    {
        JsonDocument doc;
        try
        {
            doc = JsonDocument.Parse(planBytes);
        }
        catch (JsonException ex)
        {
            throw new BatchRefusedException($"plan is not valid JSON: {ex.Message}");
        }
        using (doc)
        {
            if (!doc.RootElement.TryGetProperty("events", out var arr) || arr.ValueKind != JsonValueKind.Array)
            {
                throw new BatchRefusedException("plan has no 'events' array");
            }
            var list = new List<PlanEvent>();
            foreach (var e in arr.EnumerateArray())
            {
                var names = e.EnumerateObject().Select(p => p.Name).ToHashSet(StringComparer.Ordinal);
                if (!names.SetEquals(EventFields))
                {
                    throw new BatchRefusedException(
                        $"plan event #{list.Count} fields [{string.Join(",", names.Order())}] != [{string.Join(",", EventFields)}]");
                }
                string S(string n) => e.GetProperty(n).ValueKind == JsonValueKind.String
                    ? e.GetProperty(n).GetString()!
                    : throw new BatchRefusedException($"plan event #{list.Count}: '{n}' is not a string");
                int I(string n) => e.GetProperty(n).ValueKind == JsonValueKind.Number && e.GetProperty(n).TryGetInt32(out var v)
                    ? v
                    : throw new BatchRefusedException($"plan event #{list.Count}: '{n}' is not an integer");
                list.Add(new PlanEvent(S("block"), S("model"), S("model_env"), S("bundle"), S("encoding"),
                                       S("page"), S("task_id"), I("repetition"), I("rep")));
            }
            if (doc.RootElement.TryGetProperty("counts", out var countsEl))
            {
                foreach (var c in countsEl.EnumerateObject())
                {
                    var n = list.Count(x => x.Block == c.Name);
                    if (c.Value.GetInt32() != n)
                    {
                        throw new BatchRefusedException($"plan counts[{c.Name}] = {c.Value} but {n} events");
                    }
                }
            }
            return list;
        }
    }

    private static IEnumerable<((string, string, string) Key, string Sha, int Tokens)> ParseManifest(string path)
    {
        var lines = File.ReadAllLines(path);
        if (lines.Length == 0 || lines[0].TrimEnd('\r') != "page\tbundle\tencoding\ttokens\tsha256")
        {
            throw new BatchRefusedException($"unexpected manifest header in {path}");
        }
        foreach (var raw in lines.Skip(1))
        {
            var line = raw.TrimEnd('\r');
            if (line.Length == 0)
            {
                continue;
            }
            var f = line.Split('\t');
            if (f.Length != 5 || f[4].Length != 64 || !int.TryParse(f[3], out var tokens) || tokens <= 0)
            {
                throw new BatchRefusedException($"malformed manifest row in {path}: {line}");
            }
            yield return ((f[0], f[1], f[2]), f[4], tokens);
        }
    }
}
