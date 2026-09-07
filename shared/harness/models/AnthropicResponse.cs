using System.Text.Json.Serialization;

namespace BoundedAgents.Shared.Harness;

public static partial class LlmClient
{
    private record AnthropicResponse(
        [property: JsonPropertyName("content")] AContentBlock[] Content,
        [property: JsonPropertyName("usage")] AUsage Usage
    );
}
