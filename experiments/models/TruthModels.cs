using System.Text.Json.Serialization;

// ── Truth deserialization types ───────────────────────────────────────────
// Global-namespace internal types shared by the driver loop and the run modes.

internal record VolatilityLabels(
    [property: JsonPropertyName("volatile_ids")] string[] VolatileIds,
    [property: JsonPropertyName("volatile_classes")] string[] VolatileClasses
);

internal record TruthTarget(
    [property: JsonPropertyName("id")] string Id,
    [property: JsonPropertyName("intent")] string Intent,
    [property: JsonPropertyName("oracle")] string Oracle,
    [property: JsonPropertyName("expected_stable_signal")] string ExpectedStableSignal,
    [property: JsonPropertyName("is_ambiguous")] bool IsAmbiguous,
    [property: JsonPropertyName("signal_attrs")] string[] SignalAttrs
);

internal record TruthFile(
    [property: JsonPropertyName("volatility_labels")] VolatilityLabels VolatilityLabels,
    [property: JsonPropertyName("targets")] TruthTarget[] Targets,
    [property: JsonPropertyName("shadow")] string? Shadow = null
);
