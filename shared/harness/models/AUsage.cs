using System.Text.Json.Serialization;

namespace BoundedAgents.Shared.Harness;

public static partial class LlmClient
{
    private record AUsage(
        [property: JsonPropertyName("input_tokens")] int InputTokens,
        [property: JsonPropertyName("output_tokens")] int OutputTokens
    );
}
