"""
failure_decomp.py — failure mode breakdown and mechanism analysis.

Question: why does volatile-stripping work?  The three failure modes are:
  observation_lacked_stable_signal  — no usable stable locator was in the bundle;
                                      the model had no choice but to fail.
  output_format_unreachable         — the model emitted XPath despite the CSS-only
                                      instruction AND the target sits inside a
                                      shadow root, where XPath cannot reach.
  model_grabbed_brittle_signal      — a stable signal WAS present in the bundle
                                      but the model chose a volatile/positional
                                      locator instead.

Priority (Oracle.cs, defect fix D4): lacked > unreachable > grabbed.  The
classification names the root cause, not the locator's secondary properties.
The current corpus contains zero unreachable records; the mode is handled
throughout so that a future record carrying it is counted in its own category
rather than crashing the module or being folded into another mode.

The mechanism hypothesis: volatile-stripping (B_full → B_noVolatile) removes
decoy signals the model was grabbing.  If correct:
  Δgrabbed_brittle (B_full − B_noVolatile) ≈ success gain (+91)
  Δlacked          (B_full − B_noVolatile) ≈ 0    (lacked floor is unchanged)

Also confirms the F4 ARIA-collapse diagnosis: all 79 F4 failures classified as
'model_grabbed_brittle_signal' have stable_signal_present_in_bundle=True (the
signal is in the DOM but collapsed by the ARIA tree, invisible to the model).

Input: all 6,000 records.
Expected: Δgrabbed = −91, Δlacked = 0.  Exact, not approximate.
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

LACKED      = "observation_lacked_stable_signal"
GRABBED     = "model_grabbed_brittle_signal"
UNREACHABLE = "output_format_unreachable"

CANONICAL_FAILURE_MODES = {LACKED, GRABBED, UNREACHABLE}

# All bundles that appear in the failure analysis (including the ARIA one).
ALL_BUNDLES_ORDERED = [
    "B_full", "B_noVolatile", "B_noState", "B_noSemantic",
    "B_identityCore", "B_minimalCore", "B_playwrightMCP",
]


def decompose_modes(failure_records: pd.DataFrame) -> dict:
    """
    Catalogue and count the three canonical failure modes (§6), and check the
    SSP identity.  Returns {"total", "lacked", "grabbed", "unreachable"}.

    A pure helper over an explicit record set so it can be exercised on synthetic
    data — unlike compute(), which also asserts corpus-specific values
    (total_lacked == 2584 and so on) that no synthetic set can satisfy. This holds
    the taxonomy contract alone, and is what test_failure_modes.py targets.
    """

    assert failure_records["failure_mode"].notna().all(), (
        "Some failure records have a null failure_mode — schema bug in the harness"
    )

    # Every observed mode must be one of the three canonical ones.  A mode
    # outside that set means the harness emitted a category the analysis does
    # not know how to decompose.  This is a subset check, not equality: a mode
    # being absent is not an error (the current corpus has no unreachable).
    unique_failure_modes = set(failure_records["failure_mode"].unique())
    assert unique_failure_modes <= CANONICAL_FAILURE_MODES, (
        f"Unexpected failure modes found: {unique_failure_modes - CANONICAL_FAILURE_MODES}"
    )

    total_failures    = len(failure_records)
    total_lacked      = (failure_records["failure_mode"] == LACKED).sum()
    total_grabbed     = (failure_records["failure_mode"] == GRABBED).sum()
    total_unreachable = (failure_records["failure_mode"] == UNREACHABLE).sum()

    assert total_lacked + total_grabbed + total_unreachable == total_failures

    # stable_signal_present_in_bundle == True means a stable locator existed in
    # the bundle.  A False value means there was no stable signal → 'lacked',
    # which wins over every other mode (D4 priority).
    #
    # SSP=True therefore covers BOTH remaining modes: 'grabbed_brittle' and
    # 'unreachable'.  Unreachable can only fire when a stable signal was present
    # (lacked takes precedence otherwise), so it lives on the SSP=True side of
    # this identity — it must not be compared against grabbed alone.
    ssp_true_on_failures  = failure_records["stable_signal_present_in_bundle"].sum()
    ssp_false_on_failures = (~failure_records["stable_signal_present_in_bundle"]).sum()

    assert ssp_true_on_failures  == total_grabbed + total_unreachable, (
        f"SSP=True count ({ssp_true_on_failures}) ≠ grabbed_brittle + unreachable "
        f"({total_grabbed} + {total_unreachable})"
    )
    assert ssp_false_on_failures == total_lacked, (
        f"SSP=False count ({ssp_false_on_failures}) ≠ lacked count ({total_lacked})"
    )

    return {
        "total":       total_failures,
        "lacked":      total_lacked,
        "grabbed":     total_grabbed,
        "unreachable": total_unreachable,
    }


def build_nv_residual(lacked_by_enc, grabbed_by_enc, unreachable_by_enc) -> pd.DataFrame:
    """
    Assemble the B_noVolatile "residual by encoding" table across all three
    failure modes.  Each argument is a per-encoding Series (groupby-size).

    A pure helper so the three-mode denominator can be unit-tested:
    total_fail = lacked + grabbed + unreachable — folding unreachable in so a
    future output_format_unreachable record cannot be silently dropped from the
    total (which would skew the lacked%/grabbed% denominators).

    A groupby-size Series is EMPTY when its mode has zero records, so aligning it
    onto the DataFrame yields NaN — reindex with fill_value=0 before summing.
    The current corpus has zero unreachable records: the unreachable column is
    all-zero and the lacked/grabbed percentages are identical to the two-mode
    form, by construction.
    """
    residual = pd.DataFrame({
        "lacked":  lacked_by_enc,
        "grabbed": grabbed_by_enc,
    })
    residual["unreachable"] = (
        unreachable_by_enc.reindex(residual.index, fill_value=0).astype(int)
    )
    residual["total_fail"]  = residual["lacked"] + residual["grabbed"] + residual["unreachable"]
    residual["lacked %"]      = (residual["lacked"]      / residual["total_fail"] * 100).round(1)
    residual["grabbed %"]     = (residual["grabbed"]     / residual["total_fail"] * 100).round(1)
    residual["unreachable %"] = (residual["unreachable"] / residual["total_fail"] * 100).round(1)
    return residual


def compute(df: pd.DataFrame) -> dict:
    """
    Decompose failures by mode, bundle, semantic stratum, and encoding.
    Returns a dict of scalar results for the reconciliation table.
    """

    # ── Isolate failed records ─────────────────────────────────────────────
    #
    # Only records where success=False.  The failure_mode column must be
    # non-null on every failure (the harness sets it unconditionally).
    #
    failure_records = df[df["success"] == False].copy()

    # ── Catalogue failure modes + overall breakdown ────────────────────────
    _modes            = decompose_modes(failure_records)
    total_failures    = _modes["total"]
    total_lacked      = _modes["lacked"]
    total_grabbed     = _modes["grabbed"]
    total_unreachable = _modes["unreachable"]

    # ── Per-bundle failure breakdown ───────────────────────────────────────
    all_records_by_bundle = df.groupby("bundle")["success"].count().rename("n_all")

    bundle_failure_stats_rows = []
    for bundle_name in ALL_BUNDLES_ORDERED:
        bundle_failures = failure_records[failure_records["bundle"] == bundle_name]
        n_fail        = len(bundle_failures)
        n_lacked      = (bundle_failures["failure_mode"] == LACKED).sum()
        n_grabbed     = (bundle_failures["failure_mode"] == GRABBED).sum()
        n_unreachable = (bundle_failures["failure_mode"] == UNREACHABLE).sum()
        n_all         = all_records_by_bundle.get(bundle_name, 0)

        bundle_failure_stats_rows.append({
            "bundle":         bundle_name,
            "total_fail":     n_fail,
            "lacked_n":       n_lacked,
            "lacked_pct":     round(n_lacked  / n_fail * 100, 1) if n_fail > 0 else 0.0,
            "grabbed_n":      n_grabbed,
            "grabbed_pct":    round(n_grabbed / n_fail * 100, 1) if n_fail > 0 else 0.0,
            "grabbed_of_all_pct": round(n_grabbed / n_all * 100, 1) if n_all > 0 else 0.0,
            "unreachable_n":  n_unreachable,
        })

    bundle_failure_stats = pd.DataFrame(bundle_failure_stats_rows).set_index("bundle")

    # ── Mechanism metric: B_full → B_noVolatile ───────────────────────────
    #
    # If volatile-stripping works by eliminating decoy signals:
    #   success gain = +91  (from bundle_ladder analysis)
    #   Δgrabbed_brittle should equal −91 (net: 102 grabbed→success recoveries minus 11 success→grabbed regressions)
    #     of the 102 recoveries: 90 genuine volatile grabs (predicate_non_volatile=false under B_full),
    #     12 non-resolving under B_full (unique_match/matches_oracle false) that resolved once volatile attrs stripped
    #   Δlacked should equal 0 (stripping cannot add signal; the lacked floor is fixed)
    #
    bf_grabbed = bundle_failure_stats.loc["B_full",       "grabbed_n"]
    nv_grabbed = bundle_failure_stats.loc["B_noVolatile", "grabbed_n"]
    bf_lacked  = bundle_failure_stats.loc["B_full",       "lacked_n"]
    nv_lacked  = bundle_failure_stats.loc["B_noVolatile", "lacked_n"]

    delta_grabbed = int(nv_grabbed - bf_grabbed)   # expected: −91
    delta_lacked  = int(nv_lacked  - bf_lacked)    # expected: 0

    nv_success_count = df[df["bundle"] == "B_noVolatile"]["success"].sum()
    bf_success_count = df[df["bundle"] == "B_full"      ]["success"].sum()
    success_gain     = int(nv_success_count - bf_success_count)   # expected: +91

    # ── Semantic stratum breakdown for B_full and B_noVolatile ────────────
    #
    # Does the mechanism operate differently on HIGH vs LOW semantic pages?
    # Hypothesis: LOW pages show a larger grabbed_brittle → success conversion
    # because the model relied more on volatile signals in the absence of stable
    # semantic anchors.
    #
    stratum_rows = []
    for bundle_name in ["B_full", "B_noVolatile"]:
        for stratum in ["LOW", "HIGH"]:
            subset = failure_records[
                (failure_records["bundle"] == bundle_name)
                & (failure_records["semantic_density"] == stratum)
            ]
            n_fail        = len(subset)
            n_lacked      = (subset["failure_mode"] == LACKED).sum()
            n_grabbed     = (subset["failure_mode"] == GRABBED).sum()
            n_unreachable = (subset["failure_mode"] == UNREACHABLE).sum()
            stratum_rows.append({
                "bundle":      bundle_name,
                "sem":         stratum,
                "total_fail":  n_fail,
                "lacked_n":    n_lacked,
                "lacked_pct":  round(n_lacked  / n_fail * 100, 1) if n_fail > 0 else 0.0,
                "grabbed_n":   n_grabbed,
                "grabbed_pct": round(n_grabbed / n_fail * 100, 1) if n_fail > 0 else 0.0,
                "unreachable_n": n_unreachable,
            })
    stratum_failure_stats = pd.DataFrame(stratum_rows)

    # ── F4 ARIA-collapse diagnosis ─────────────────────────────────────────
    #
    # For B_playwrightMCP×F4, stable_signal_present_in_bundle uses BundleFull
    # (the audit-corrected predicate via AttributeBundles.ResolveBundleSetForSignalCheck).  So SSP=True means
    # "stable signal in the full DOM" — not in the ARIA snapshot.
    #
    # F4 failures with SSP=True are ARIA-collapse cases: the signal was in the
    # DOM but the ARIA tree collapsed it.  The failure_mode field labels them as
    # 'grabbed_brittle' (because SSP checks BundleFull), but from the model's
    # perspective they are observation-lacked (the signal was never in the F4
    # observation the model saw).
    #
    f4_failures = failure_records[failure_records["bundle"] == "B_playwrightMCP"]
    f4_lacked_count      = (f4_failures["failure_mode"] == LACKED).sum()
    f4_grabbed_count     = (f4_failures["failure_mode"] == GRABBED).sum()
    f4_unreachable_count = (f4_failures["failure_mode"] == UNREACHABLE).sum()

    # All F4 grabbed failures must have SSP=True (ARIA-collapse, not model error).
    f4_grabbed_failures = f4_failures[f4_failures["failure_mode"] == GRABBED]
    all_f4_grabbed_have_ssp_true = f4_grabbed_failures["stable_signal_present_in_bundle"].all()

    # ── B_noVolatile residual by encoding ─────────────────────────────────
    #
    # The 'lacked' count should be identical across all four B_noVolatile encodings
    # because 'lacked' is a property of the bundle's signal content, not the encoding
    # format.  Encoding changes how the signal is serialised, not which signals exist.
    #
    nv_failures = failure_records[failure_records["bundle"] == "B_noVolatile"]

    nv_lacked_by_encoding = (
        nv_failures[nv_failures["failure_mode"] == LACKED]
        .groupby("encoding")
        .size()
    )
    nv_grabbed_by_encoding = (
        nv_failures[nv_failures["failure_mode"] == GRABBED]
        .groupby("encoding")
        .size()
    )
    nv_unreachable_by_encoding = (
        nv_failures[nv_failures["failure_mode"] == UNREACHABLE]
        .groupby("encoding")
        .size()
    )

    # ── Assertions ────────────────────────────────────────────────────────
    assert total_lacked  == 2584, f"Total lacked  {total_lacked} ≠ 2,584"
    assert total_grabbed == 912,  f"Total grabbed {total_grabbed} ≠ 912"

    assert int(bf_lacked)  == 192, f"B_full lacked  {bf_lacked} ≠ 192"
    assert int(bf_grabbed) == 242, f"B_full grabbed {bf_grabbed} ≠ 242"
    assert int(nv_lacked)  == 192, f"B_noVolatile lacked  {nv_lacked} ≠ 192"
    assert int(nv_grabbed) == 151, f"B_noVolatile grabbed {nv_grabbed} ≠ 151"

    assert delta_grabbed == -91, (
        f"Δgrabbed (NV−BF) = {delta_grabbed}, expected −91"
    )
    assert delta_lacked  ==   0, (
        f"Δlacked  (NV−BF) = {delta_lacked},  expected 0"
    )
    assert success_gain  ==  91, (
        f"Success gain (NV−BF) = {success_gain}, expected +91"
    )

    assert int(f4_lacked_count)  == 48, f"F4 lacked  {f4_lacked_count} ≠ 48"
    assert int(f4_grabbed_count) == 79, f"F4 grabbed {f4_grabbed_count} ≠ 79"
    assert all_f4_grabbed_have_ssp_true, (
        "Some F4 grabbed_brittle failures have SSP=False — unexpected; "
        "re-check audit-corrected predicate"
    )

    # The lacked count must be identical for all 4 B_noVolatile encodings.
    # This is the encoding-invariance property: lacked is determined by bundle content.
    assert set(nv_lacked_by_encoding.unique()) == {48}, (
        f"B_noVolatile lacked count varies by encoding: {nv_lacked_by_encoding.to_dict()}"
        " — expected 48 for all four encodings"
    )

    # ── Print tables ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("FAILURE DECOMP: overall breakdown")
    print(f"{'='*60}")
    print(f"  Total failures:  {total_failures:,}")
    print(f"  lacked:          {total_lacked:,}  ({total_lacked/total_failures:.1%})")
    print(f"  grabbed_brittle: {total_grabbed:,}  ({total_grabbed/total_failures:.1%})")
    print(f"  unreachable:     {total_unreachable:,}  ({total_unreachable/total_failures:.1%})")

    print(f"\n{'='*60}")
    print("FAILURE DECOMP: per-bundle breakdown")
    print(f"{'='*60}")
    print(tabulate(bundle_failure_stats.reset_index(), headers="keys", tablefmt="pipe", showindex=False))

    print(f"\n  Mechanism metric (B_full → B_noVolatile):")
    print(f"  Success gain:    {success_gain:+d} records")
    print(f"  Δgrabbed:        {delta_grabbed:+d} records  (expect −91)")
    print(f"  Δlacked:         {delta_lacked:+d}  records  (expect  0)")

    print(f"\n{'='*60}")
    print("FAILURE DECOMP: semantic-stratum breakdown (B_full and B_noVolatile)")
    print(f"{'='*60}")
    print(tabulate(stratum_failure_stats, headers="keys", tablefmt="pipe", showindex=False))

    print(f"\n{'='*60}")
    print("FAILURE DECOMP: B_playwrightMCP×F4 — ARIA-collapse diagnosis")
    print(f"{'='*60}")
    # Percentages computed from the live counts (never hardcoded), over all three
    # modes so the denominator can't silently drop a future unreachable record.
    f4_total = int(f4_lacked_count) + int(f4_grabbed_count) + int(f4_unreachable_count)
    print(f"  F4 lacked  (SSP=False, no DOM signal):  {f4_lacked_count}  ({f4_lacked_count/f4_total:.1%})")
    print(f"  F4 grabbed (SSP=True, ARIA-collapsed):  {f4_grabbed_count}  ({f4_grabbed_count/f4_total:.1%})")
    print(f"  All F4 grabbed have SSP=True: {all_f4_grabbed_have_ssp_true}")

    print(f"\n{'='*60}")
    print("FAILURE DECOMP: B_noVolatile residual by encoding")
    print(f"{'='*60}")
    residual = build_nv_residual(
        nv_lacked_by_encoding, nv_grabbed_by_encoding, nv_unreachable_by_encoding
    )
    print(tabulate(residual.reset_index(), headers="keys", tablefmt="pipe", showindex=False))
    unique_lacked = int(nv_lacked_by_encoding.unique()[0])
    print(f"  (lacked count is {unique_lacked} for all encodings — encoding-invariant)")

    return {
        "total_lacked":          total_lacked,
        "total_grabbed":         total_grabbed,
        "total_unreachable":     total_unreachable,
        "bf_lacked":             int(bf_lacked),
        "bf_grabbed":            int(bf_grabbed),
        "nv_lacked":             int(nv_lacked),
        "nv_grabbed":            int(nv_grabbed),
        "delta_grabbed":         delta_grabbed,
        "delta_lacked":          delta_lacked,
        "success_gain":          success_gain,
        "f4_lacked_count":       int(f4_lacked_count),
        "f4_grabbed_count":      int(f4_grabbed_count),
        "f4_unreachable_count":  int(f4_unreachable_count),
        "all_f4_grabbed_ssp":    bool(all_f4_grabbed_have_ssp_true),
        "nv_lacked_by_encoding": nv_lacked_by_encoding.to_dict(),
        "nv_unreachable_by_encoding": nv_unreachable_by_encoding.to_dict(),
        "bundle_failure_stats":  bundle_failure_stats,
        "stratum_failure_stats": stratum_failure_stats,
    }


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).parent.parent.parent
    df = load_dataframe(repo_root)
    compute(df)
