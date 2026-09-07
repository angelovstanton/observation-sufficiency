// ── Axis C per-model progress tracking ───────────────────────────────────
// Consumed by the Axis C mode.

internal sealed class AxisCModelStats
{
    public int Total = 0;
    public int Done = 0;
    public long ObsTok = 0;  // fixed o200k_base tokenizer obs tokens (the cost metric)
    public long ApiTok = 0;  // API-reported prompt tokens (informational)
    public int Retries429 = 0;
    public int SkippedTpm = 0;
    public DateTimeOffset ModelStart = DateTimeOffset.MinValue;
    public TimeSpan Elapsed => ModelStart == DateTimeOffset.MinValue
        ? TimeSpan.Zero : DateTimeOffset.UtcNow - ModelStart;
}
