using System.ClientModel;
using System.ClientModel.Primitives;
using Azure.AI.OpenAI;
using OpenAI.Chat;

namespace BoundedAgents.Shared.Harness;

/// <summary>
/// One Azure OpenAI completion plus the response metadata the corpus records did not keep:
/// the model identifier the service returned, the finish reason and the system fingerprint.
/// </summary>
public record LlmCallDetail(LlmResponse Response, string? ResponseModel, string? FinishReason, string? SystemFingerprint);

/// <summary>
/// HTTP 429 from the service: the request was rejected before generation, so it is safe to
/// retry. <see cref="RetryAfter"/> is the server's Retry-After hint, when it sent one.
/// </summary>
public sealed class LlmRateLimitedException(TimeSpan? retryAfter, Exception inner)
    : Exception("HTTP 429 (rate limited)", inner)
{
    public TimeSpan? RetryAfter { get; } = retryAfter;
}

public static partial class LlmClient
{
    private static AzureOpenAIClient? _openAiClientNoRetry;

    /// <summary>
    /// Same request as the AzureOpenAI path of <see cref="CallAsync"/> (same Temperature and
    /// MaxTokens constants, same o-series rule), with two differences that do not touch the
    /// generation: the SDK's automatic retries are off (the caller owns and logs every attempt),
    /// and the returned model id, finish reason and system fingerprint are read back.
    /// A 429 surfaces as <see cref="LlmRateLimitedException"/>; anything else propagates.
    /// </summary>
    public static async Task<LlmCallDetail> CallAzureOpenAiDetailedAsync(
        string systemPrompt, string userPrompt, string deployment, string endpoint, CancellationToken ct = default)
    {
        if (_openAiClientNoRetry is null)
        {
            lock (_openAiLock)
            {
                if (_openAiClientNoRetry is null)
                {
                    var opts = new AzureOpenAIClientOptions(
                        AzureOpenAIClientOptions.ServiceVersion.V2024_12_01_Preview)
                    {
                        RetryPolicy = new ClientRetryPolicy(maxRetries: 0),
                    };
                    _openAiClientNoRetry = new AzureOpenAIClient(new Uri(endpoint), GetKeyCredential(), opts);
                }
            }
        }
        var chat = _openAiClientNoRetry.GetChatClient(deployment);

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(systemPrompt),
            new UserChatMessage(userPrompt),
        };

        bool isReasoning = IsReasoningModel(deployment);
        var options = new ChatCompletionOptions
        {
            MaxOutputTokenCount = isReasoning ? null : MaxTokens,
        };
        if (!isReasoning)
        {
            options.Temperature = Temperature;
        }

        Console.Error.WriteLine(
            $"[LlmClient] AzureOpenAI(detailed, no SDK retry) deployment={deployment} reasoning={isReasoning} " +
            $"temp={(isReasoning ? "omitted" : "0")} maxTokens={options.MaxOutputTokenCount}");

        ChatCompletion c;
        try
        {
            c = (await chat.CompleteChatAsync(messages, options, ct)).Value;
        }
        catch (ClientResultException ex) when (ex.Status == 429)
        {
            TimeSpan? retryAfter = null;
            var raw = ex.GetRawResponse();
            if (raw is not null && raw.Headers.TryGetValue("Retry-After", out var ra)
                && int.TryParse(ra, out var seconds))
            {
                retryAfter = TimeSpan.FromSeconds(seconds);
            }
            throw new LlmRateLimitedException(retryAfter, ex);
        }

        // CallAsync indexes Content[0] and would throw on an empty completion (e.g. a reasoning
        // model that spent its budget); here the paid response is kept as "" with its finish reason.
        return new LlmCallDetail(
            new LlmResponse(
                Content: c.Content.Count > 0 ? c.Content[0].Text.Trim() : string.Empty,
                PromptTokens: c.Usage.InputTokenCount,
                CompletionTokens: c.Usage.OutputTokenCount,
                ModelId: deployment),
            ResponseModel: c.Model,
            FinishReason: c.FinishReason.ToString(),
            SystemFingerprint: c.SystemFingerprint);
    }
}
