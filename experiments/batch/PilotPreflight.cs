using System.Text.Json;
using BoundedAgents.Shared.Harness;

namespace BoundedAgents.Experiments.Batch;

/// <summary>
/// Static checks of the pilot profile before the lock and before any paid call. The first mismatch
/// throws <see cref="BatchRefusedException"/>; nothing is called, nothing is written. The batch
/// profile's checks (<see cref="BatchPreflight"/>) are not used here.
/// </summary>
public static class PilotPreflight
{
    /// <summary>The 9 batch_plan.json fields …</summary>
    private static readonly string[] BatchFields =
        { "block", "model", "model_env", "bundle", "encoding", "page", "task_id", "repetition", "rep" };

    /// <summary>… plus the 10 pilot fields (pilot_plan.json "fields"). Exactly these 19, no more, no less.</summary>
    private static readonly string[] PilotFields =
    {
        "event_key", "cell", "domain", "rank", "target_sha256_key", "xpath", "task", "stratum",
        "observation_sha256", "input_tokens",
    };

    private static readonly HashSet<string> IntFields = new(StringComparer.Ordinal) { "repetition", "rep", "rank", "input_tokens" };

    /// <summary>Code bundle → pilot cell label.</summary>
    public static readonly IReadOnlyDictionary<string, string> CellOf = new Dictionary<string, string>(StringComparer.Ordinal)
    {
        ["B_full"] = "B_full", ["B_noVolatileConsistent"] = "B_noVolatile", ["B_full_minus_volClass"] = "class_only",
    };

    private static readonly string[] Primary = { "B_full", "B_noVolatileConsistent" };
    private const string ClassOnly = "B_full_minus_volClass";
    private const string Nvc = "B_noVolatileConsistent";
    private static readonly string[] Encodings = { "F1", "F3" };

    public static PilotPlan Run(PilotOptions o)
    {
        // 1. Pinned files.
        var planBytes = Pinned(o.PlanPath, o.ExpectedPlanSha256, "pilot plan");
        var reuseBytes = Pinned(o.ReuseMapPath, o.ExpectedReuseMapSha256, "reuse map");
        var targetsBytes = Pinned(o.TargetsPath, o.ExpectedTargetsSha256, "targets.json");
        Pinned(o.ManifestPath, o.ExpectedManifestSha256, "observations manifest");
        var sitesBytes = Pinned(o.SitesPath, o.ExpectedSitesSha256, "pilot_sites.json");
        if (!File.Exists(o.ShimPath))
        {
            throw new BatchRefusedException($"shim not found: {o.ShimPath}");
        }
        var shimJs = File.ReadAllText(o.ShimPath);
        var shimSha = Hashing.Sha256Hex(shimJs.Replace("\r\n", "\n"));
        if (shimSha != o.ExpectedShimSha256)
        {
            throw new BatchRefusedException($"shim sha256 (LF) {shimSha} != pinned {o.ExpectedShimSha256}");
        }
        var prompt = BatchPins.PromptDigest();
        if (prompt != o.ExpectedPromptDigest)
        {
            throw new BatchRefusedException($"prompt digest {prompt} != audited {o.ExpectedPromptDigest}");
        }

        var targets = ParseTargets(targetsBytes);
        var manifest = ParseManifest(o.ManifestPath);
        var sites = ParseSites(sitesBytes, o.HtmlDir);
        var siteByKey = sites.ToDictionary(s => s.Key, StringComparer.Ordinal);

        // 2. Strict parse of the plan: exactly the 9 batch fields + the 10 pilot fields, typed.
        using var plan = Parse(planBytes, "pilot plan");
        var root = plan.RootElement;
        var events = new List<PlanEvent>();
        var info = new Dictionary<string, PilotEventInfo>(StringComparer.Ordinal);
        var plannedTokens = new Dictionary<string, int>(StringComparer.Ordinal);
        int n = 0;
        foreach (var ev in Arr(root, "events", "pilot plan"))
        {
            var where = $"pilot plan event #{n++}";
            var names = ev.EnumerateObject().Select(p => p.Name).ToList();
            var expected = BatchFields.Concat(PilotFields).ToHashSet(StringComparer.Ordinal);
            if (names.Count != expected.Count || !names.ToHashSet(StringComparer.Ordinal).SetEquals(expected))
            {
                throw new BatchRefusedException(
                    $"{where}: fields [{string.Join(",", names.Order(StringComparer.Ordinal))}] != " +
                    $"[{string.Join(",", expected.Order(StringComparer.Ordinal))}]");
            }
            foreach (var f in expected)
            {
                var kind = ev.GetProperty(f).ValueKind;
                if (IntFields.Contains(f) ? kind != JsonValueKind.Number || !ev.GetProperty(f).TryGetInt32(out _)
                                          : kind != JsonValueKind.String)
                {
                    throw new BatchRefusedException($"{where}: '{f}' is not {(IntFields.Contains(f) ? "an integer" : "a string")}");
                }
            }
            string S(string f) => ev.GetProperty(f).GetString()!;
            int I(string f) => ev.GetProperty(f).GetInt32();

            var e = new PlanEvent(S("block"), S("model"), S("model_env"), S("bundle"), S("encoding"),
                                  S("page"), S("task_id"), I("repetition"), I("rep"));
            // Same key formula as the batch (PlanEvent.Key).
            if (S("event_key") != e.Key)
            {
                throw new BatchRefusedException($"{where}: event_key '{S("event_key")}' != {e.Key}");
            }
            if (info.ContainsKey(e.Key))
            {
                throw new BatchRefusedException($"duplicate event key in pilot plan: {e.Key}");
            }
            if (e.Block != "pilot" || e.Repetition != 0 || e.Rep != e.Repetition + 1)
            {
                throw new BatchRefusedException($"{where}: block/repetition/rep {e.Block}/{e.Repetition}/{e.Rep} != pilot/0/1");
            }
            if (!o.AllowedCells.ContainsKey((e.Bundle, e.Encoding)))
            {
                throw new BatchRefusedException($"{where}: cell {e.Bundle}×{e.Encoding} outside the pilot cells");
            }
            if (S("cell") != CellOf[e.Bundle])
            {
                throw new BatchRefusedException($"{where}: cell label '{S("cell")}' != {CellOf[e.Bundle]} for {e.Bundle}");
            }
            if (!o.ModelEnv.TryGetValue(e.Model, out var slot) || slot != e.ModelEnv)
            {
                throw new BatchRefusedException($"{where}: model {e.Model} uses {e.ModelEnv}; pinned slot is {slot ?? "none"}");
            }

            // Page and task against pilot_sites.json, targets.json and the manifest (not page_NN / truth.json).
            var domain = S("domain");
            var rank = I("rank");
            if (!siteByKey.TryGetValue(e.Page, out var site) || site.Domain != domain || site.Rank != rank
                || e.Page != $"{rank:D4}_{domain}")
            {
                throw new BatchRefusedException($"{where}: page {e.Page} is not the site {rank:D4}_{domain} of pilot_sites.json");
            }
            if (!targets.TryGetValue((domain, e.TaskId), out var t))
            {
                throw new BatchRefusedException($"{where}: task {e.TaskId} of {domain} not in targets.json");
            }
            if (t.Rank != rank || t.Xpath != S("xpath") || t.Task != S("task") || t.Stratum != S("stratum")
                || t.Sha256Key != S("target_sha256_key"))
            {
                throw new BatchRefusedException($"{where}: target fields differ from targets.json ({domain} {e.TaskId})");
            }
            if (!manifest.TryGetValue((domain, e.Bundle, e.Encoding), out var m) || m.Sha != S("observation_sha256")
                || m.Rank != rank)
            {
                throw new BatchRefusedException(
                    $"{where}: observation_sha256 {S("observation_sha256")} != observations_manifest.tsv for {domain} {e.Bundle}×{e.Encoding}");
            }
            if (I("input_tokens") <= 0)
            {
                throw new BatchRefusedException($"{where}: input_tokens {I("input_tokens")} <= 0");
            }

            events.Add(e);
            info[e.Key] = new PilotEventInfo(e, S("cell"), site, t, I("input_tokens"));
            plannedTokens[e.Key] = I("input_tokens");
        }

        // 3. Counts and budget against the events and the pins.
        if (events.Count != o.PlannedCalls)
        {
            throw new BatchRefusedException($"pilot plan has {events.Count} events, pinned {o.PlannedCalls}");
        }
        var sumTokens = events.Sum(e => (long)plannedTokens[e.Key]);
        if (sumTokens != o.PlannedInputTokens)
        {
            throw new BatchRefusedException($"pilot plan input tokens {sumTokens:N0} != pinned {o.PlannedInputTokens:N0}");
        }
        foreach (var (cell, expected) in o.AllowedCells)
        {
            var actual = events.Count(e => (e.Bundle, e.Encoding) == cell);
            if (actual != expected)
            {
                throw new BatchRefusedException($"cell {cell.Bundle}×{cell.Encoding}: {actual} events, pinned {expected}");
            }
        }
        var counts = Obj(root, "counts", "pilot plan");
        if (counts.EnumerateObject().Count() != 1 || Long(counts, "pilot", "counts") != events.Count)
        {
            throw new BatchRefusedException("pilot plan 'counts' != {\"pilot\": events}");
        }
        var perCell = Obj(root, "per_cell", "pilot plan");
        foreach (var c in perCell.EnumerateObject())
        {
            var sel = events.Where(e => $"{CellOf[e.Bundle]}|{e.Encoding}" == c.Name).ToList();
            if (Long(c.Value, "calls", c.Name) != sel.Count
                || Long(c.Value, "input_tokens", c.Name) != sel.Sum(e => (long)plannedTokens[e.Key]))
            {
                throw new BatchRefusedException($"pilot plan per_cell[{c.Name}] disagrees with the events");
            }
        }
        if (perCell.EnumerateObject().Count() != o.AllowedCells.Count)
        {
            throw new BatchRefusedException("pilot plan per_cell does not list every cell");
        }
        var b = Obj(root, "budget", "pilot plan");
        if (Long(b, "planned_calls", "budget") != events.Count || Long(b, "planned_input_tokens", "budget") != sumTokens
            || Long(b, "max_output_tokens", "budget") != o.MaxCompletionTokens
            || Long(Obj(root, "settings", "pilot plan"), "max_output_tokens", "settings") != o.MaxCompletionTokens)
        {
            throw new BatchRefusedException("pilot plan budget (calls / input tokens / max_output_tokens) != events and pins");
        }
        var prices = Obj(b, "price_usd_per_1M", "budget");
        if (Dec(prices, "input", "price") != o.InputMicroUsdPerToken || Dec(prices, "output", "price") != o.OutputMicroUsdPerToken
            || Dec(b, "hard_cap_usd", "budget") * 1_000_000m != o.CapMicroUsd)
        {
            throw new BatchRefusedException(
                $"pilot plan prices / hard_cap_usd != pinned ({o.InputMicroUsdPerToken}/{o.OutputMicroUsdPerToken} µUSD per token, cap {o.CapMicroUsd:N0} µUSD)");
        }

        // 4. Reuse map: class_only cells not called, each byte-identical to a called B_noVolatile cell.
        using var reuseDoc = Parse(reuseBytes, "reuse map");
        var rr = reuseDoc.RootElement;
        if (Str(rr, "plan_sha256", "reuse map") != o.ExpectedPlanSha256 || Long(rr, "count", "reuse map") != o.ReusedCount
            || Long(root, "class_only_not_called", "pilot plan") != o.ReusedCount)
        {
            throw new BatchRefusedException("reuse map plan_sha256 / count or plan class_only_not_called != pins");
        }
        var reused = new Dictionary<string, ReusedEvent>(StringComparer.Ordinal);
        foreach (var r in Arr(rr, "reuse", "reuse map"))
        {
            var src = Str(r, "reused_event_key", "reuse");
            var key = Str(r, "class_only_event_key", "reuse");
            if (!info.TryGetValue(src, out var si) || si.Event.Bundle != Nvc)
            {
                throw new BatchRefusedException($"reuse {key}: source {src} is not a called {Nvc} event");
            }
            var se = si.Event;
            var e = se with { Bundle = ClassOnly };
            if (key != e.Key || info.ContainsKey(key) || reused.ContainsKey(key))
            {
                throw new BatchRefusedException($"reuse {key}: not the class_only twin of {src}, or called, or duplicate");
            }
            if (Str(r, "page", "reuse") != se.Page || Str(r, "task_id", "reuse") != se.TaskId
                || Str(r, "encoding", "reuse") != se.Encoding || Str(r, "domain", "reuse") != si.Site.Domain)
            {
                throw new BatchRefusedException($"reuse {key}: page/task/encoding/domain differ from {src}");
            }
            var co = manifest[(si.Site.Domain, ClassOnly, se.Encoding)].Sha;
            var nv = manifest[(si.Site.Domain, Nvc, se.Encoding)].Sha;
            if (co != nv || Str(r, "class_only_observation_sha256", "reuse") != co
                || Str(r, "b_novolatile_observation_sha256", "reuse") != nv)
            {
                throw new BatchRefusedException($"reuse {key}: observations are not byte-identical to {src} (manifest)");
            }
            reused[key] = new ReusedEvent(e, src);
            info[key] = si with { Event = e, Cell = CellOf[ClassOnly] };
        }
        if (reused.Count != o.ReusedCount)
        {
            throw new BatchRefusedException($"reuse map lists {reused.Count} cells, pinned {o.ReusedCount}");
        }

        // 5. Coverage: every target of an included site has its 4 primary cells and, per encoding,
        //    class_only either called or reused (exactly one); excluded sites have no events.
        var excluded = Arr(root, "excluded_sites", "pilot plan").Select(x => Str(x, "domain", "excluded_sites"))
                                                               .ToHashSet(StringComparer.Ordinal);
        var included = sites.Select(s => s.Domain).ToHashSet(StringComparer.Ordinal);
        if (included.Overlaps(excluded) || !targets.Keys.Select(k => k.Domain).ToHashSet(StringComparer.Ordinal)
                                                     .SetEquals(included.Union(excluded)))
        {
            throw new BatchRefusedException("targets.json sites != pilot_sites.json sites + excluded_sites");
        }
        if (!events.Select(e => e.Page).ToHashSet(StringComparer.Ordinal).SetEquals(sites.Select(s => s.Key)))
        {
            throw new BatchRefusedException("pilot plan pages != pilot_sites.json sites");
        }
        var includedTargets = targets.Values.Count(t => included.Contains(t.Domain));
        if (sites.Count != o.SiteCount || includedTargets != o.TargetCount)
        {
            throw new BatchRefusedException(
                $"pilot has {sites.Count} sites / {includedTargets} targets, pinned {o.SiteCount} / {o.TargetCount}");
        }
        foreach (var e in events.Where(e => e.Bundle == ClassOnly))
        {
            var d = info[e.Key].Site.Domain;
            if (manifest[(d, ClassOnly, e.Encoding)].Sha == manifest[(d, Nvc, e.Encoding)].Sha)
            {
                throw new BatchRefusedException($"{e.Key}: called, but its observation equals B_noVolatile's (reuse rule)");
            }
        }
        var byKey = new HashSet<string>(info.Keys, StringComparer.Ordinal);
        foreach (var t in targets.Values.Where(t => included.Contains(t.Domain)))
        {
            var page = $"{t.Rank:D4}_{t.Domain}";
            foreach (var enc in Encodings)
            {
                foreach (var bundle in Primary)
                {
                    if (!events.Any(e => e.Key == new PlanEvent("pilot", "gpt-4.1", "", bundle, enc, page, t.Marker, 0, 1).Key))
                    {
                        throw new BatchRefusedException($"{page} {t.Marker}: no {bundle}×{enc} event");
                    }
                }
                var co = new PlanEvent("pilot", "gpt-4.1", "", ClassOnly, enc, page, t.Marker, 0, 1).Key;
                if (!byKey.Contains(co))
                {
                    throw new BatchRefusedException($"{page} {t.Marker}: class_only×{enc} neither called nor reused");
                }
            }
        }

        // 6. Deployment slot → effective deployment == the event's model; Azure OpenAI route.
        var deployments = new Dictionary<string, string>(StringComparer.Ordinal);
        foreach (var model in events.Select(e => e.Model).Distinct())
        {
            var slot = o.ModelEnv[model];
            var effective = o.Env(slot);
            if (effective != model)
            {
                throw new BatchRefusedException($"{slot} = '{effective ?? "<unset>"}', but the pilot runs '{model}' on it");
            }
            if (!BatchPreflight.IsAzureOpenAiDeployment(effective))
            {
                throw new BatchRefusedException($"{effective} does not route to Azure OpenAI");
            }
            deployments[model] = effective;
        }

        // 7. The cap comes from the plan; the batch's knobs must not look as if they applied.
        foreach (var name in new[] { "BAR_BATCH_MAX_INPUT_TOKENS", "BAR_BATCH_BLOCKS" })
        {
            if (!string.IsNullOrEmpty(o.Env(name)))
            {
                throw new BatchRefusedException($"{name} is set — the pilot's cap is pilot_plan.json's hard cap and it has no blocks");
            }
        }

        // 8. Output stays out of experiments/runs.
        var outFull = Path.GetFullPath(o.OutDir).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var runsFull = Path.GetFullPath(Path.Combine(o.RepoRoot, "experiments", "runs")).TrimEnd(Path.DirectorySeparatorChar)
                       + Path.DirectorySeparatorChar;
        if (outFull.StartsWith(runsFull, StringComparison.OrdinalIgnoreCase))
        {
            throw new BatchRefusedException($"output directory {o.OutDir} is inside experiments/runs");
        }

        var obsSha = new Dictionary<(string, string, string), string>();
        var obsTok = new Dictionary<(string, string, string), int>();
        foreach (var s in sites)
        {
            foreach (var bundle in CellOf.Keys)
            {
                foreach (var enc in Encodings)
                {
                    if (!manifest.TryGetValue((s.Domain, bundle, enc), out var m))
                    {
                        throw new BatchRefusedException($"observations_manifest.tsv has no {s.Domain} {bundle}×{enc}");
                    }
                    obsSha[(s.Key, bundle, enc)] = m.Sha;
                    obsTok[(s.Key, bundle, enc)] = m.Tokens;
                }
            }
        }

        var x = new BatchExpectations
        {
            PlanSha256 = o.ExpectedPlanSha256,
            Plan = events.ToDictionary(e => e.Key, StringComparer.Ordinal),
            Deployments = deployments,
            ObservationSha = obsSha,
            ObservationTokens = obsTok,
            PagePathOf = e => e.Page,
            Reused = reused,
            MaxCompletionTokens = o.MaxCompletionTokens,
            MarksReuse = true,
        };
        var budget = new BudgetModel(
            "µUSD", "pilot hard cap (pilot_plan.json budget.hard_cap_usd)", "pilot cost cap", o.CapMicroUsd,
            j => j.SpentInputTokens * o.InputMicroUsdPerToken + j.SpentCompletionTokens * o.OutputMicroUsdPerToken,
            reservation => reservation * o.InputMicroUsdPerToken + o.MaxCompletionTokens * o.OutputMicroUsdPerToken);

        return new PilotPlan
        {
            Events = events,
            Reused = reused,
            Info = info,
            Sites = sites,
            TargetsBySite = sites.ToDictionary(
                s => s.Key, s => (IReadOnlyList<PilotTarget>)targets.Values.Where(t => t.Domain == s.Domain).ToList(),
                StringComparer.Ordinal),
            ObservationSha = obsSha,
            ObservationTokens = obsTok,
            Deployments = deployments,
            ShimJs = shimJs,
            PlannedInputTokens = sumTokens,
            Expectations = x,
            Budget = budget,
        };
    }

    /// <summary>The planned input tokens per called key (the runner checks the live count against it).</summary>
    public static IReadOnlyDictionary<string, int> PlannedInputTokensOf(PilotPlan p) =>
        p.Events.ToDictionary(e => e.Key, e => p.Info[e.Key].InputTokens, StringComparer.Ordinal);

    // Parsing
    private static byte[] Pinned(string path, string expected, string what)
    {
        if (!File.Exists(path))
        {
            throw new BatchRefusedException($"{what} not found: {path}");
        }
        var bytes = File.ReadAllBytes(path);
        var sha = Hashing.Sha256Hex(bytes);
        if (sha != expected)
        {
            throw new BatchRefusedException($"{what} sha256 {sha} != pinned {expected}");
        }
        return bytes;
    }

    private static JsonDocument Parse(byte[] bytes, string what)
    {
        try
        {
            return JsonDocument.Parse(bytes);
        }
        catch (JsonException ex)
        {
            throw new BatchRefusedException($"{what} is not valid JSON: {ex.Message}");
        }
    }

    private static JsonElement Prop(JsonElement o, string name, string where, JsonValueKind kind)
    {
        if (o.ValueKind != JsonValueKind.Object || !o.TryGetProperty(name, out var v) || v.ValueKind != kind)
        {
            throw new BatchRefusedException($"{where}: '{name}' missing or not {kind}");
        }
        return v;
    }

    private static JsonElement.ArrayEnumerator Arr(JsonElement o, string name, string where) =>
        Prop(o, name, where, JsonValueKind.Array).EnumerateArray();

    private static JsonElement Obj(JsonElement o, string name, string where) => Prop(o, name, where, JsonValueKind.Object);

    private static string Str(JsonElement o, string name, string where) => Prop(o, name, where, JsonValueKind.String).GetString()!;

    private static long Long(JsonElement o, string name, string where) =>
        Prop(o, name, where, JsonValueKind.Number).TryGetInt64(out var v)
            ? v : throw new BatchRefusedException($"{where}: '{name}' is not an integer");

    private static decimal Dec(JsonElement o, string name, string where) => Prop(o, name, where, JsonValueKind.Number).GetDecimal();

    private static Dictionary<(string Domain, string Marker), PilotTarget> ParseTargets(byte[] bytes)
    {
        using var doc = Parse(bytes, "targets.json");
        var d = new Dictionary<(string, string), PilotTarget>();
        foreach (var t in Arr(doc.RootElement, "items", "targets.json"))
        {
            var signal = Arr(t, "signal_attrs", "targets.json").Select(a => a.ValueKind == JsonValueKind.String
                ? a.GetString()! : throw new BatchRefusedException("targets.json: signal_attrs entry is not a string")).ToList();
            var pt = new PilotTarget(Str(t, "domain", "targets.json"), checked((int)Long(t, "rank", "targets.json")),
                                     Str(t, "marker", "targets.json"), Str(t, "xpath", "targets.json"),
                                     Str(t, "task", "targets.json"), Str(t, "stratum", "targets.json"), signal,
                                     Str(t, "sha256_key", "targets.json"));
            if (Hashing.Sha256Hex($"{pt.Domain}|{pt.Xpath}") != pt.Sha256Key)
            {
                throw new BatchRefusedException($"targets.json {pt.Domain} {pt.Marker}: sha256_key != sha256(domain|xpath)");
            }
            if (!d.TryAdd((pt.Domain, pt.Marker), pt))
            {
                throw new BatchRefusedException($"targets.json: duplicate marker {pt.Domain} {pt.Marker}");
            }
        }
        return d;
    }

    private static Dictionary<(string Domain, string Bundle, string Encoding), (int Rank, int Tokens, string Sha)> ParseManifest(string path)
    {
        var lines = File.ReadAllText(path).Split('\n');
        if (lines[0].TrimEnd('\r') != "domain\trank\tcell_bundle\tcode_bundle\tencoding\ttokens\tsha256")
        {
            throw new BatchRefusedException($"unexpected manifest header in {path}");
        }
        var d = new Dictionary<(string, string, string), (int, int, string)>();
        foreach (var raw in lines.Skip(1))
        {
            var line = raw.TrimEnd('\r');
            if (line.Length == 0)
            {
                continue;
            }
            var f = line.Split('\t');
            if (f.Length != 7 || f[6].Length != 64 || !int.TryParse(f[1], out var rank) || !int.TryParse(f[5], out var tok)
                || tok <= 0 || !CellOf.TryGetValue(f[3], out var label) || label != f[2] || !Encodings.Contains(f[4]))
            {
                throw new BatchRefusedException($"malformed manifest row in {path}: {line}");
            }
            if (!d.TryAdd((f[0], f[3], f[4]), (rank, tok, f[6])))
            {
                throw new BatchRefusedException($"duplicate manifest row in {path}: {line}");
            }
        }
        return d;
    }

    private static List<PilotSite> ParseSites(byte[] bytes, string htmlDir)
    {
        using var doc = Parse(bytes, "pilot_sites.json");
        var list = new List<PilotSite>();
        foreach (var s in Arr(doc.RootElement, "sites", "pilot_sites.json"))
        {
            var key = Str(s, "key", "pilot_sites.json");
            var where = $"pilot_sites.json {key}";
            var rank = checked((int)Long(s, "rank", where));
            var domain = Str(s, "domain", where);
            if (key != $"{rank:D4}_{domain}")
            {
                throw new BatchRefusedException($"{where}: key != rank_domain");
            }
            var tsEl = Prop(s, "timestamp", where, JsonValueKind.String);
            if (!tsEl.TryGetDateTime(out var ts) || ts.Kind != DateTimeKind.Utc)
            {
                throw new BatchRefusedException($"{where}: timestamp is not a UTC ISO time");
            }
            var file = Str(s, "html_file", where);
            if (file != Path.GetFileName(file) || file != $"{key}.html")
            {
                throw new BatchRefusedException($"{where}: html_file '{file}' is not {key}.html");
            }
            var html = Path.Combine(htmlDir, file);
            if (!File.Exists(html))
            {
                throw new BatchRefusedException($"{where}: HTML not found: {html}");
            }
            var htmlBytes = File.ReadAllBytes(html);
            var htmlSha = Str(s, "html_sha256", where);
            if (htmlBytes.Length != Long(s, "html_bytes", where) || Hashing.Sha256Hex(htmlBytes) != htmlSha)
            {
                throw new BatchRefusedException($"{where}: {html} sha256 {Hashing.Sha256Hex(htmlBytes)} != pinned {htmlSha}");
            }
            HashSet<string> Set(string name)
            {
                var v = Arr(s, name, where).Select(a => a.ValueKind == JsonValueKind.String
                    ? a.GetString()! : throw new BatchRefusedException($"{where}: {name} entry is not a string")).ToList();
                var set = v.ToHashSet(StringComparer.Ordinal);
                return set.Count == v.Count ? set : throw new BatchRefusedException($"{where}: duplicate in {name}");
            }
            list.Add(new PilotSite(key, rank, domain, Str(s, "url", where), ts, html, htmlSha, Set("vol_ids"), Set("vol_classes")));
        }
        if (list.Count != Long(doc.RootElement, "count", "pilot_sites.json")
            || list.Select(s => s.Key).Distinct(StringComparer.Ordinal).Count() != list.Count)
        {
            throw new BatchRefusedException("pilot_sites.json: count mismatch or duplicate site");
        }
        return list.OrderBy(s => s.Rank).ToList();
    }
}
