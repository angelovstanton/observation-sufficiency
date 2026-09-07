namespace BoundedAgents.Shared.Tokenizer;

/// <summary>
/// Fixed tokenizer for cost measurement. Token count is the sole cost unit —
/// never convert to dollars or mix in latency (§6).
/// Bumping <see cref="TokenizerEncoding"/> requires an explicit decision;
/// record the value on every JSONL run record.
/// </summary>
public static class TokenCounter
{
    public const string TokenizerEncoding = "o200k_base";

    private static readonly Lazy<SharpToken.GptEncoding> _enc =
        new(() => SharpToken.GptEncoding.GetEncoding(TokenizerEncoding));

    public static int CountTokens(string text) => _enc.Value.Encode(text).Count;

    public static string TokenizerVersion() => TokenizerEncoding;
}
