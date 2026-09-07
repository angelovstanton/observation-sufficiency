"""
thesis.py — B_full vs B_noVolatile per-page and corpus comparison.

Question: does removing volatile attributes (hashed class strings, auto-generated
fragment IDs) from the observation improve grounding success?  And does the gain
hold across the full 24-page corpus, or was it driven by outliers?

Input: all records where bundle ∈ {B_full, B_noVolatile} and
       encoding ∈ {F0, F1, F2, F3}.  Each bundle has exactly 960 records
       (24 pages × 10 tasks × 4 encodings × 1 repetition).

Expected headline: B_full=54.79%, B_noVolatile=64.27%, corpus delta=+9.48 pp.
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

# Allow running this file directly (python experiments/analysis/thesis.py).
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import load_dataframe, DOM_ENCODINGS


def compute(df: pd.DataFrame) -> dict:
    """
    Compute B_full vs B_noVolatile comparison.  Returns a dict of scalar results
    for use by run_all.py's reconciliation table.
    """

    # ── Filter to the two bundles of interest ─────────────────────────────
    #
    # Exclude F4/ARIA records: the thesis comparison is DOM-encoding-only,
    # so we use F0–F3 aggregated.  Averaging over 4 encodings is fine because
    # this comparison is about bundle content, not encoding format.
    #
    thesis_records = df[
        df["bundle"].isin(["B_full", "B_noVolatile"])
        & df["encoding"].isin(DOM_ENCODINGS)
    ].copy()

    assert len(thesis_records) == 1920, (
        f"Expected 960 records × 2 bundles = 1,920; got {len(thesis_records)}"
    )

    # ── Per-page success rates ─────────────────────────────────────────────
    #
    # Aggregate over all 4 DOM encodings for each (page, bundle) pair.
    # Each cell = 40 records (10 tasks × 4 encodings).
    #
    page_bundle_success = (
        thesis_records
        .groupby(["page", "bundle"])["success"]
        .agg(n_success=("sum"), n_records=("count"))
    )
    page_bundle_success["success_rate"] = (
        page_bundle_success["n_success"] / page_bundle_success["n_records"]
    )

    # Pivot so each page is one row with separate columns for B_full and B_noVolatile.
    per_page_rates = page_bundle_success["success_rate"].unstack("bundle")
    per_page_rates = per_page_rates.rename(columns={
        "B_full": "b_full_rate",
        "B_noVolatile": "b_nv_rate",
    })

    # Compute the per-page delta (positive = B_noVolatile wins).
    per_page_rates["delta_pp"] = (
        (per_page_rates["b_nv_rate"] - per_page_rates["b_full_rate"]) * 100
    )

    # Re-attach semantic density (take from the index, it's the same for both bundles).
    semantic_density_by_page = (
        thesis_records[["page", "semantic_density"]]
        .drop_duplicates()
        .set_index("page")
    )
    per_page_rates = per_page_rates.join(semantic_density_by_page)

    # Sort by delta descending to match the results MD presentation.
    per_page_rates = per_page_rates.sort_values("delta_pp", ascending=False)

    # ── Count win/tie/loss pages ───────────────────────────────────────────
    nv_strictly_wins_count = (per_page_rates["delta_pp"] > 0).sum()
    bf_strictly_wins_count = (per_page_rates["delta_pp"] < 0).sum()
    ties_count             = (per_page_rates["delta_pp"] == 0).sum()

    # ── Corpus totals ──────────────────────────────────────────────────────
    corpus_summary = (
        thesis_records
        .groupby("bundle")["success"]
        .agg(n_success="sum", n_records="count")
    )
    corpus_summary["success_rate"] = (
        corpus_summary["n_success"] / corpus_summary["n_records"]
    )

    bf_success_rate = corpus_summary.loc["B_full", "success_rate"]
    nv_success_rate = corpus_summary.loc["B_noVolatile", "success_rate"]
    corpus_delta_pp = (nv_success_rate - bf_success_rate) * 100

    # ── Semantic density split ─────────────────────────────────────────────
    #
    # Does the volatile-stripping benefit concentrate on LOW-semantic pages
    # (fewer stable anchors → model grabs hashed classes as fallback) or is
    # it evenly distributed?
    #
    stratum_summary = (
        thesis_records
        .groupby(["bundle", "semantic_density"])["success"]
        .mean()
        .unstack("bundle")
    )
    stratum_summary.columns = ["b_full_rate", "b_nv_rate"]
    stratum_summary["delta_pp"] = (
        (stratum_summary["b_nv_rate"] - stratum_summary["b_full_rate"]) * 100
    )

    low_delta_pp  = stratum_summary.loc["LOW",  "delta_pp"]
    high_delta_pp = stratum_summary.loc["HIGH", "delta_pp"]

    # ── Assertions ────────────────────────────────────────────────────────
    #
    # These values are load-bearing for the paper.  If any assertion fails,
    # the underlying data or analysis logic needs investigation.
    #
    assert abs(bf_success_rate - 0.5479) < 0.001, (
        f"B_full success rate {bf_success_rate:.4f} differs from expected 0.5479"
    )
    assert abs(nv_success_rate - 0.6427) < 0.001, (
        f"B_noVolatile success rate {nv_success_rate:.4f} differs from expected 0.6427"
    )
    assert nv_strictly_wins_count == 18, (
        f"Expected B_noVolatile strictly beats B_full on 18 pages, got {nv_strictly_wins_count}"
    )
    assert bf_strictly_wins_count == 2, (
        f"Expected B_full strictly wins on 2 pages, got {bf_strictly_wins_count}"
    )
    assert abs(low_delta_pp  - 15.00) < 0.5, (
        f"LOW delta {low_delta_pp:.2f} pp differs from expected 15.00 pp"
    )
    assert abs(high_delta_pp - 3.96)  < 0.5, (
        f"HIGH delta {high_delta_pp:.2f} pp differs from expected 3.96 pp"
    )

    # ── Print tables ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("THESIS: B_full vs B_noVolatile — per-page rates")
    print(f"{'='*60}")

    per_page_display = per_page_rates.copy()
    per_page_display["B_full %"]     = (per_page_display["b_full_rate"] * 100).round(1)
    per_page_display["B_noVolatile %"] = (per_page_display["b_nv_rate"] * 100).round(1)
    per_page_display["delta pp"]     = per_page_display["delta_pp"].round(1)
    per_page_display = per_page_display[
        ["semantic_density", "B_full %", "B_noVolatile %", "delta pp"]
    ].reset_index()
    print(tabulate(per_page_display, headers="keys", tablefmt="pipe"))

    print(f"\n{'='*60}")
    print("THESIS: Corpus and semantic-density totals")
    print(f"{'='*60}")
    print(f"  B_full       : {bf_success_rate:.2%}  ({corpus_summary.loc['B_full','n_success']:.0f}/960)")
    print(f"  B_noVolatile : {nv_success_rate:.2%}  ({corpus_summary.loc['B_noVolatile','n_success']:.0f}/960)")
    print(f"  Delta        : {corpus_delta_pp:+.2f} pp")
    print(f"  NV > BF pages (strict): {nv_strictly_wins_count}")
    print(f"  BF > NV pages (strict): {bf_strictly_wins_count}")
    print(f"  Ties:                   {ties_count}")
    print(f"  LOW delta  : {low_delta_pp:+.2f} pp")
    print(f"  HIGH delta : {high_delta_pp:+.2f} pp")

    return {
        "bf_success_rate":        bf_success_rate,
        "nv_success_rate":        nv_success_rate,
        "corpus_delta_pp":        corpus_delta_pp,
        "nv_strictly_wins_count": nv_strictly_wins_count,
        "bf_strictly_wins_count": bf_strictly_wins_count,
        "ties_count":             ties_count,
        "low_delta_pp":           low_delta_pp,
        "high_delta_pp":          high_delta_pp,
        "per_page_rates":         per_page_rates,
        "stratum_summary":        stratum_summary,
    }


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).parent.parent.parent
    df = load_dataframe(repo_root)
    compute(df)
