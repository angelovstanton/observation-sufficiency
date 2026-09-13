using System.Text.Json;
using Azure;
using Azure.AI.Inference;
using Azure.AI.OpenAI;
using BoundedAgents.Models;
using OpenAI.Chat;

namespace BoundedAgents.Shared.Harness;

public record LlmResponse(string Content, int PromptTokens, int CompletionTokens, string ModelId);

public static partial class LlmClient
{
    // temperature=0 for the two OpenAI-family models that accept it (GPT-4.1,
    // GPT-4.1-nano) — never expose as a parameter. o-series reasoning models
    // (o1/o3/o4) reject temperature=0 — the API either errors or silently
    // ignores it — so it is omitted for them. The Anthropic path
    // (CallAnthropicAsync) has no temperature field at all: Claude runs at
    // the provider's own default, not 0.
    private const float Temperature = 0f;
    private const int MaxTokens = 256;

    // Delays for 429 retry on AzureInference (Llama): 1 s, 2 s, 4 s (3 attempts).
    private static readonly int[] RetryDelaysMs = [1_000, 2_000, 4_000];
    // Anthropic 429s include "Please wait N seconds" — we parse that instead of using a fixed delay.
    // 5 retries to cover window resets up to ~60 s (with 2 s buffer each).
    private const int MaxAnthropicRetries = 5;

    /// <summary>
    /// Cumulative 429 retries across all calls since last reset.
    /// Reset this field (= 0) before each model run to get per-model counts.
    /// Interlocked for safety; sequential callers can read directly.
    /// </summary>
    public static int TotalRetries429 = 0;

    /// <summary>True for o1-*, o3-*, o4-* deployments (reasoning models).</summary>
    public static bool IsReasoningModel(string deployment) =>
        deployment.StartsWith("o1", StringComparison.OrdinalIgnoreCase) ||
        deployment.StartsWith("o3", StringComparison.OrdinalIgnoreCase) ||
        deployment.StartsWith("o4", StringComparison.OrdinalIgnoreCase);

    /// <summary>
    /// Dispatches one completion to the provider matching <paramref name="clientType"/>
    /// and returns the content plus prompt/completion token counts.
    /// Runs at temperature 0, except for o-series reasoning deployments, which
    /// reject the field and have it omitted entirely.
    /// </summary>
    public static async Task<LlmResponse> CallAsync(
        string systemPrompt,
        string userPrompt,
        string deployment,
        string endpoint,
        LlmClientType clientType,
        CancellationToken ct = default)
    {
        return clientType switch
        {
            LlmClientType.AzureOpenAI => await CallOpenAiAsync(systemPrompt, userPrompt, deployment, endpoint, ct),
            LlmClientType.AzureInference => await CallInferenceAsync(systemPrompt, userPrompt, deployment, endpoint, ct),
            LlmClientType.AnthropicMessages => await CallAnthropicAsync(systemPrompt, userPrompt, deployment, endpoint, ct),
            _ => throw new ArgumentOutOfRangeException(nameof(clientType)),
        };
    }

    // ── Credential helpers ────────────────────────────────────────────────────

    private static AzureKeyCredential GetKeyCredential()
    {
        var key = Environment.GetEnvironmentVariable("BAR_AZURE_OPENAI_KEY")
            ?? throw new InvalidOperationException(
                "BAR_AZURE_OPENAI_KEY is not set. Add it to .env.");
        return new AzureKeyCredential(key);
    }

    private static string GetAnthropicKey() =>
        Environment.GetEnvironmentVariable("BAR_AZURE_ANTHROPIC_KEY")
            ?? throw new InvalidOperationException(
                "BAR_AZURE_ANTHROPIC_KEY is not set. Paste the key from the Azure AI portal into .env.");

    // ── Azure.AI.OpenAI path (GPT-4.1, GPT-4.1-nano, o4-mini) ──────────────

    private static AzureOpenAIClient? _openAiClient;
    private static readonly object _openAiLock = new();

    private static AzureOpenAIClient GetOpenAiClient(string endpoint)
    {
        if (_openAiClient is null)
        {
            lock (_openAiLock)
            {
                if (_openAiClient is null)
                {
                    // V2024_12_01_Preview is the minimum that supports o4-mini (and all GPT-4.1 variants).
                    var opts = new AzureOpenAIClientOptions(
                        AzureOpenAIClientOptions.ServiceVersion.V2024_12_01_Preview);
                    _openAiClient = new AzureOpenAIClient(new Uri(endpoint), GetKeyCredential(), opts);
                }
            }
        }

        return _openAiClient;
    }

    private static async Task<LlmResponse> CallOpenAiAsync(
        string system, string user, string deployment, string endpoint, CancellationToken ct)
    {
        var client = GetOpenAiClient(endpoint);
        var chat = client.GetChatClient(deployment);

        var messages = new List<ChatMessage>
        {
            new SystemChatMessage(system),
            new UserChatMessage(user),
        };

        bool isReasoning = IsReasoningModel(deployment);
        var options = new ChatCompletionOptions
        {
            // Reasoning models (o-series) reject max_tokens; omit the field so the model
            // uses its own default. Our locator output is ~75 tokens — well within any default.
            MaxOutputTokenCount = isReasoning ? null : MaxTokens,
        };
        // Reasoning models reject temperature=0; omit the field entirely for them.
        if (!isReasoning)
        {
            options.Temperature = Temperature;
        }

        Console.Error.WriteLine(
            $"[LlmClient] AzureOpenAI deployment={deployment} reasoning={isReasoning} " +
            $"temp={(isReasoning ? "omitted" : "0")} maxTokens={options.MaxOutputTokenCount}");
        var result = await chat.CompleteChatAsync(messages, options, ct);
        var c = result.Value;

        return new LlmResponse(
            Content: c.Content[0].Text.Trim(),
            PromptTokens: c.Usage.InputTokenCount,
            CompletionTokens: c.Usage.OutputTokenCount,
            ModelId: deployment
        );
    }

    // ── Azure.AI.Inference path (Llama / Phi via Foundry serverless) ─────────

    private static async Task<LlmResponse> CallInferenceAsync(
        string system, string user, string deployment, string endpoint, CancellationToken ct)
    {
        var client = new ChatCompletionsClient(new Uri(endpoint), GetKeyCredential());

        var options = new ChatCompletionsOptions
        {
            Model = deployment,
            Temperature = Temperature,
            MaxTokens = MaxTokens,
            Messages =
            {
                new ChatRequestSystemMessage(system),
                new ChatRequestUserMessage(user),
            },
        };

        for (int attempt = 0; ; attempt++)
        {
            try
            {
                var response = await client.CompleteAsync(options, ct);
                var c = response.Value;

                return new LlmResponse(
                    Content: c.Content.Trim(),
                    PromptTokens: c.Usage.PromptTokens,
                    CompletionTokens: c.Usage.CompletionTokens,
                    ModelId: deployment
                );
            }
            catch (RequestFailedException ex) when (ex.Status == 429 && attempt < RetryDelaysMs.Length)
            {
                Interlocked.Increment(ref TotalRetries429);
                var delay = RetryDelaysMs[attempt];
                Console.Error.WriteLine(
                    $"[LlmClient] 429 on {deployment} — retry {attempt + 1}/{RetryDelaysMs.Length} in {delay} ms");
                await Task.Delay(delay, ct);
            }
        }
    }

    // ── Anthropic Messages API path (claude-* via Azure AI Services) ──────────
    //
    // Request shape differs from OpenAI in three ways:
    //   1. `system` is a top-level field, NOT a role:system message in the messages array
    //   2. `max_tokens` is required (Anthropic has no server-side default)
    //   3. Response content is content[0].text, not choices[0].message.content
    //
    // Auth: the Azure AI Services Anthropic endpoint requires the Anthropic-native
    // `x-api-key` header plus `anthropic-version: 2023-06-01` (both set on the request below).

    private static readonly HttpClient _http = new();
    private static readonly JsonSerializerOptions _jsonOpts = new() { PropertyNameCaseInsensitive = true };

    private static async Task<LlmResponse> CallAnthropicAsync(
        string system, string user, string deployment, string endpoint, CancellationToken ct)
    {
        var key = GetAnthropicKey();
        var body = new AnthropicRequest(
            Model: deployment,
            MaxTokens: MaxTokens,
            System: system,
            Messages: [new AMessage("user", user)]
        );

        Console.Error.WriteLine($"[LlmClient] Anthropic deployment={deployment} maxTokens={MaxTokens}");

        for (int attempt = 0; ; attempt++)
        {
            // ByteArrayContent sets Content-Length automatically; JsonContent uses chunked
            // encoding which the Azure AI Services Anthropic endpoint rejects (400).
            var bodyBytes = System.Text.Encoding.UTF8.GetBytes(JsonSerializer.Serialize(body));
            using var request = new HttpRequestMessage(HttpMethod.Post, endpoint)
            {
                Content = new ByteArrayContent(bodyBytes),
            };
            request.Content.Headers.ContentType =
                new System.Net.Http.Headers.MediaTypeHeaderValue("application/json");
            request.Headers.Add("x-api-key", key);
            request.Headers.Add("anthropic-version", "2023-06-01");

            var httpResp = await _http.SendAsync(request, ct);

            if (httpResp.StatusCode == System.Net.HttpStatusCode.TooManyRequests &&
                attempt < MaxAnthropicRetries)
            {
                Interlocked.Increment(ref TotalRetries429);
                var body429 = await httpResp.Content.ReadAsStringAsync(ct);
                // Parse "Please wait N seconds" from the API error body (if present) and add a 2 s buffer.
                // This is more reliable than a fixed backoff because the Claude 80K TPM window can reset
                // anywhere between 1 s and 60 s depending on when prior tokens were consumed.
                int delayMs = 20_000; // safe fallback
                var m = System.Text.RegularExpressions.Regex.Match(
                    body429, @"Please wait (\d+) seconds", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
                if (m.Success && int.TryParse(m.Groups[1].Value, out int waitSec))
                {
                    delayMs = (waitSec + 2) * 1_000;
                }

                Console.Error.WriteLine(
                    $"[LlmClient] 429 on {deployment} — retry {attempt + 1}/{MaxAnthropicRetries} in {delayMs / 1000} s  (body: {body429[..Math.Min(120, body429.Length)]})");
                await Task.Delay(delayMs, ct);
                continue;
            }

            var raw = await httpResp.Content.ReadAsStringAsync(ct);

            if (!httpResp.IsSuccessStatusCode)
            {
                throw new InvalidOperationException(
                    $"Anthropic endpoint returned HTTP {(int)httpResp.StatusCode} ({httpResp.ReasonPhrase}).\n" +
                    $"Body: {raw}");
            }

            AnthropicResponse resp;
            try
            {
                resp = JsonSerializer.Deserialize<AnthropicResponse>(raw, _jsonOpts)
                       ?? throw new InvalidOperationException("Deserialized null response.");
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException(
                    $"Failed to parse Anthropic response.\nRaw body:\n{raw}", ex);
            }

            var textBlock = resp.Content.FirstOrDefault(b => b.Type == "text")
                ?? throw new InvalidOperationException(
                    $"No text content block in Anthropic response.\nRaw body:\n{raw}");

            return new LlmResponse(
                Content: (textBlock.Text ?? string.Empty).Trim(),
                PromptTokens: resp.Usage.InputTokens,
                CompletionTokens: resp.Usage.OutputTokens,
                ModelId: deployment
            );
        }
    }
}
