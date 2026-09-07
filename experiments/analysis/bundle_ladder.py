"""
bundle_ladder.py — six-bundle cost-sufficiency ladder.

Question: how does success rate and observation cost change as we strip
increasingly important attribute categories from the observation?  Where is the
primary cliff, and which bundles are Pareto-dominated?

The six bundles form a conceptual ladder from most information (B_full) to none
(B_minimalCore).  The ladder is NOT monotone — B_noVolatile beats B_full despite
being cheaper, which is the central B-axis finding of this study.

Input: all DOM records (encoding ∈ {F0,F1,F2,F3}).  Each bundle has 960 records.
F4/B_playwrightMCP is excluded here; it is handled in pareto.py.

Expected: primary cliff B_noState→B_noSemantic = −19.79 pp.
"""

import pathlib
import sys
import pandas as pd
from tabulate import tabulate

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import load_dataframe, DOM_ENCODINGS

# The conceptual ladder order is by information content (subset structure),
# NOT by token count.  B_noVolatile and B_noState are close in token cost but
# differ in which attributes they retain.
BUNDLE_LADDER_ORDER = [
    "B_full",
    "B_noVolatile",
    "B_noState",
    "B_noSemantic",
    "B_identityCore",
    "B_minimalCore",
]


def compute(df: pd.DataFrame) -> dict:
    """
    Compute per-bundle success rates and mean observation tokens.
    Returns a dict of scalars for the reconciliation table.
    """

    # ── Filter to DOM encodings ────────────────────────────────────────────
    #
    # Only F0–F3.  B_playwrightMCP with F4 is separately handled in pareto.py.
    #
    dom_records = df[
        df["bundle"].isin(BUNDLE_LADDER_ORDER)
        & df["encoding"].isin(DOM_ENCODINGS)
    ].copy()

    assert len(dom_records) == 5760, (
        f"Expected 6 bundles × 960 records = 5,760; got {len(dom_records)}"
    )

    # ── Per-bundle statistics ─────────────────────────────────────────────
    #
    # success_rate:  fraction of records where the record passed all five predicate
    #                conditions (§6 — the fifth is stable_signal_present_in_bundle).
    # mean_obs_tokens: average observation token count (the primary cost metric).
    # low_success, high_success: rates split by semantic density stratum.
    #
    bundle_stats = dom_records.groupby("bundle").agg(
        n_success=("success", "sum"),
        n_records=("success", "count"),
        mean_obs_tokens=("observation_tokens", "mean"),
    )
    bundle_stats["success_rate"] = bundle_stats["n_success"] / bundle_stats["n_records"]

    # Compute LOW and HIGH success rates separately using the semantic_density column.
    stratum_rates = (
        dom_records
        .groupby(["bundle", "semantic_density"])["success"]
        .mean()
        .unstack("semantic_density")
    )
    bundle_stats = bundle_stats.join(stratum_rates)

    # ── Apply the ladder order ─────────────────────────────────────────────
    bundle_stats = bundle_stats.reindex(BUNDLE_LADDER_ORDER)

    # ── Adjacent transitions ───────────────────────────────────────────────
    #
    # Compute the success delta between each consecutive pair in the ladder.
    # Negative means success DROPS as we descend (expected for most steps).
    # Positive (non-monotonic) means the lower-information bundle beats the one above.
    #
    success_rates_in_order = bundle_stats["success_rate"].values
    transitions = []
    for i in range(1, len(BUNDLE_LADDER_ORDER)):
        upper_bundle = BUNDLE_LADDER_ORDER[i - 1]
        lower_bundle = BUNDLE_LADDER_ORDER[i]
        delta_pp = (success_rates_in_order[i] - success_rates_in_order[i - 1]) * 100
        transitions.append({
            "transition":          f"{upper_bundle} -> {lower_bundle}",
            "upper_success_pct":   round(success_rates_in_order[i - 1] * 100, 2),
            "lower_success_pct":   round(success_rates_in_order[i]     * 100, 2),
            "delta_pp":            round(delta_pp, 2),
            "note": (
                "non-monotonic gain" if delta_pp > 0
                else "primary cliff" if abs(delta_pp) > 20
                else ""
            ),
        })
    transitions_df = pd.DataFrame(transitions)

    # ── Extract key scalars ───────────────────────────────────────────────
    nv_success_rate      = bundle_stats.loc["B_noVolatile", "success_rate"]
    bf_success_rate      = bundle_stats.loc["B_full",       "success_rate"]
    nostate_success_rate = bundle_stats.loc["B_noState",    "success_rate"]
    nosem_success_rate   = bundle_stats.loc["B_noSemantic", "success_rate"]
    idcore_success_rate  = bundle_stats.loc["B_identityCore","success_rate"]
    minimal_success_rate = bundle_stats.loc["B_minimalCore","success_rate"]

    nosem_mean_tokens    = bundle_stats.loc["B_noSemantic", "mean_obs_tokens"]

    # The primary cliff: B_noState → B_noSemantic drop.
    cliff_pp = (nosem_success_rate - nostate_success_rate) * 100  # will be negative

    # ── Assertions ────────────────────────────────────────────────────────
    assert nv_success_rate > bf_success_rate, (
        "B_noVolatile must beat B_full (volatile-stripping gain); this is the thesis."
    )

    # B_noSemantic should be WORSE than B_identityCore (the Pareto trap).
    assert nosem_success_rate < idcore_success_rate, (
        f"B_noSemantic ({nosem_success_rate:.4f}) should be < "
        f"B_identityCore ({idcore_success_rate:.4f}) — Pareto trap"
    )

    assert minimal_success_rate == 0.0, (
        f"B_minimalCore must have 0% success (zero-information baseline); "
        f"got {minimal_success_rate:.4f}"
    )
    assert bundle_stats.loc["B_minimalCore", "mean_obs_tokens"] <= 1.0, (
        f"B_minimalCore mean observation tokens must be ≤ 1 (near-zero baseline); "
        f"got {bundle_stats.loc['B_minimalCore', 'mean_obs_tokens']:.2f}"
    )

    assert abs(nv_success_rate - 0.6427) < 0.001, (
        f"B_noVolatile success {nv_success_rate:.4f} ≠ expected 0.6427"
    )
    assert abs(nostate_success_rate - 0.5510) < 0.001, (
        f"B_noState success {nostate_success_rate:.4f} ≠ expected 0.5510"
    )
    assert abs(nosem_success_rate - 0.3531) < 0.001, (
        f"B_noSemantic success {nosem_success_rate:.4f} ≠ expected 0.3531"
    )
    assert abs(idcore_success_rate - 0.3958) < 0.001, (
        f"B_identityCore success {idcore_success_rate:.4f} ≠ expected 0.3958"
    )

    # The cliff is the transition from B_noState to B_noSemantic.
    # Expected: −19.79 pp (large negative, the primary sufficiency cliff).
    # Re-pinned 2026-07-22: was −26.56 pp; B_noSemantic rose 28.54%→35.31% after
    # the signal_attrs completeness correction (unlisted id/href false negatives),
    # so the cliff is shallower. B_noState unchanged.
    assert abs(cliff_pp - (-19.79)) < 0.5, (
        f"Primary cliff (B_noState→B_noSemantic) = {cliff_pp:.2f} pp, expected −19.79 pp"
    )

    assert abs(nosem_mean_tokens - 11013) < 5, (
        f"B_noSemantic mean tokens {nosem_mean_tokens:.0f} ≠ expected 11,013"
    )

    # ── Print tables ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("BUNDLE LADDER: per-bundle success rates and token costs")
    print(f"{'='*60}")

    ladder_display = bundle_stats.copy()
    ladder_display["success %"]    = (ladder_display["success_rate"] * 100).round(2)
    ladder_display["mean tok"]     = ladder_display["mean_obs_tokens"].round(0).astype(int)
    ladder_display["% of B_full"]  = (
        ladder_display["mean_obs_tokens"] / bundle_stats.loc["B_full", "mean_obs_tokens"] * 100
    ).round(1)
    ladder_display["LOW %"]        = (ladder_display["LOW"]  * 100).round(2)
    ladder_display["HIGH %"]       = (ladder_display["HIGH"] * 100).round(2)
    print(tabulate(
        ladder_display[["success %", "mean tok", "% of B_full", "LOW %", "HIGH %"]].reset_index(),
        headers="keys", tablefmt="pipe", showindex=False,
    ))

    print(f"\n{'='*60}")
    print("BUNDLE LADDER: adjacent transitions")
    print(f"{'='*60}")
    print(tabulate(transitions_df, headers="keys", tablefmt="pipe", showindex=False))

    return {
        "bf_success_rate":        bf_success_rate,
        "nv_success_rate":        nv_success_rate,
        "nostate_success_rate":   nostate_success_rate,
        "nosem_success_rate":     nosem_success_rate,
        "idcore_success_rate":    idcore_success_rate,
        "minimal_success_rate":   minimal_success_rate,
        "nosem_mean_tokens":      nosem_mean_tokens,
        "cliff_pp":               cliff_pp,
        "bundle_stats":           bundle_stats,
        "transitions_df":         transitions_df,
    }


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).parent.parent.parent
    df = load_dataframe(repo_root)
    compute(df)
