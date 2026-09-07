namespace BoundedAgents.Shared.Oracle;

/// <summary>
/// Identifies the target element by its data-oracle-id value.
/// The data-oracle-id attribute lives only in the raw DOM (bookkeeping anchor);
/// it is stripped from the observation before encoding (TESTBED_SPEC §3).
/// </summary>
public record OracleRef(string OracleId);
