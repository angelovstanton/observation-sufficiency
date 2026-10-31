using BoundedAgents.Shared.Harness;
using BoundedAgents.Shared.Tokenizer;

namespace BoundedAgents.Experiments.Batch;

/// <summary>
/// Input-token budget. The ledger holds native API usage (prompt_tokens); a call is made only if
/// spent + reservation ≤ cap, where the reservation is the exact o200k_base count of the system and
/// user prompt (the same fixed tokenizer the corpus records use) plus a fixed chat-framing reserve.
/// </summary>
public static class BatchBudget
{
    /// <summary>
    /// Chat-format framing tokens added by the API on top of the two message strings: 9–30 per
    /// event on the corpus (native usage − string count), so 64 is above twice the maximum.
    /// A response whose native usage exceeds the reservation stops the run.
    /// </summary>
    public const int FramingReserveTokens = 64;

    public static int Reservation(string userPrompt) =>
        TokenCounter.CountTokens(GroundingRunner.SystemPrompt) + TokenCounter.CountTokens(userPrompt)
        + FramingReserveTokens;
}
