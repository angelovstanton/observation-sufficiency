using System.Text.Json.Serialization;

// ── Predicate control record types ───────────────────────────────────────
// Consumed by the predicate controls mode.

internal record ControlExpected(
    [property: JsonPropertyName("success")] bool Success,
    [property: JsonPropertyName("failure_mode")] string? FailureMode,
    [property: JsonPropertyName("non_volatile")] bool NonVolatile,
    [property: JsonPropertyName("non_positional")] bool NonPositional,
    [property: JsonPropertyName("stable_signal_present")] bool StableSignalPresent
);

internal record ControlRecord(
    [property: JsonPropertyName("label")] string Label,
    [property: JsonPropertyName("page_id")] string PageId,
    [property: JsonPropertyName("oracle_id")] string OracleId,
    [property: JsonPropertyName("locator_type")] string LocatorType,
    [property: JsonPropertyName("locator_value")] string LocatorValue,
    [property: JsonPropertyName("dimension")] string Dimension,
    [property: JsonPropertyName("direction")] string Direction,
    [property: JsonPropertyName("expected")] ControlExpected Expected,
    [property: JsonPropertyName("bundle")] string? Bundle = null,
    [property: JsonPropertyName("rationale")] string Rationale = ""
);
