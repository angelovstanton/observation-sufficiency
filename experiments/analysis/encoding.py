"""
encoding.py — Axis B encoding comparison within B_noVolatile.

Question: given the optimal bundle (B_noVolatile), which encoding format
gives the best success-vs-token trade-off?

The four DOM encodings are:
  F0 — HTML reconstruction of the DOM
  F1 — flat JSON with full attribute key names ("role", "name", "aria-label")
  F2 — flat JSON with abbreviated keys ("r", "n", "al") — tests whether
       abbreviation saves enough tokens to compensate for any model confusion
  F3 — linearized DSL, e.g. "button[Subscribe] role aria-label"

F2 hypothesis: abbreviating keys saves ~0% tokens (key names are a small fraction)
               but confuses the model — net harm.
F3 hypothesis: the DSL format strips JSON overhead, saving ~29% tokens at near-
               zero success cost — the recommended encoding.

Input: bundle == 'B_noVolatile', encoding ∈ {F0,F1,F2,F3}.
       240 records per encoding (24 pages × 10 tasks × 1 repetition).
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
from load import load_dataframe, DOM_ENCODINGS, DOM_BUNDLES

# Pages whose tok/element ratio (from the smoke test) puts them in a distinct
# size tier for the F3 content-dependence analysis.
# tok/el thresholds derived from smoke_all24.txt:
#   elem-dense: page_17 @ 22.6 tok/el (5,096 elements, deep shadow DOM)
#   text-dense: page_06 @ 29.8 tok/el, page_18 @ 28.2 tok/el
#   standard:   all remaining 21 pages
ELEM_DENSE_PAGES = {"page_17"}
TEXT_DENSE_PAGES = {"page_06", "page_18"}


def compute(df: pd.DataFrame) -> dict:
    """
    Compute encoding-axis statistics within B_noVolatile.
    Also produces the cross-bundle encoding pattern table.
    Returns a dict of scalar results for the reconciliation table.
    """

    # ── Filter to B_noVolatile DOM encodings ──────────────────────────────
    nv_records = df[
        (df["bundle"] == "B_noVolatile")
        & df["encoding"].isin(DOM_ENCODINGS)
    ].copy()

    assert len(nv_records) == 960, (
        f"Expected 4 encodings × 240 records = 960; got {len(nv_records)}"
    )

    # ── Per-encoding success rates and token costs ─────────────────────────
    encoding_stats = nv_records.groupby("encoding").agg(
        n_success=("success",          "sum"),
        n_records=("success",          "count"),
        mean_obs_tokens=("observation_tokens", "mean"),
    )
    encoding_stats["success_rate"] = (
        encoding_stats["n_success"] / encoding_stats["n_records"]
    )

    # LOW and HIGH success rates per encoding.
    stratum_rates = (
        nv_records
        .groupby(["encoding", "semantic_density"])["success"]
        .mean()
        .unstack("semantic_density")
    )
    encoding_stats = encoding_stats.join(stratum_rates)

    # ── Verify the aggregate matches the known corpus-wide B_noVolatile rate ──
    #
    # All four encodings together must give the same rate as the bundle-ladder
    # value.  If not, there is a filtering bug.
    #
    aggregate_success_rate = encoding_stats["n_success"].sum() / encoding_stats["n_records"].sum()
    assert abs(aggregate_success_rate - 0.6427) < 0.001, (
        f"B_noVolatile aggregate rate {aggregate_success_rate:.4f} ≠ expected 0.6427"
    )

    # ── Extract scalars for each encoding ─────────────────────────────────
    f0_success = encoding_stats.loc["F0", "success_rate"]
    f1_success = encoding_stats.loc["F1", "success_rate"]
    f2_success = encoding_stats.loc["F2", "success_rate"]
    f3_success = encoding_stats.loc["F3", "success_rate"]

    f1_mean_tokens = encoding_stats.loc["F1", "mean_obs_tokens"]
    f3_mean_tokens = encoding_stats.loc["F3", "mean_obs_tokens"]

    # ── F2 harms: abbreviated keys degrade success at identical token cost ──
    f2_harm_delta_pp = (f2_success - f1_success) * 100   # expected: negative (~−12.08)

    # ── F3 savings: DSL encoding reduces tokens with near-zero success cost ──
    f3_success_delta_pp   = (f3_success - f1_success) * 100
    f3_token_reduction_pct = (f1_mean_tokens - f3_mean_tokens) / f1_mean_tokens * 100

    # ── F3 content-dependence: savings by page size tier ──────────────────
    #
    # Hypothesis: element-dense pages should compress more (structural redundancy)
    # while text-dense pages compress less (incompressible short text strings).
    # We test this by comparing mean F3 vs F1 token counts per page.
    #
    nv_f1 = nv_records[nv_records["encoding"] == "F1"]
    nv_f3 = nv_records[nv_records["encoding"] == "F3"]

    f1_tokens_per_page = nv_f1.groupby("page")["observation_tokens"].mean().rename("f1_tok")
    f3_tokens_per_page = nv_f3.groupby("page")["observation_tokens"].mean().rename("f3_tok")

    per_page_tokens = pd.concat([f1_tokens_per_page, f3_tokens_per_page], axis=1)
    per_page_tokens["f3_savings_pct"] = (
        (per_page_tokens["f1_tok"] - per_page_tokens["f3_tok"])
        / per_page_tokens["f1_tok"] * 100
    )

    # Assign size tier based on the smoke-test tok/el ratios.
    def assign_tier(page_name: str) -> str:
        if page_name in ELEM_DENSE_PAGES:
            return "elem-dense"
        elif page_name in TEXT_DENSE_PAGES:
            return "text-dense"
        else:
            return "standard"

    per_page_tokens["tier"] = per_page_tokens.index.map(assign_tier)

    mean_savings_by_tier = (
        per_page_tokens.groupby("tier")["f3_savings_pct"].mean().round(1)
    )

    # ── Cross-bundle encoding table ────────────────────────────────────────
    #
    # Same encoding comparison repeated for all five DOM bundles — shows whether
    # F2 harm and F3 benefit are specific to B_noVolatile or are universal.
    #
    dom_records = df[
        df["bundle"].isin(DOM_BUNDLES - {"B_minimalCore"})
        & df["encoding"].isin(DOM_ENCODINGS)
    ]
    cross_bundle_rates = (
        dom_records
        .groupby(["bundle", "encoding"])["success"]
        .mean()
        .unstack("encoding")
        * 100
    ).round(1)

    # ── Assertions ────────────────────────────────────────────────────────
    assert abs(f1_success - 0.6750) < 0.001, (
        f"B_noVolatile×F1 success {f1_success:.4f} ≠ expected 0.6750"
    )
    assert abs(f2_success - 0.5542) < 0.001, (
        f"B_noVolatile×F2 success {f2_success:.4f} ≠ expected 0.5542"
    )
    assert abs(f3_success - 0.6792) < 0.001, (
        f"B_noVolatile×F3 success {f3_success:.4f} ≠ expected 0.6792"
    )
    assert abs(f2_harm_delta_pp - (-12.08)) < 0.1, (
        f"F2 harm delta {f2_harm_delta_pp:.2f} pp ≠ expected −12.08 pp"
    )
    assert abs(f3_token_reduction_pct - 29.1) < 0.5, (
        f"F3 token reduction {f3_token_reduction_pct:.1f}% ≠ expected 29.1%"
    )

    assert abs(f1_mean_tokens - 25239) <= 1, (
        f"B_noVolatile×F1 mean tokens {f1_mean_tokens:.0f} ≠ expected 25,239"
    )
    assert abs(f3_mean_tokens - 17888) <= 1, (
        f"B_noVolatile×F3 mean tokens {f3_mean_tokens:.0f} ≠ expected 17,888"
    )

    # ── Print tables ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("ENCODING: B_noVolatile × {F0,F1,F2,F3} — success and tokens")
    print(f"{'='*60}")

    enc_display = encoding_stats.copy()
    enc_display["success %"] = (enc_display["success_rate"] * 100).round(2)
    enc_display["mean tok"]  = enc_display["mean_obs_tokens"].round(0).astype(int)
    enc_display["LOW %"]     = (enc_display["LOW"]  * 100).round(2)
    enc_display["HIGH %"]    = (enc_display["HIGH"] * 100).round(2)
    print(tabulate(
        enc_display[["success %", "mean tok", "LOW %", "HIGH %"]].reset_index(),
        headers="keys", tablefmt="pipe", showindex=False,
    ))

    print(f"\n  F2 harm (F2−F1):           {f2_harm_delta_pp:+.2f} pp")
    print(f"  F3 vs F1 success delta:    {f3_success_delta_pp:+.2f} pp")
    print(f"  F3 token reduction vs F1:  {f3_token_reduction_pct:.1f}%")

    print(f"\n{'='*60}")
    print("ENCODING: F3 content-dependence by page size tier")
    print(f"{'='*60}")
    print(tabulate(
        per_page_tokens[["tier","f1_tok","f3_tok","f3_savings_pct"]].reset_index()
        .sort_values(["tier","page"]),
        headers=["page","tier","F1 tok","F3 tok","F3 save %"],
        tablefmt="pipe", showindex=False, floatfmt=".1f",
    ))
    print(f"\nMean savings by tier:")
    for tier, savings in mean_savings_by_tier.items():
        print(f"  {tier:15s}: {savings:.1f}%")

    print(f"\n{'='*60}")
    print("ENCODING: cross-bundle success% by encoding")
    print(f"{'='*60}")
    print(tabulate(cross_bundle_rates.reset_index(), headers="keys", tablefmt="pipe", showindex=False))

    return {
        "f0_success":              f0_success,
        "f1_success":              f1_success,
        "f2_success":              f2_success,
        "f3_success":              f3_success,
        "f1_mean_tokens":          f1_mean_tokens,
        "f3_mean_tokens":          f3_mean_tokens,
        "f2_harm_delta_pp":        f2_harm_delta_pp,
        "f3_success_delta_pp":     f3_success_delta_pp,
        "f3_token_reduction_pct":  f3_token_reduction_pct,
        "encoding_stats":          encoding_stats,
        "per_page_tokens":         per_page_tokens,
        "mean_savings_by_tier":    mean_savings_by_tier,
        "cross_bundle_rates":      cross_bundle_rates,
    }


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).parent.parent.parent
    df = load_dataframe(repo_root)
    compute(df)
