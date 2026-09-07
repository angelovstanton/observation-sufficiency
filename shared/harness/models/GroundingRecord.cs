using System.Text.Json;
using System.Text.Json.Serialization;

namespace BoundedAgents.Models;

// ---------------------------------------------------------------------------
// JSONL record — one per grounding event (§6)
// Field names use snake_case to match schema_version "1.0" established by
// the Python prototype. JsonNamingPolicy.SnakeCaseLower handles the mapping.
// ---------------------------------------------------------------------------

/// <param name="ObservationTokens">invariant cost metric; o200k_base for all models</param>
/// <param name="PromptTokensTotal">as-billed by the provider API; provider-specific tokenizer; informational only</param>
public record GroundingRecord(
    string RunId,
    string TaskId,
    string Page,
    string Bundle,
    string Encoding,
    string Regime,
    string Model,
    int Repetition,
    int ObservationTokens,
    int PromptTokensTotal,
    int CompletionTokens,
    string LocatorRaw,
    string LocatorType,
    string LocatorValue,
    bool Success,
    string? FailureMode,
    bool PredicateUniqueMatch,
    bool PredicateMatchesOracle,
    bool PredicateNonVolatile,
    bool PredicateNonPositional,
    bool StableSignalPresentInBundle,
    string ModelIdReturned,
    string TokenizerVersion,
    string SchemaVersion,
    string TestbedPage,
    string TimestampUtc,
    int Seed
)
{
    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        DefaultIgnoreCondition = JsonIgnoreCondition.Never,
        WriteIndented = false,
    };

    public string ToJsonl() => JsonSerializer.Serialize(this, JsonOpts);
}
