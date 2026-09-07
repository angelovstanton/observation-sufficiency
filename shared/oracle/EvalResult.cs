namespace BoundedAgents.Shared.Oracle;

/// <summary>
/// Result of the five-part success predicate (§6 + bundle-aware signal check).
/// All five must be true for success = true.
/// </summary>
public record EvalResult(
    bool Success,
    // null (success) | "observation_lacked_stable_signal" | "output_format_unreachable"
    // | "model_grabbed_brittle_signal".  Priority: lacked > unreachable > grabbed.
    string? FailureMode,
    bool PredicateUniqueMatch,
    bool PredicateMatchesOracle,
    bool PredicateNonVolatile,
    bool PredicateNonPositional,
    bool StableSignalPresentInBundle     // bundle-aware: at least one signal_attr survives in this bundle; [] (NONE) → always false
);
