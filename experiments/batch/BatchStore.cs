using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using BoundedAgents.Models;
using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;

namespace BoundedAgents.Experiments.Batch;

/// <summary>Strict JSONL: every line a JSON object, file ends with '\n'. Anything else refuses.</summary>
internal static class StrictJsonl
{
    public static List<JsonObject> Read(string path)
    {
        var list = new List<JsonObject>();
        if (!File.Exists(path))
        {
            return list;
        }
        var text = File.ReadAllText(path, Encoding.UTF8);
        if (text.Length == 0)
        {
            return list;
        }
        if (!text.EndsWith('\n'))
        {
            throw new BatchRefusedException(
                $"{Path.GetFileName(path)}: last line is partial (no trailing newline) — refusing; inspect by hand");
        }
        var lines = text[..^1].Split('\n');
        for (int i = 0; i < lines.Length; i++)
        {
            JsonObject? obj = null;
            try
            {
                obj = JsonNode.Parse(lines[i]) as JsonObject;
            }
            catch (JsonException) { }
            if (obj is null)
            {
                throw new BatchRefusedException(
                    $"{Path.GetFileName(path)}:{i + 1}: not a JSON object — refusing; inspect by hand");
            }
            list.Add(obj);
        }
        return list;
    }

    /// <summary>Append one line and flush it to disk before returning.</summary>
    public static void AppendDurable(string path, JsonObject obj)
    {
        var bytes = Encoding.UTF8.GetBytes(obj.ToJsonString() + "\n");
        using var fs = new FileStream(path, FileMode.Append, FileAccess.Write, FileShare.Read);
        fs.Write(bytes);
        fs.Flush(flushToDisk: true);
    }
}

/// <summary>Exclusive lock on the output directory for the whole run (released by the OS on exit).</summary>
public sealed class BatchLock : IDisposable
{
    private readonly FileStream _fs;

    private BatchLock(FileStream fs) => _fs = fs;

    public static BatchLock Acquire(string outDir)
    {
        var path = Path.Combine(outDir, ".lock");
        try
        {
            var fs = new FileStream(path, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
            fs.SetLength(0);
            var stamp = Encoding.UTF8.GetBytes($"pid={Environment.ProcessId} started={DateTimeOffset.UtcNow:O}\n");
            fs.Write(stamp);
            fs.Flush(flushToDisk: true);
            return new BatchLock(fs);
        }
        catch (IOException ex)
        {
            throw new BatchRefusedException($"another batch runner holds {path} ({ex.Message})");
        }
    }

    public void Dispose() => _fs.Dispose();
}

/// <summary>What every journal entry and record must agree with (all from the passed preflight).</summary>
public sealed class BatchExpectations
{
    public required string PlanSha256 { get; init; }
    public required IReadOnlyDictionary<string, PlanEvent> Plan { get; init; }
    public required IReadOnlyDictionary<string, string> Deployments { get; init; }
    public required IReadOnlyDictionary<(string Page, string Bundle, string Encoding), string> ObservationSha { get; init; }
    public required IReadOnlyDictionary<(string Page, string Bundle, string Encoding), int> ObservationTokens { get; init; }

    // Pilot profile only; the defaults keep the batch profile's behaviour.
    /// <summary>The record's page / testbed_page value (batch: pages/page_NN.html; pilot: the site key).</summary>
    public Func<PlanEvent, string> PagePathOf { get; init; } = e => $"pages/{e.Page}.html";
    /// <summary>Events not called: class_only key → (its event, the called event whose result it reuses).</summary>
    public IReadOnlyDictionary<string, ReusedEvent> Reused { get; init; } = new Dictionary<string, ReusedEvent>();
    /// <summary>Completion tokens the budget model reserves per call; a response above it is an overrun.</summary>
    public long? MaxCompletionTokens { get; init; }
    /// <summary>Records carry the reuse marker fields (<see cref="BatchRecords.ReuseFields"/>).</summary>
    public bool MarksReuse { get; init; }

    public string DeploymentOf(PlanEvent e) => Deployments[e.Model];
    public string ObservationShaOf(PlanEvent e) => ObservationSha[(e.Page, e.Bundle, e.Encoding)];
    public int ObservationTokensOf(PlanEvent e) => ObservationTokens[(e.Page, e.Bundle, e.Encoding)];

    public static BatchExpectations From(PreflightResult pf, string planSha) => new()
    {
        PlanSha256 = planSha,
        Plan = pf.AllEvents.ToDictionary(e => e.Key, StringComparer.Ordinal),
        Deployments = pf.Deployments,
        ObservationSha = pf.ExpectedObservationSha,
        ObservationTokens = pf.ExpectedObservationTokens,
    };
}

/// <summary>A planned cell that is not called: its result is the called <paramref name="SourceKey"/>'s.</summary>
public sealed record ReusedEvent(PlanEvent Event, string SourceKey);

/// <summary>Typed field access that refuses on a missing key or a wrong JSON type.</summary>
internal static class Field
{
    public static string Str(JsonObject o, string name, string where)
    {
        if (o.TryGetPropertyValue(name, out var n) && n is JsonValue v
            && v.GetValueKind() == JsonValueKind.String && v.TryGetValue<string>(out var s))
        {
            return s;
        }
        throw new BatchRefusedException($"{where}: '{name}' missing or not a string");
    }

    public static string NonEmpty(JsonObject o, string name, string where)
    {
        var s = Str(o, name, where);
        return s.Length > 0 ? s : throw new BatchRefusedException($"{where}: '{name}' is empty");
    }

    public static string? StrOrNull(JsonObject o, string name, string where)
    {
        if (!o.TryGetPropertyValue(name, out var n))
        {
            throw new BatchRefusedException($"{where}: '{name}' missing");
        }
        return n is null ? null : Str(o, name, where);
    }

    public static long Long(JsonObject o, string name, string where, long min)
    {
        if (o.TryGetPropertyValue(name, out var n) && n is JsonValue v
            && v.GetValueKind() == JsonValueKind.Number && v.TryGetValue<long>(out var x))
        {
            return x >= min ? x : throw new BatchRefusedException($"{where}: '{name}' = {x} < {min}");
        }
        throw new BatchRefusedException($"{where}: '{name}' missing or not an integer");
    }

    public static int Int(JsonObject o, string name, string where, int min) => checked((int)Long(o, name, where, min));

    public static bool Bool(JsonObject o, string name, string where)
    {
        if (o.TryGetPropertyValue(name, out var n) && n is JsonValue v
            && v.GetValueKind() is JsonValueKind.True or JsonValueKind.False)
        {
            return v.GetValue<bool>();
        }
        throw new BatchRefusedException($"{where}: '{name}' missing or not a boolean");
    }

    public static void Expect<T>(T actual, T expected, string name, string where)
    {
        if (!EqualityComparer<T>.Default.Equals(actual, expected))
        {
            throw new BatchRefusedException(
                $"{where}: '{name}' = {actual?.ToString() ?? "null"}, expected {expected?.ToString() ?? "null"}");
        }
    }
}

/// <summary>
/// Append-only journal of paid requests (batch_runs/journal.jsonl). Written before the call
/// ("pending") and immediately after the response ("response"), each line flushed to disk,
/// so a paid answer survives any later crash and is never bought twice.
///
/// Every entry is checked on load and on append: typed fields, plan hash, the event's deployment
/// and pinned observation hash, and the state transition per key:
///   start → pending(1); pending(a) → response(a) | rejected_429(a) | error(a) | released(a);
///   rejected_429(a) → pending(a+1); error(a) → released(a); released(a) → pending(a+1);
///   response(a) → budget_overrun(a) | overrun_released(a)   (only if usage > the pending's reservation);
///   budget_overrun(a) → overrun_released(a). Anything else refuses the whole run.
/// An overrun (native prompt_tokens above the reservation of its pending, or, pilot only, completion
/// tokens above the reserved maximum) is derived from the journal itself, so it survives a crash
/// before the budget_overrun line; it stays open, and blocks every later start, until an explicit
/// overrun_released.
/// A released request with unknown outcome may have been billed: the reservation of its pending stays a
/// budget liability (<see cref="ReleasedReservations"/>; real_pilot/pilot_addendum_scoring.md (б)).
/// </summary>
public sealed class BatchJournal
{
    public const string Pending = "pending";
    public const string Response = "response";
    public const string Rejected429 = "rejected_429";
    public const string Error = "error";
    public const string Released = "released";
    public const string BudgetOverrun = "budget_overrun";
    public const string OverrunReleased = "overrun_released";

    private readonly string _path;
    private readonly BatchExpectations _x;
    private readonly Dictionary<string, JsonObject> _responses = new(StringComparer.Ordinal);
    private readonly Dictionary<string, (string Type, int Attempt)> _last = new(StringComparer.Ordinal);
    private readonly Dictionary<string, long> _reservation = new(StringComparer.Ordinal);
    private readonly HashSet<string> _openOverruns = new(StringComparer.Ordinal);
    private readonly List<long> _released = new();

    public long SpentInputTokens { get; private set; }

    /// <summary>Native completion tokens of all responses (the pilot's cost ledger; the batch budget is input only).</summary>
    public long SpentCompletionTokens { get; private set; }

    private BatchJournal(string path, BatchExpectations x)
    {
        _path = path;
        _x = x;
    }

    public static BatchJournal Load(string outDir, BatchExpectations x)
    {
        var j = new BatchJournal(Path.Combine(outDir, "journal.jsonl"), x);
        int n = 0;
        foreach (var e in StrictJsonl.Read(j._path))
        {
            n++;
            j.Apply(e, $"journal.jsonl:{n}");
        }
        return j;
    }

    /// <summary>Validate one entry against the plan and the key's current state, then record it.</summary>
    private void Apply(JsonObject e, string where)
    {
        var type = Field.Str(e, "type", where);
        var key = Field.Str(e, "key", where);
        Field.Expect(Field.Str(e, "plan_sha256", where), _x.PlanSha256, "plan_sha256", where);
        Field.NonEmpty(e, "ts", where);
        if (!_x.Plan.TryGetValue(key, out var ev))
        {
            throw new BatchRefusedException($"{where}: key {key} is not in the plan");
        }
        var attempt = Field.Int(e, "attempt", where, 1);
        var deployment = _x.DeploymentOf(ev);

        switch (type)
        {
            case Pending:
                Field.Expect(Field.Str(e, "deployment", where), deployment, "deployment", where);
                Field.Expect(Field.Str(e, "observation_sha256", where), _x.ObservationShaOf(ev), "observation_sha256", where);
                Field.Long(e, "reservation", where, 1);
                break;
            case Response:
                Field.Expect(Field.Str(e, "deployment", where), deployment, "deployment", where);
                Field.Expect(Field.Str(e, "model_id", where), deployment, "model_id", where);
                Field.Expect(Field.Str(e, "observation_sha256", where), _x.ObservationShaOf(ev), "observation_sha256", where);
                Field.Str(e, "locator_raw", where);
                Field.Long(e, "prompt_tokens", where, 1);
                Field.Long(e, "completion_tokens", where, 0);
                Field.NonEmpty(e, "response_model", where);
                Field.NonEmpty(e, "finish_reason", where);
                Field.StrOrNull(e, "system_fingerprint", where);
                break;
            case Rejected429:
                Field.Long(e, "retry_after_ms", where, 0);
                break;
            case Error:
                Field.Str(e, "message", where);
                break;
            case Released:
                Field.NonEmpty(e, "reason", where);
                break;
            case BudgetOverrun:
                Field.Long(e, "prompt_tokens", where, 1);
                Field.Long(e, "reservation", where, 1);
                break;
            case OverrunReleased:
                Field.NonEmpty(e, "reason", where);
                break;
            default:
                throw new BatchRefusedException($"{where}: unknown entry type '{type}'");
        }

        bool ok;
        if (_last.TryGetValue(key, out var last))
        {
            ok = (last.Type, type) switch
            {
                (Pending, Response or Rejected429 or Error or Released) => attempt == last.Attempt,
                (Rejected429, Pending) or (Released, Pending) => attempt == last.Attempt + 1,
                (Error, Released) => attempt == last.Attempt,
                (Response, BudgetOverrun or OverrunReleased) => attempt == last.Attempt && _openOverruns.Contains(key),
                (BudgetOverrun, OverrunReleased) => attempt == last.Attempt,
                _ => false,
            };
        }
        else
        {
            ok = type == Pending && attempt == 1;
        }
        if (!ok)
        {
            var from = _last.TryGetValue(key, out var l) ? $"{l.Type}({l.Attempt})" : "start";
            throw new BatchRefusedException($"{where}: invalid transition {from} → {type}({attempt}) for {key}");
        }

        if (type == BudgetOverrun)
        {
            // The line must restate the numbers the journal already holds.
            Field.Expect(Field.Long(e, "prompt_tokens", where, 1), Field.Long(_responses[key], "prompt_tokens", where, 1),
                         "prompt_tokens", where);
            Field.Expect(Field.Long(e, "reservation", where, 1), _reservation[key], "reservation", where);
        }
        if (type is Released or OverrunReleased)
        {
            // Fields added by real_pilot/pilot_addendum_scoring.md (б). The batch journal predates them;
            // there the values come from the pending / response being released.
            if (e.ContainsKey("reservation"))
            {
                Field.Expect(Field.Long(e, "reservation", where, 1), _reservation[key], "reservation", where);
            }
            if (type == OverrunReleased)
            {
                foreach (var f in new[] { "prompt_tokens", "completion_tokens" })
                {
                    if (e.ContainsKey(f))
                    {
                        Field.Expect(Field.Long(e, f, where, 0), Field.Long(_responses[key], f, where, 0), f, where);
                    }
                }
            }
        }

        _last[key] = (type, attempt);
        switch (type)
        {
            case Pending:
                _reservation[key] = Field.Long(e, "reservation", where, 1);
                break;
            case Response:
                _responses[key] = e;
                var used = Field.Long(e, "prompt_tokens", where, 1);
                var completion = Field.Long(e, "completion_tokens", where, 0);
                SpentInputTokens += used;
                SpentCompletionTokens += completion;
                if (used > _reservation[key] || (_x.MaxCompletionTokens is long maxOut && completion > maxOut))
                {
                    _openOverruns.Add(key);
                }
                break;
            case Released:
                // The released request may have been billed: its reservation stays a budget liability.
                _released.Add(_reservation[key]);
                break;
            case OverrunReleased:
                _openOverruns.Remove(key);
                break;
        }
    }

    /// <summary>
    /// The reservation (input tokens) of every released request with unknown outcome, in journal order: a budget
    /// liability (the request may have been billed), counted by <see cref="BudgetModel.Liability"/>. An overrun
    /// release adds nothing here — its usage is known and already counted with its response.
    /// </summary>
    public IReadOnlyList<long> ReleasedReservations => _released;

    /// <summary>Keys whose native usage exceeded their reservation and were not explicitly released.</summary>
    public IReadOnlyList<string> OpenOverruns() =>
        _openOverruns.OrderBy(k => k, StringComparer.Ordinal).ToList();

    /// <summary>The reservation recorded with the key's latest pending.</summary>
    public long ReservationOf(string key) => _reservation[key];

    public JsonObject? ResponseFor(string key) => _responses.GetValueOrDefault(key);

    /// <summary>The attempt number the next request for this key must carry.</summary>
    public int NextAttempt(string key) => _last.TryGetValue(key, out var l) ? l.Attempt + 1 : 1;

    public int LastAttempt(string key) => _last.TryGetValue(key, out var l) ? l.Attempt : 0;

    /// <summary>Keys whose last request has no known outcome (pending without response, or error).</summary>
    public IReadOnlyList<string> UnknownKeys() =>
        _last.Where(kv => kv.Value.Type is Pending or Error)
             .Select(kv => kv.Key).OrderBy(k => k, StringComparer.Ordinal).ToList();

    public void Append(string type, string key, JsonObject fields)
    {
        var e = new JsonObject
        {
            ["type"] = type,
            ["key"] = key,
            ["plan_sha256"] = _x.PlanSha256,
            ["ts"] = DateTimeOffset.UtcNow.ToString("O"),
        };
        foreach (var (k, v) in fields)
        {
            e[k] = v?.DeepClone();
        }
        // The writer obeys the reader's rules: an entry that would not load is never written.
        var probe = (JsonObject)JsonNode.Parse(e.ToJsonString())!;
        Apply(probe, $"journal append ({type} {key})");
        StrictJsonl.AppendDurable(_path, probe);
    }
}

/// <summary>Score fields of a record, as recomputed from the stored locator.</summary>
public sealed record BatchScore(
    string ObservationSha256, int ObservationTokens, string LocatorType, string LocatorValue,
    bool Success, string? FailureMode, bool PredicateUniqueMatch, bool PredicateMatchesOracle,
    bool PredicateNonVolatile, bool PredicateNonPositional, bool StableSignalPresentInBundle);

/// <summary>Output shards: strict semantic load; a record counts as done only if it agrees with
/// the plan, the pinned observation and its journaled response.</summary>
public static class BatchRecords
{
    public static readonly string[] ExtraFields =
    {
        "rep", "block", "event_key", "plan_sha256", "observation_sha256",
        "response_model_id", "finish_reason", "system_fingerprint", "llm_attempts", "replayed_from_journal",
    };

    public static readonly string[] RecordFields =
        typeof(GroundingRecord).GetConstructors().Single().GetParameters()
            .Select(p => JsonNamingPolicy.SnakeCaseLower.ConvertName(p.Name!))
            .Concat(ExtraFields).ToArray();

    /// <summary>Pilot only: reused (bool) and reused_from_event_key (the called event, or null).</summary>
    public static readonly string[] ReuseFields = { "reused", "reused_from_event_key" };

    /// <summary>
    /// Pilot only (addendum (а′) point 4): loads used by the scoring checkpoint, the mutation window's count of each
    /// (in order; the last is 0) and ms from the start of the accepted load to the end of its evaluation.
    /// </summary>
    public static readonly string[] ScoringFields = { "scoring_attempts", "scoring_mutations", "scoring_ms" };

    public static IReadOnlyList<string> RecordFieldsOf(BatchExpectations x) =>
        x.MarksReuse ? RecordFields.Concat(ReuseFields).Concat(ScoringFields).ToArray() : RecordFields;

    private static readonly JsonSerializerOptions StrictRecord = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        RespectNullableAnnotations = true,
        RespectRequiredConstructorParameters = true,
    };

    public static string ShardPath(string outDir, PlanEvent e, string deployment) =>
        Path.Combine(outDir, $"batch_{e.Block}_{deployment.Replace('.', '-')}_{e.Page}.jsonl");

    /// <summary>Complete, consistent records by event key. Any doubt refuses the whole run.</summary>
    public static Dictionary<string, JsonObject> LoadDone(string outDir, BatchExpectations x, BatchJournal journal)
    {
        var done = new Dictionary<string, JsonObject>(StringComparer.Ordinal);
        foreach (var path in Directory.GetFiles(outDir, "batch_*.jsonl").Order(StringComparer.Ordinal))
        {
            var name = Path.GetFileName(path);
            int n = 0;
            foreach (var r in StrictJsonl.Read(path))
            {
                n++;
                var where = $"{name}:{n}";
                var missing = RecordFieldsOf(x).Where(f => !r.ContainsKey(f)).ToList();
                if (missing.Count > 0)
                {
                    throw new BatchRefusedException($"{where}: incomplete record (missing {string.Join(",", missing)})");
                }
                var key = Field.Str(r, "event_key", where);
                string? source = null;
                if (!x.Plan.TryGetValue(key, out var e))
                {
                    if (!x.Reused.TryGetValue(key, out var re))
                    {
                        throw new BatchRefusedException($"{where}: event_key {key} not in the plan");
                    }
                    (e, source) = (re.Event, re.SourceKey);
                }
                Validate(r, e, x, journal, where, source);
                if (Path.GetFileName(ShardPath(outDir, e, x.DeploymentOf(e))) != name)
                {
                    throw new BatchRefusedException($"{where}: record for {key} is in the wrong shard");
                }
                if (!done.TryAdd(key, r))
                {
                    throw new BatchRefusedException($"{where}: duplicate record for {key}");
                }
            }
        }
        return done;
    }

    private static GroundingRecord Typed(JsonObject r, string where)
    {
        try
        {
            return JsonSerializer.Deserialize<GroundingRecord>(r.ToJsonString(), StrictRecord)
                   ?? throw new BatchRefusedException($"{where}: null record");
        }
        catch (JsonException ex)
        {
            throw new BatchRefusedException($"{where}: record has a wrong type ({ex.Message})");
        }
    }

    private static void Validate(JsonObject r, PlanEvent e, BatchExpectations x, BatchJournal journal, string where,
                                 string? reusedFrom = null)
    {
        var g = Typed(r, where);
        var dep = x.DeploymentOf(e);

        // Identity vs the plan and the pinned apparatus.
        Field.Expect(g.Model, dep, "model", where);
        Field.Expect(g.Bundle, e.Bundle, "bundle", where);
        Field.Expect(g.Encoding, e.Encoding, "encoding", where);
        Field.Expect(g.TaskId, e.TaskId, "task_id", where);
        Field.Expect(g.Page, x.PagePathOf(e), "page", where);
        Field.Expect(g.TestbedPage, x.PagePathOf(e), "testbed_page", where);
        Field.Expect(g.Repetition, e.Repetition, "repetition", where);
        Field.Expect(g.Regime, "full_page", "regime", where);
        Field.Expect(g.TokenizerVersion, TokenCounter.TokenizerVersion(), "tokenizer_version", where);
        Field.Expect(g.SchemaVersion, GroundingRunner.SchemaVersion, "schema_version", where);
        Field.Expect(g.Seed, Config.RandomSeed, "seed", where);
        Field.Expect(g.ObservationTokens, x.ObservationTokensOf(e), "observation_tokens", where);
        Field.Expect(Field.Int(r, "rep", where, 1), e.Rep, "rep", where);
        Field.Expect(Field.Str(r, "block", where), e.Block, "block", where);
        Field.Expect(Field.Str(r, "plan_sha256", where), x.PlanSha256, "plan_sha256", where);
        Field.Expect(Field.Str(r, "observation_sha256", where), x.ObservationShaOf(e), "observation_sha256", where);
        Field.Bool(r, "replayed_from_journal", where);
        if (x.MarksReuse)
        {
            Field.Expect(Field.Bool(r, "reused", where), reusedFrom is not null, "reused", where);
            Field.Expect(Field.StrOrNull(r, "reused_from_event_key", where), reusedFrom, "reused_from_event_key", where);
            if (reusedFrom is not null)
            {
                Field.Expect(Field.Bool(r, "replayed_from_journal", where), false, "replayed_from_journal", where);
            }
            var attempts = Field.Int(r, "scoring_attempts", where, 1);
            var counts = r["scoring_mutations"] as JsonArray
                         ?? throw new BatchRefusedException($"{where}: scoring_mutations is not an array");
            if (attempts > ScoringCheckpoint.MaxLoads || counts.Count != attempts
                || counts.Any(c => c is not JsonValue v || !v.TryGetValue<int>(out var i) || i < -1)
                || counts[^1]!.GetValue<int>() != 0)
            {
                throw new BatchRefusedException(
                    $"{where}: scoring_attempts / scoring_mutations disagree with the scoring checkpoint");
            }
            Field.Long(r, "scoring_ms", where, 0);
        }

        // Record vs its journaled response (a reused record: the response of the event it reuses).
        var respKey = reusedFrom ?? e.Key;
        var resp = journal.ResponseFor(respKey)
                   ?? throw new BatchRefusedException($"{where}: record for {respKey} has no journaled response");
        Field.Expect(g.LocatorRaw, Field.Str(resp, "locator_raw", "response"), "locator_raw", where);
        Field.Expect((long)g.PromptTokensTotal, Field.Long(resp, "prompt_tokens", "response", 1), "prompt_tokens_total", where);
        Field.Expect((long)g.CompletionTokens, Field.Long(resp, "completion_tokens", "response", 0), "completion_tokens", where);
        Field.Expect(g.ModelIdReturned, Field.Str(resp, "model_id", "response"), "model_id_returned", where);
        Field.Expect(Field.StrOrNull(r, "response_model_id", where), Field.Str(resp, "response_model", "response"), "response_model_id", where);
        Field.Expect(Field.StrOrNull(r, "finish_reason", where), Field.Str(resp, "finish_reason", "response"), "finish_reason", where);
        Field.Expect(Field.StrOrNull(r, "system_fingerprint", where), Field.StrOrNull(resp, "system_fingerprint", "response"), "system_fingerprint", where);
        Field.Expect(Field.Int(r, "llm_attempts", where, 1), Field.Int(resp, "attempt", "response", 1), "llm_attempts", where);

        // Score: the locator parse, and success / failure mode agree with the five predicates.
        var (lt, lv) = GroundingRunner.ParseLocatorForReplay(g.LocatorRaw);
        Field.Expect(g.LocatorType, lt, "locator_type", where);
        Field.Expect(g.LocatorValue, lv, "locator_value", where);
        var allFive = g.PredicateUniqueMatch && g.PredicateMatchesOracle && g.PredicateNonVolatile
                      && g.PredicateNonPositional && g.StableSignalPresentInBundle;
        Field.Expect(g.Success, allFive, "success (vs the five predicates)", where);
        Field.Expect(g.FailureMode is null, g.Success, "failure_mode null iff success", where);
    }

    /// <summary>The recorded score fields, for comparison with a recomputed <see cref="BatchScore"/>.</summary>
    public static BatchScore ScoreOf(JsonObject r)
    {
        var g = Typed(r, "record");
        return new BatchScore(r["observation_sha256"]!.GetValue<string>(), g.ObservationTokens, g.LocatorType,
            g.LocatorValue, g.Success, g.FailureMode, g.PredicateUniqueMatch, g.PredicateMatchesOracle,
            g.PredicateNonVolatile, g.PredicateNonPositional, g.StableSignalPresentInBundle);
    }
}
