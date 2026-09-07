using System.Text.Json.Serialization;

namespace BoundedAgents.Shared.Harness;

public static partial class LlmClient
{
    private record AMessage(
        [property: JsonPropertyName("role")] string Role,
        [property: JsonPropertyName("content")] string Content
    );
}
