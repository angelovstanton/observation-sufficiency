namespace BoundedAgents.Shared.Oracle;

/// <summary>
/// A single DOM element after the JS walk. Attrs contains only the raw
/// attribute map; bundle filtering is applied by the harness before passing
/// filtered lists to the oracle.
/// </summary>
public record ElementData(
    string Tag,
    string Text,
    IReadOnlyDictionary<string, string> Attrs,
    bool IsInShadowRoot = false    // true when the element lives inside an open shadow root
);
