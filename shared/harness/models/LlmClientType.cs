namespace BoundedAgents.Models;

public enum LlmClientType
{
    /// <summary>GPT-4.1, GPT-4.1-nano, o4-mini — Azure OpenAI Service endpoint.</summary>
    AzureOpenAI,
    /// <summary>Llama, Phi — Azure AI Foundry serverless endpoint.</summary>
    AzureInference,
    /// <summary>claude-* — Anthropic Messages API via Azure AI Services wrapper.</summary>
    AnthropicMessages,
}
