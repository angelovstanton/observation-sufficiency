"""
pareto.py — full 21-cell bundle×encoding Pareto surface.

Question: across all valid (bundle, encoding) combinations, which cells lie on
the Pareto frontier in (success%, mean observation tokens) space, and what is the
joint cost-optimal profile (COP)?

The 21 cells are:
  - 20 DOM cells: 5 bundles × {F0,F1,F2,F3}
    (B_full, B_noVolatile, B_noState, B_noSemantic, B_identityCore)
  - 1 ARIA cell: B_playwrightMCP × F4

B_minimalCore is excluded (degenerate: 0 tokens, 0% success — not a real choice).

A cell is on the Pareto frontier if no other cell achieves both higher success
AND lower (or equal) cost.  Dominated cells can be dropped from any analysis.

Also performs the task-level F4 vs B_noVolatile cross-reference:
  - "NV wins" = NV succeeded (any of F0–F3) AND F4 failed for that (page, task_id).
  - "F4 wins" = F4 succeeded AND all NV encodings failed.

Expected: 4 frontier / 17 dominated.  COP = B_noVolatile × F3.
Headline: +10.00 pp success at −34% tokens vs naïve B_full×F1 baseline.
"""

# UTF-8 console-independence: reconfigure stdout/stderr so Unicode glyphs
# (minus sign, x, >=, ...) print on any console (e.g. Windows cp1252) without
# requiring PYTHONUTF8. Affects output ENCODING only, never any printed value.
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import pathlib
import sys
import pandas as pd
from tabulate import tabulate

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import load_dataframe, DOM_ENCODINGS

# DOM bundles included in the 21-cell matrix (excludes B_minimalCore).
DOM_BUNDLES_FOR_PARETO = [
    "B_full", "B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore",
]


def compute(df: pd.DataFrame) -> dict:
    """
    Compute the full 21-cell Pareto surface and task-level F4 cross-reference.
    Returns a dict of scalar results for the reconciliation table.
    """

    # ── Compute all 21 cells ──────────────────────────────────────────────
    #
    # Each (bundle, encoding) pair defines one cell with 240 records
    # (24 pages × 10 tasks × 1 repetition).
    #
    pareto_records = df[
        (df["bundle"].isin(DOM_BUNDLES_FOR_PARETO) & df["encoding"].isin(DOM_ENCODINGS))
        | (df["bundle"] == "B_playwrightMCP")   # already constrained to F4 by schema
    ].copy()

    assert len(pareto_records) == 5040, (
        f"Expected 20 DOM cells × 240 + 1 ARIA cell × 240 = 5,040; got {len(pareto_records)}"
    )

    cell_stats = pareto_records.groupby(["bundle", "encoding"]).agg(
        n_success=("success",           "sum"),
        n_records=("success",           "count"),
        mean_obs_tokens=("observation_tokens", "mean"),
    )
    cell_stats["success_rate"] = cell_stats["n_success"] / cell_stats["n_records"]

    assert len(cell_stats) == 21, (
        f"Expected 21 cells; got {len(cell_stats)}"
    )

    # Verify specific cells match prior analyses.
    nv_f1_rate  = cell_stats.loc[("B_noVolatile",   "F1"), "success_rate"]
    nv_f3_rate  = cell_stats.loc[("B_noVolatile",   "F3"), "success_rate"]
    nv_f1_tok   = cell_stats.loc[("B_noVolatile",   "F1"), "mean_obs_tokens"]
    nv_f3_tok   = cell_stats.loc[("B_noVolatile",   "F3"), "mean_obs_tokens"]
    f4_rate     = cell_stats.loc[("B_playwrightMCP","F4"), "success_rate"]
    f4_tok      = cell_stats.loc[("B_playwrightMCP","F4"), "mean_obs_tokens"]
    bf_f1_rate  = cell_stats.loc[("B_full",         "F1"), "success_rate"]
    bf_f1_tok   = cell_stats.loc[("B_full",         "F1"), "mean_obs_tokens"]

    # ── Pareto frontier identification ────────────────────────────────────
    #
    # Sort cells cheapest → most expensive.  Walk through in that order,
    # tracking the maximum success rate seen so far.  A cell is on the frontier
    # if its success exceeds every cheaper-or-equal cell; otherwise it is
    # dominated (there exists a cheaper point with equal or better success).
    #
    cells_sorted = cell_stats.sort_values("mean_obs_tokens").copy()
    cells_sorted["pareto_status"] = "dominated"

    max_success_seen_so_far = -1.0
    for idx in cells_sorted.index:
        current_success = cells_sorted.loc[idx, "success_rate"]
        if current_success > max_success_seen_so_far:
            cells_sorted.loc[idx, "pareto_status"] = "FRONTIER"
            max_success_seen_so_far = current_success

    frontier_cells   = cells_sorted[cells_sorted["pareto_status"] == "FRONTIER"]
    dominated_cells  = cells_sorted[cells_sorted["pareto_status"] == "dominated"]

    frontier_count  = len(frontier_cells)
    dominated_count = len(dominated_cells)

    # ── Identify the COP ──────────────────────────────────────────────────
    #
    # The Canonical Observation Profile (COP) is the cheapest frontier cell
    # whose success rate exceeds 50%.  Under the frozen predicate B_noVolatile×F3
    # is the ONLY frontier cell above that threshold: F3 now beats F1 on success
    # (67.92% vs 67.50%) at ~29% fewer tokens, so B_noVolatile×F1 is dominated and
    # has left the frontier.  F3 is therefore the COP on both axes, not merely the
    # cheaper of two adequate options.
    #
    high_success_frontier = frontier_cells[frontier_cells["success_rate"] > 0.50]
    cop = high_success_frontier.iloc[0]          # cheapest in the sorted table
    cop_bundle   = cop.name[0]
    cop_encoding = cop.name[1]

    # ── Abstract headline ─────────────────────────────────────────────────
    #
    # Compare COP (B_noVolatile×F3) against the naïve baseline B_full×F1 —
    # the configuration a developer would reach for without any bundle/encoding
    # research.
    #
    headline_success_delta_pp    = (nv_f3_rate  - bf_f1_rate) * 100
    headline_token_reduction_pct = (bf_f1_tok   - nv_f3_tok)  / bf_f1_tok * 100

    # ── Task-level F4 vs B_noVolatile cross-reference ─────────────────────
    #
    # Each (page, task_id) pair has:
    #   - 4 B_noVolatile records (one per DOM encoding F0–F3)
    #   - 1 B_playwrightMCP×F4 record
    #
    # "NV succeeds" = any DOM encoding succeeded for that task (best-of-4).
    # This is the fairest comparison for the COP bundle-level claim.
    # The asymmetry (4:1) is explicitly labelled in the paper.
    #
    nv_all_records = df[
        (df["bundle"] == "B_noVolatile") & df["encoding"].isin(DOM_ENCODINGS)
    ]
    f4_all_records = df[df["bundle"] == "B_playwrightMCP"]

    # One repetition only — assert to avoid double-counting if data ever expands.
    assert nv_all_records["repetition"].nunique() == 1, (
        "Multiple NV repetitions in data — task-level cross-ref needs updating"
    )

    # For each (page, task_id): did ANY B_noVolatile encoding succeed?
    nv_task_success = (
        nv_all_records
        .groupby(["page", "task_id"])["success"]
        .any()
        .rename("nv_succeeded")
    )

    # For each (page, task_id): did F4 succeed?
    f4_task_success = (
        f4_all_records
        .groupby(["page", "task_id"])["success"]
        .first()               # only one F4 record per task
        .rename("f4_succeeded")
    )

    # Join the two series on (page, task_id).
    task_comparison = pd.concat([nv_task_success, f4_task_success], axis=1)

    assert len(task_comparison) == 240, (
        f"Expected 240 unique (page, task_id) pairs; got {len(task_comparison)}"
    )

    both_succeed_count = (task_comparison["nv_succeeded"]  & task_comparison["f4_succeeded"]).sum()
    f4_wins_count      = (~task_comparison["nv_succeeded"] & task_comparison["f4_succeeded"]).sum()
    nv_wins_count      = (task_comparison["nv_succeeded"]  & ~task_comparison["f4_succeeded"]).sum()
    both_fail_count    = (~task_comparison["nv_succeeded"] & ~task_comparison["f4_succeeded"]).sum()

    assert both_succeed_count + f4_wins_count + nv_wins_count + both_fail_count == 240

    # ── Assertions ────────────────────────────────────────────────────────
    assert frontier_count == 4, (
        f"Expected 4 frontier cells, got {frontier_count}"
    )
    assert dominated_count == 17, (
        f"Expected 17 dominated cells, got {dominated_count}"
    )
    assert cop_bundle   == "B_noVolatile", (
        f"COP bundle expected B_noVolatile, got {cop_bundle}"
    )
    assert cop_encoding == "F3", (
        f"COP encoding expected F3, got {cop_encoding}"
    )

    assert abs(headline_success_delta_pp    - 10.00) < 0.1, (
        f"Headline success delta {headline_success_delta_pp:.2f} pp ≠ expected 10.00 pp"
    )
    assert abs(headline_token_reduction_pct - 34.0) < 0.5, (
        f"Headline token reduction {headline_token_reduction_pct:.1f}% ≠ expected 34.0%"
    )

    assert abs(nv_f1_rate - 0.6750) < 0.001
    assert abs(f4_rate    - 0.4708) < 0.001
    assert abs(nv_f1_tok  - 25239)  <= 1
    assert abs(f4_tok     - 8914)   <= 1

    assert nv_wins_count == 70, (
        f"NV wins over F4 = {nv_wins_count}, expected 70"
    )
    assert f4_wins_count == 14, (
        f"F4 wins over NV = {f4_wins_count}, expected 14"
    )

    # ── Print tables ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("PARETO: full 21-cell table (sorted by cost ascending)")
    print(f"{'='*60}")

    display = cells_sorted.copy().reset_index()
    display["success %"] = (display["success_rate"] * 100).round(2)
    display["mean tok"]  = display["mean_obs_tokens"].round(0).astype(int)
    print(tabulate(
        display[["bundle", "encoding", "success %", "mean tok", "pareto_status"]],
        headers="keys", tablefmt="pipe", showindex=False,
    ))

    print(f"\n{'='*60}")
    print("PARETO: frontier path (cheapest → most expensive)")
    print(f"{'='*60}")
    frontier_display = frontier_cells.reset_index()
    frontier_display["success %"] = (frontier_display["success_rate"] * 100).round(2)
    frontier_display["mean tok"]  = frontier_display["mean_obs_tokens"].round(0).astype(int)
    print(tabulate(
        frontier_display[["bundle", "encoding", "success %", "mean tok"]],
        headers="keys", tablefmt="pipe", showindex=False,
    ))

    print(f"\n  Dominated cells: {dominated_count}")
    print(f"  COP: {cop_bundle} × {cop_encoding}  ({cop['success_rate']:.2%}, {cop['mean_obs_tokens']:.0f} tok)")
    print(f"\n  Headline: B_noVolatile×F3 vs B_full×F1")
    print(f"  Success delta:   {headline_success_delta_pp:+.2f} pp")
    print(f"  Token reduction: {headline_token_reduction_pct:.1f}%")

    print(f"\n{'='*60}")
    print("PARETO: task-level F4 vs B_noVolatile cross-reference")
    print(f"(NV = any-of-4-encodings; F4 = single ARIA encoding)")
    print(f"{'='*60}")
    cross_table = pd.DataFrame([
        {"outcome": "Both succeed",    "count": both_succeed_count, "pct": both_succeed_count/240*100},
        {"outcome": "F4 wins",         "count": f4_wins_count,      "pct": f4_wins_count/240*100},
        {"outcome": "NV wins",         "count": nv_wins_count,       "pct": nv_wins_count/240*100},
        {"outcome": "Both fail",       "count": both_fail_count,     "pct": both_fail_count/240*100},
    ])
    print(tabulate(cross_table, headers="keys", tablefmt="pipe", showindex=False, floatfmt=".1f"))

    return {
        "frontier_count":              frontier_count,
        "dominated_count":             dominated_count,
        "cop_bundle":                  cop_bundle,
        "cop_encoding":                cop_encoding,
        "headline_success_delta_pp":   headline_success_delta_pp,
        "headline_token_reduction_pct":headline_token_reduction_pct,
        "f4_success_rate":             f4_rate,
        "f4_mean_tokens":              f4_tok,
        "nv_f1_success":               nv_f1_rate,
        "nv_f1_mean_tokens":           nv_f1_tok,
        "nv_wins_over_f4":             nv_wins_count,
        "f4_wins_over_nv":             f4_wins_count,
        "both_succeed_count":          int(both_succeed_count),
        "both_fail_count":             int(both_fail_count),
        "cells_sorted":                cells_sorted,
        "frontier_cells":              frontier_cells,
    }


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).parent.parent.parent
    df = load_dataframe(repo_root)
    compute(df)
