using System.Text.Json.Serialization;

namespace BoundedAgents.Shared.Harness;

public static partial class LlmClient
{
    private record AContentBlock(
        [property: JsonPropertyName("type")] string Type,
        [property: JsonPropertyName("text")] string? Text
    );
}
