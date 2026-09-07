using System.Text.Json.Serialization;

namespace BoundedAgents.Shared.Harness;

public static partial class LlmClient
{
    // ── Private DTO records for Anthropic JSON (de)serialization ─────────────

    private record AnthropicRequest(
        [property: JsonPropertyName("model")] string Model,
        [property: JsonPropertyName("max_tokens")] int MaxTokens,
        [property: JsonPropertyName("system")] string System,
        [property: JsonPropertyName("messages")] AMessage[] Messages
    );
}
