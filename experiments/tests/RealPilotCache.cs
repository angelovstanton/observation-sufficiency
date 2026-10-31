using BoundedAgents.Experiments.Batch;
using Xunit;

namespace Experiments.Tests;

/// <summary>
/// Tests that load the archived real-site pages. Those pages are third-party content and are not
/// redistributed; they are re-fetched from the WARC pointers into ../_external/cc_cache next to the
/// repository (see README, Revision 1). Without them these tests are skipped, not failed.
/// </summary>
internal static class RealPilotCache
{
    public static string? SkipReason()
    {
        var may = PilotPins.Production(Testbed.RepoRoot).HtmlDir;
        var september = Path.Combine(Path.GetDirectoryName(may)!, "CC-MAIN-2026-39");
        return Directory.Exists(may) && Directory.Exists(september)
            ? null
            : $"needs the archived real-site pages in {Path.GetDirectoryName(may)} (not redistributed)";
    }
}

public sealed class RealPilotFactAttribute : FactAttribute
{
    public RealPilotFactAttribute() => Skip = RealPilotCache.SkipReason();
}

public sealed class RealPilotTheoryAttribute : TheoryAttribute
{
    public RealPilotTheoryAttribute() => Skip = RealPilotCache.SkipReason();
}
