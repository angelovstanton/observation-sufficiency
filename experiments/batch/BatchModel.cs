using System.Security.Cryptography;
using System.Text;

namespace BoundedAgents.Experiments.Batch;

/// <summary>One planned grounding event, exactly as batch_plan.json lists it.</summary>
public sealed record PlanEvent(
    string Block, string Model, string ModelEnv, string Bundle, string Encoding,
    string Page, string TaskId, int Repetition, int Rep)
{
    /// <summary>Event identity (block deliberately excluded: an event may not appear in two blocks).</summary>
    public string Key => $"{Model}|{Bundle}|{Encoding}|{Page}|{TaskId}|{Repetition}";
}

/// <summary>Allowed (block, model, bundle, encoding, rep) cell of the pinned plan.</summary>
public readonly record struct PlanCell(string Block, string Model, string Bundle, string Encoding, int Rep);

/// <summary>A check failed before any paid call (or before the next one). Nothing is retried.</summary>
public sealed class BatchRefusedException(string message) : Exception(message);

/// <summary>The run stopped on purpose (budget, unknown request outcome, exhausted 429 retries).</summary>
public sealed class BatchStoppedException(string message) : Exception(message);

/// <summary>Everything the runner needs; <see cref="BatchPins.Production"/> builds the pinned one.</summary>
public sealed record BatchOptions
{
    public required string RepoRoot { get; init; }
    public required string PlanPath { get; init; }
    public required string ExpectedPlanSha256 { get; init; }
    public required string OutDir { get; init; }
    public required IReadOnlyDictionary<PlanCell, int> AllowedCells { get; init; }
    public required IReadOnlyDictionary<string, string> ModelEnv { get; init; }
    /// <summary>Observation manifests (page, bundle, encoding, tokens, sha256) with their pinned sha256.</summary>
    public required IReadOnlyList<(string Path, string ExpectedSha256)> ObservationManifests { get; init; }
    public required string ExpectedPagesDigest { get; init; }
    public required string ExpectedPromptDigest { get; init; }
    /// <summary>Environment lookup (process env after .env load in production; a dictionary in tests).</summary>
    public required Func<string, string?> Env { get; init; }
    public int MaxAttempts { get; init; } = 4;
}

public static class Hashing
{
    public static string Sha256Hex(byte[] bytes) =>
        Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    public static string Sha256Hex(string text) => Sha256Hex(Encoding.UTF8.GetBytes(text));

    public static string FileSha256(string path) => Sha256Hex(File.ReadAllBytes(path));
}
