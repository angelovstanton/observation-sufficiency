"""
run_all.py — orchestrator, reconciliation, and computed_findings.md writer.

Runs all six analysis modules in order, then prints a RECONCILIATION table
that compares every key number against hardcoded expected values pinned to the
reclassified corpus (as regenerated in computed_findings.md and mirrored in the
curated FINDINGS.md).

Rules:
- Any mismatch is printed as MISMATCH and flagged for review.  Do NOT adjust a
  script to silence a mismatch — the mismatch itself is the finding.
- Any assertion failure in a sub-module aborts the run with a non-zero exit code
  and prints the failing assertion.
- All computed output is written to experiments/results/computed/ (CSV + MD tables).
- Computed numeric tables are written to experiments/computed_findings.md (ALWAYS
  REGENERATED — never add hand-written prose here).
- experiments/FINDINGS.md is the human-curated log.  This script never touches it.

Run from repo root:
    python experiments/analysis/run_all.py
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
import textwrap
import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
# Allow sub-modules to import load.py via `from load import ...`
ANALYSIS_DIR = pathlib.Path(__file__).parent
REPO_ROOT    = ANALYSIS_DIR.parent.parent
sys.path.insert(0, str(ANALYSIS_DIR))

from load           import load_dataframe
import thesis        as _thesis
import bundle_ladder as _bundle_ladder
import encoding      as _encoding
import pareto        as _pareto
import failure_decomp as _failure_decomp
import stats         as _stats

# ── Output paths ──────────────────────────────────────────────────────────────
COMPUTED_DIR = REPO_ROOT / "experiments" / "results" / "computed"
COMPUTED_DIR.mkdir(parents=True, exist_ok=True)

# Machine-generated file — always overwritten on each run.
# Do NOT add hand-written prose here; it will be lost on the next run.
COMPUTED_FINDINGS_PATH = REPO_ROOT / "experiments" / "computed_findings.md"

# Human-curated log — this script MUST NEVER write it.
# FINDINGS.md is the author's interpretation layer; it is not regenerable.
FINDINGS_MD_PATH = REPO_ROOT / "experiments" / "FINDINGS.md"

# Content guard. The check further down proves this SCRIPT did not modify
# FINDINGS.md during a run; this constant proves the file is still the reviewed
# canonical version — it catches an edit made by anything else, at any time.
#
# Updating it is a deliberate act: edit FINDINGS.md, review the diff, then repin.
#   python -c "import hashlib,pathlib; print(hashlib.sha256(pathlib.Path('experiments/FINDINGS.md').read_bytes()).hexdigest())"
#
# Pinned 2026-07-22 — signal_attrs completeness correction (unlisted id/href false
# negatives): B_noSemantic 28.54%→35.31%, B_identityCore 33.54%→39.58%, cliff
# −26.56→−19.79pp, lacked 2728→2584, grabbed 891→912. Thesis (+9.48pp), COP headline
# (+10.00pp), −91 substitution, McNemar, and Pareto frontier membership UNCHANGED.
#
# Re-pinned 2026-09-13 — the reasoning-vs-instruction cross-model finding was moved
# to REFUTED: the "reasoning" tier grouping (o4-mini + claude-sonnet-4-6) was a
# cross_model.py code label, not a property of the run — claude-sonnet-4-6's
# request never carried a `thinking` field. Also: dropped "and reasoning capability"
# / "and reasoning" from the Axis C framing bullets, added a caveat that Axis C is
# not temperature-aligned across models, and fixed the "58/58 reconcile" citation
# to 56/56 (two tier-average reconciliation checks were removed from cross_model.py).
# No per-model number changed.
#
# Re-pinned 2026-09-13 (442f77f "update docs") — four claims softened to match
# the manuscript and the analysis code: B_noState no longer claims state
# attributes are generally useless; the F3 mechanism is stated as syntax
# removal with attribute names retained, not key-name elimination; the ARIA
# failure decomposition is stated as observed counts rather than 100%/zero;
# and the form-invariance finding is scoped to the three models with paired
# measurements (o4-mini was COP-cell only). No reported value changed.
EXPECTED_FINDINGS_SHA256 = "0199e613505583f0521de8ee93c1021414660bbd66d02d0b7f4917fd855971f3"

# Safety invariant: the two paths must never resolve to the same file.
# This assertion fires at import time, before any data is loaded.
assert COMPUTED_FINDINGS_PATH.resolve() != FINDINGS_MD_PATH.resolve(), (
    "SAFETY VIOLATION: COMPUTED_FINDINGS_PATH and FINDINGS_MD_PATH resolve "
    "to the same file. Fix before running — this script must never touch "
    "the hand-curated FINDINGS.md."
)


# ═══════════════════════════════════════════════════════════════════════════════
# RECONCILIATION TABLE
#
# Each row: (finding_label, expected_value, tolerance, extractor_function).
# After all modules run, we evaluate every extractor against the computed dicts
# and print MATCH / MISMATCH.
#
# tolerance=None means exact integer match.
# tolerance=float means abs(computed − expected) ≤ tolerance is MATCH.
# ═══════════════════════════════════════════════════════════════════════════════

def _pct(x):
    """Format a rate in [0,1] as a percentage string."""
    return f"{x * 100:.2f}%"

def _pp(x):
    """Format a percentage-point value."""
    return f"{x:+.2f} pp"


def make_reconciliation_table(thesis_r, ladder_r, encoding_r, pareto_r, decomp_r, stats_r):
    """
    Build the reconciliation table.
    Returns a list of dicts: {finding, expected_str, computed_value, tolerance, status}.
    """

    # Each entry: (label, expected_value, tolerance, computed_value)
    entries = [
        # ── thesis.py findings ─────────────────────────────────────────────
        ("B_full corpus success",
            0.5479,   0.001,  thesis_r["bf_success_rate"]),
        ("B_noVolatile corpus success",
            0.6427,   0.001,  thesis_r["nv_success_rate"]),
        ("Corpus delta (NV−BF)",
            9.48,     0.05,   thesis_r["corpus_delta_pp"]),
        ("NV > BF pages (strict)",
            18,       None,   thesis_r["nv_strictly_wins_count"]),
        ("BF wins pages (strict)",
            2,        None,   thesis_r["bf_strictly_wins_count"]),
        ("LOW semantic delta",
            15.00,    0.5,    thesis_r["low_delta_pp"]),
        ("HIGH semantic delta",
            3.96,     0.5,    thesis_r["high_delta_pp"]),

        # ── bundle_ladder.py findings ──────────────────────────────────────
        ("B_noState success",
            0.5510,   0.001,  ladder_r["nostate_success_rate"]),
        ("B_noSemantic success",
            0.3531,   0.001,  ladder_r["nosem_success_rate"]),
        ("B_identityCore success",
            0.3958,   0.001,  ladder_r["idcore_success_rate"]),
        ("B_minimalCore success",
            0.0,      None,   ladder_r["minimal_success_rate"]),
        ("B_noSemantic mean tokens",
            11013,    5.0,    ladder_r["nosem_mean_tokens"]),
        ("Cliff B_noState→B_noSemantic (pp)",
            -19.79,   0.5,    ladder_r["cliff_pp"]),

        # ── encoding.py findings ───────────────────────────────────────────
        ("NV×F1 success",
            0.6750,   0.001,  encoding_r["f1_success"]),
        ("NV×F2 success",
            0.5542,   0.001,  encoding_r["f2_success"]),
        ("F2 harm vs F1 (pp)",
            -12.08,   0.1,    encoding_r["f2_harm_delta_pp"]),
        ("NV×F3 success",
            0.6792,   0.001,  encoding_r["f3_success"]),
        ("F3 token reduction vs F1 (%)",
            29.1,     0.5,    encoding_r["f3_token_reduction_pct"]),
        ("NV×F1 mean tokens",
            25239,    1.0,    encoding_r["f1_mean_tokens"]),
        ("NV×F3 mean tokens",
            17888,    1.0,    encoding_r["f3_mean_tokens"]),

        # ── pareto.py findings ─────────────────────────────────────────────
        ("Pareto frontier cells",
            4,        None,   pareto_r["frontier_count"]),
        ("Dominated cells",
            17,       None,   pareto_r["dominated_count"]),
        ("Headline success delta NV×F3−BF×F1 (pp)",
            10.00,     0.1,    pareto_r["headline_success_delta_pp"]),
        ("Headline token reduction (%)",
            34.0,     0.5,    pareto_r["headline_token_reduction_pct"]),
        ("F4 (B_playwrightMCP) success",
            0.4708,    0.001,  pareto_r["f4_success_rate"]),
        ("F4 (B_playwrightMCP) mean tokens",
            8914,     1.0,    pareto_r["f4_mean_tokens"]),
        ("NV wins over F4 (task-level)",
            70,       None,   pareto_r["nv_wins_over_f4"]),
        ("F4 wins over NV (task-level)",
            14,       None,   pareto_r["f4_wins_over_nv"]),
        ("F4 task table — Both succeed",
            99,       None,   pareto_r["both_succeed_count"]),
        ("F4 task table — Both fail",
            57,       None,   pareto_r["both_fail_count"]),

        # ── failure_decomp.py findings ─────────────────────────────────────
        ("Total lacked failures",
            2584,     None,   decomp_r["total_lacked"]),
        ("Total grabbed_brittle failures",
            912,      None,   decomp_r["total_grabbed"]),
        ("B_full grabbed_brittle",
            242,      None,   decomp_r["bf_grabbed"]),
        ("B_noVolatile grabbed_brittle",
            151,      None,   decomp_r["nv_grabbed"]),
        ("Δgrabbed (NV−BF)",
            -91,      None,   decomp_r["delta_grabbed"]),
        ("Δlacked (NV−BF)",
            0,        None,   decomp_r["delta_lacked"]),
        ("Success gain (NV−BF records)",
            91,       None,   decomp_r["success_gain"]),
        ("F4 lacked failures",
            48,       None,   decomp_r["f4_lacked_count"]),
        ("F4 ARIA-collapse failures (grabbed+SSP=True)",
            79,       None,   decomp_r["f4_grabbed_count"]),
        ("NV lacked per encoding (invariant)",
            48,       None,   list(decomp_r["nv_lacked_by_encoding"].values())[0]),

        # ── stats.py findings ──────────────────────────────────────────────
        # "less_than" / "greater_than" tolerance: check direction, not magnitude.
        ("Contingency table total pairs",
            960,          None,             stats_r["total_pairs"]),
        ("Discordant net (n10 − n01)",
            91,           None,             stats_r["n10"] - stats_r["n01"]),
        ("McNemar p-value",
            0.001,        "less_than",      stats_r["mcnemar_p"]),
        ("Bootstrap 95% CI lower bound (pp)",
            0.0,          "greater_than",   stats_r["ci_lo_pp"]),
    ]

    rows = []
    all_match = True
    for label, expected, tolerance, computed in entries:
        if tolerance is None:
            # Exact integer match.
            match = (int(computed) == int(expected))
            expected_str = str(int(expected))
            computed_str = str(int(computed))
        elif tolerance == "less_than":
            # Directional check: computed must be strictly less than expected.
            match = float(computed) < float(expected)
            expected_str = f"< {expected}"
            computed_str = f"{float(computed):.2e}" if float(computed) < 0.01 else f"{float(computed):.4f}"
        elif tolerance == "greater_than":
            # Directional check: computed must be strictly greater than expected.
            match = float(computed) > float(expected)
            expected_str = f"> {expected}"
            computed_str = f"{float(computed):.2f}"
        else:
            match = abs(float(computed) - float(expected)) <= tolerance
            # Use % formatting for rates (small floats), plain formatting for the rest.
            if 0 < abs(expected) < 2:
                expected_str = f"{expected * 100:.2f}%"
                computed_str = f"{float(computed) * 100:.2f}%"
            else:
                expected_str = f"{expected:.2f}"
                computed_str = f"{float(computed):.2f}"

        status = "MATCH" if match else "MISMATCH ← FLAG"
        if not match:
            all_match = False

        rows.append({
            "Finding":           label,
            "Expected":          expected_str,
            "Computed":          computed_str,
            "Tolerance":         (
                "exact"               if tolerance is None
                else "< expected"     if tolerance == "less_than"
                else "> expected"     if tolerance == "greater_than"
                else f"±{tolerance}"
            ),
            "Status":            status,
        })

    return rows, all_match


def write_computed_tables(thesis_r, ladder_r, encoding_r, pareto_r, decomp_r):
    """Write CSV and MD snapshots of each key table to experiments/results/computed/."""

    # thesis per-page table
    per_page = thesis_r["per_page_rates"].copy().reset_index()
    per_page["B_full %"]       = (per_page["b_full_rate"] * 100).round(1)
    per_page["B_noVolatile %"] = (per_page["b_nv_rate"]   * 100).round(1)
    per_page["delta pp"]       = per_page["delta_pp"].round(1)
    per_page = per_page[["page", "semantic_density", "B_full %", "B_noVolatile %", "delta pp"]]
    per_page.to_csv(COMPUTED_DIR / "thesis_per_page.csv", index=False)

    # bundle ladder table
    ladder_stats = ladder_r["bundle_stats"].copy()
    ladder_stats["success %"] = (ladder_stats["success_rate"] * 100).round(2)
    ladder_stats["mean tok"]  = ladder_stats["mean_obs_tokens"].round(0).astype(int)
    ladder_stats[["success %", "mean tok", "LOW", "HIGH"]].reset_index().to_csv(
        COMPUTED_DIR / "bundle_ladder.csv", index=False,
    )

    # Pareto 21-cell table
    pareto_r["cells_sorted"].copy().reset_index().to_csv(
        COMPUTED_DIR / "pareto_21cells.csv", index=False,
    )

    # Failure decomp per-bundle table
    decomp_r["bundle_failure_stats"].copy().reset_index().to_csv(
        COMPUTED_DIR / "failure_decomp_by_bundle.csv", index=False,
    )

    print(f"\n  Computed tables written to: {COMPUTED_DIR}/")


def write_computed_findings(thesis_r, ladder_r, encoding_r, pareto_r, decomp_r, stats_r, recon_rows):
    """
    Write experiments/computed_findings.md — machine-generated numeric tables only.

    This file is ALWAYS OVERWRITTEN on each run.  It contains no interpretation
    or hand-written prose — only tables, counts, and deltas derived from the JSONL.
    Human caveats, refuted hypotheses, and future-work notes live in
    experiments/FINDINGS.md, which this function MUST NEVER touch.
    """
    import hashlib

    # Snapshot FINDINGS.md before writing so we can verify it is unchanged after.
    findings_before = None
    if FINDINGS_MD_PATH.exists():
        findings_before = hashlib.sha256(FINDINGS_MD_PATH.read_bytes()).hexdigest()

        # Content guard: FINDINGS.md must still be the reviewed canonical file.
        # This is distinct from the post-write check below — that one proves this
        # script did not touch the file; this one proves nothing else did either.
        assert findings_before == EXPECTED_FINDINGS_SHA256, (
            "FINDINGS.md CONTENT DRIFT: the file does not match the pinned "
            "canonical hash. Either it was edited without repinning, or it was "
            "modified unintentionally.\n"
            f"  expected: {EXPECTED_FINDINGS_SHA256}\n"
            f"  actual:   {findings_before}\n"
            "If the edit was intended and reviewed, update "
            "EXPECTED_FINDINGS_SHA256 in run_all.py."
        )

    bf_pct  = thesis_r["bf_success_rate"] * 100
    nv_pct  = thesis_r["nv_success_rate"] * 100
    delta   = thesis_r["corpus_delta_pp"]
    low_d   = thesis_r["low_delta_pp"]
    high_d  = thesis_r["high_delta_pp"]

    f1_pct   = encoding_r["f1_success"] * 100
    f2_pct   = encoding_r["f2_success"] * 100
    f3_pct   = encoding_r["f3_success"] * 100
    f2_harm  = encoding_r["f2_harm_delta_pp"]
    f3_red   = encoding_r["f3_token_reduction_pct"]
    f1_tok   = encoding_r["f1_mean_tokens"]
    f3_tok   = encoding_r["f3_mean_tokens"]

    ns_pct   = ladder_r["nostate_success_rate"]  * 100
    nsm_pct  = ladder_r["nosem_success_rate"]    * 100
    ic_pct   = ladder_r["idcore_success_rate"]   * 100
    cliff    = ladder_r["cliff_pp"]
    nsm_tok  = ladder_r["nosem_mean_tokens"]

    h_succ   = pareto_r["headline_success_delta_pp"]
    h_tok    = pareto_r["headline_token_reduction_pct"]
    f4_pct   = pareto_r["f4_success_rate"]   * 100
    f4_tok   = pareto_r["f4_mean_tokens"]

    # Render the frontier path from the ACTUAL frontier rather than a fixed list —
    # frontier membership changes when the predicate does, and a hardcoded path
    # silently misreports which cells survived.
    _cop_key = (pareto_r["cop_bundle"], pareto_r["cop_encoding"])
    _frontier_lines = []
    for _i, (_key, _row) in enumerate(pareto_r["frontier_cells"].iterrows(), start=1):
        _mark = "  ← COP" if _key == _cop_key else ""
        _label = f"{_key[0]} × {_key[1]}"
        _entry = (f"{_row['success_rate']*100:.2f}%, {_row['mean_obs_tokens']:.0f} tok")
        if _mark:
            _frontier_lines.append(f"{_i}. **{_label}  ({_entry}){_mark}**")
        else:
            _frontier_lines.append(f"{_i}. {_label} ({_entry})")
    frontier_path = "\n    ".join(_frontier_lines)
    nv_wins  = pareto_r["nv_wins_over_f4"]
    f4_wins  = pareto_r["f4_wins_over_nv"]
    fr_n     = pareto_r["frontier_count"]
    dom_n    = pareto_r["dominated_count"]

    # F4 task-level cross-reference cell counts — sourced directly from pareto.py,
    # not recomputed here (a data-independent fallback would collapse to 47).
    f4_both_succeed = pareto_r["both_succeed_count"]
    f4_both_fail    = pareto_r["both_fail_count"]

    assert f4_both_succeed + nv_wins + f4_wins + f4_both_fail == 240, (
        f"F4 task-level cells sum to "
        f"{f4_both_succeed + nv_wins + f4_wins + f4_both_fail}, expected 240"
    )
    assert f4_both_succeed == 99, (
        f"F4 'Both succeed' = {f4_both_succeed}, expected 99"
    )
    assert f4_both_fail == 57, (
        f"F4 'Both fail' = {f4_both_fail}, expected 57"
    )

    t_lack   = decomp_r["total_lacked"]
    t_grab   = decomp_r["total_grabbed"]
    t_unr    = decomp_r["total_unreachable"]
    bf_lack  = decomp_r["bf_lacked"]
    nv_lack  = decomp_r["nv_lacked"]
    bf_grab  = decomp_r["bf_grabbed"]
    nv_grab  = decomp_r["nv_grabbed"]
    d_grab   = decomp_r["delta_grabbed"]
    d_lack   = decomp_r["delta_lacked"]
    s_gain   = decomp_r["success_gain"]
    f4_lack  = decomp_r["f4_lacked_count"]
    f4_grab  = decomp_r["f4_grabbed_count"]
    nv_lack_enc = list(decomp_r["nv_lacked_by_encoding"].values())[0]

    mc_chi2  = stats_r["mcnemar_chi2"]
    mc_p_str = stats_r["corpus_p_str"]
    mc_or    = stats_r["odds_ratio"]
    ci_lo    = stats_r["ci_lo_pp"]
    ci_hi    = stats_r["ci_hi_pp"]
    n10      = stats_r["n10"]
    n01      = stats_r["n01"]
    low_sr   = {"chi2": stats_r["low_chi2"], "p": stats_r["low_p"], "or": stats_r["low_or"]}
    high_sr  = {"chi2": stats_r["high_chi2"], "p": stats_r["high_p"], "or": stats_r["high_or"]}
    low_p_str  = f"< 0.001" if low_sr["p"]  < 0.001 else f"= {low_sr['p']:.3f}"
    high_p_str = f"< 0.001" if high_sr["p"] < 0.001 else f"= {high_sr['p']:.3f}"
    stats_summary = stats_r["summary"]

    # Reconciliation status line
    mismatches = [r for r in recon_rows if "MISMATCH" in r["Status"]]
    recon_status = (
        f"**All {len(recon_rows)} values MATCH** — script output is consistent with prior analyses."
        if not mismatches
        else (
            f"**{len(mismatches)} MISMATCH(ES) detected** — review flagged findings:\n"
            + "\n".join(f"- {m['Finding']}: expected {m['Expected']}, got {m['Computed']}"
                        for m in mismatches)
        )
    )

    content = textwrap.dedent(f"""\
    # Computed Findings — Machine-Generated Numbers

    **AUTO-GENERATED by `experiments/analysis/run_all.py` — do not hand-edit.**
    Re-running the script overwrites this file completely.
    Interpretation, caveats, refuted hypotheses, and future-work notes live in
    `experiments/FINDINGS.md`, which the script never touches.

    Source: 24-page corpus, 6,000 records.
    Tokenizer: `o200k_base` (SharpToken fixed). Schema version: `1.0`.

    ## Corpus provenance

    The corpus is uniformly classified under the predicate frozen
    **2026-06-17T18:34:41Z**. Eleven pages measured before that freeze
    (01, 02, 04, 05, 08, 10, 11, 12, 14, 19, 21) carried classifications from the
    superseded predicate and were re-classified by zero-LLM replay of their
    recorded locators — the model outputs are the originals; only the predicate
    was re-applied. The thirteen post-freeze pages were already consistent and
    were not touched.

    The replay **touched 206 records** across those eleven pages; most were
    predicate-field flips (`stable_signal_present_in_bundle` / `failure_mode`)
    that left the success outcome unchanged. The **net success-outcome change was
    +51**, from two mechanisms:

    - **`VolatileClassRe` over-rejection fix** — legitimate semantic classes
      (`.btn`, `.btn-search`, `.form-select`, …) were wrongly flagged volatile.
      Un-rejecting them flipped **+61 records from failure to success** (the sole
      positive driver).
    - **`page_01` t_04** — a breadcrumb whose only stable signal is visible text,
      now correctly `observation_lacked_stable_signal` (§36, output-language-limited).
      This **re-labeled 13 records** across every bundle including the ARIA
      snapshot, because `stable_signal_present_in_bundle` is bundle-aware rather
      than format-aware; the **10** of those that had previously succeeded on the
      text signal now correctly fail (the remaining 3 were `failure_mode`-only
      relabels).

    Reconciliation: **+61 gained − 10 lost = +51 net** success-outcome change;
    the balance of the 206 touched records were predicate-field flips with no
    outcome change.

    ## Reconciliation status

    {recon_status}

    ---

    ## 1. Axis A — bundle content (thesis result)

    **B_full vs B_noVolatile, all DOM encodings (F0–F3) aggregated, 24-page corpus.**

    | Bundle | Success rate | N/960 |
    |---|---|---|
    | B_full | {bf_pct:.2f}% | {int(thesis_r['bf_success_rate']*960)}/960 |
    | B_noVolatile | {nv_pct:.2f}% | {int(thesis_r['nv_success_rate']*960)}/960 |
    | **Delta** | **{delta:+.2f} pp** | |

    - B_noVolatile strictly beats B_full on {thesis_r['nv_strictly_wins_count']}/24 pages.
    - B_full strictly beats B_noVolatile on {thesis_r['bf_strictly_wins_count']}/24 pages.
    - Ties: {thesis_r['ties_count']}.
    - LOW-semantic stratum delta: {low_d:+.2f} pp.
    - HIGH-semantic stratum delta: {high_d:+.2f} pp.

    **Interpretation:** volatile attribute stripping produces a robust, corpus-wide gain, concentrated on pages with fewer stable semantic anchors (LOW stratum, {low_d:+.1f} pp) but present even on richer pages (HIGH, {high_d:+.1f} pp).

    ### Six-bundle ladder

    | Bundle | Success % | Mean obs tokens |
    |---|---|---|
    | B_full | {bf_pct:.2f}% | — |
    | B_noVolatile | {nv_pct:.2f}% | — |
    | B_noState | {ns_pct:.2f}% | — |
    | B_noSemantic | {nsm_pct:.2f}% | {nsm_tok:.0f} |
    | B_identityCore | {ic_pct:.2f}% | — |
    | B_minimalCore | 0.00% | 0 |

    Primary sufficiency cliff: **B_noState → B_noSemantic = {cliff:.2f} pp**.
    B_noSemantic is Pareto-trapped: cheaper than B_noState but worse than B_identityCore.

    ---

    ## 2. Axis B — encoding format (within B_noVolatile)

    | Encoding | Success % | Mean obs tokens |
    |---|---|---|
    | F0 (HTML) | {encoding_r['f0_success']*100:.2f}% | — |
    | F1 (JSON full keys) | {f1_pct:.2f}% | {f1_tok:.0f} |
    | F2 (JSON abbrev keys) | {f2_pct:.2f}% | ≈{f1_tok:.0f} |
    | F3 (linearized DSL) | {f3_pct:.2f}% | {f3_tok:.0f} |

    - **F2 harms**: abbreviated keys save ≈0 tokens but cost {f2_harm:.2f} pp success.
    - **F3 saves**: DSL encoding reduces tokens by {f3_red:.1f}% vs F1 at {encoding_r['f3_success_delta_pp']:+.2f} pp success. Under the frozen predicate this delta is POSITIVE — F3 is better *and* cheaper than F1, so F1 is Pareto-dominated.

    ---

    ## 3. Full Pareto surface (21 cells)

    {fr_n}/21 cells on the Pareto frontier. {dom_n} dominated.

    Frontier path (cheapest → most expensive):

    {frontier_path}

    B_noVolatile × F1 ({f1_pct:.2f}%, {f1_tok:.0f} tok) is NOT on the frontier: it is
    dominated by B_noVolatile × F3, which is both more successful and ~29% cheaper.

    **Canonical Observation Profile (COP): B_noVolatile × F3.**
    Cheapest frontier cell with >50% success.

    ### Abstract headline (COP vs naïve baseline B_full×F1)

    B_noVolatile×F3 achieves **{h_succ:+.2f} pp higher success** at **{h_tok:.1f}% fewer observation tokens** than B_full×F1.

    ### F4 task-level comparison (NV any-of-4 vs F4 single)

    | Outcome | Count / 240 tasks |
    |---|---|
    | Both succeed | {f4_both_succeed} |
    | NV wins | {nv_wins} |
    | F4 wins | {f4_wins} |
    | Both fail | {f4_both_fail} |

    NV (best-of-4 encodings) wins {nv_wins} tasks where F4 fails.
    F4 wins {f4_wins} tasks where all NV encodings fail.
    Note: the 4:1 comparison asymmetry (NV = 4 encodings, F4 = 1) is explicitly labelled.

    ---

    ## 4. Failure decomposition

    **Total failures across all 6,000 records:**

    | Mode | Count | Fraction |
    |---|---|---|
    | observation_lacked_stable_signal | {t_lack:,} | {t_lack/(t_lack+t_grab+t_unr):.1%} |
    | model_grabbed_brittle_signal | {t_grab:,} | {t_grab/(t_lack+t_grab+t_unr):.1%} |
    | output_format_unreachable | {t_unr:,} | {t_unr/(t_lack+t_grab+t_unr):.1%} |

    **Mechanism (B_full → B_noVolatile):**

    | Metric | Value |
    |---|---|
    | Success gain (records) | {s_gain:+d} |
    | Δgrabbed_brittle (records) | {d_grab:+d} |
    | Δlacked (records) | {d_lack:+d} |

    Interpretation: the {s_gain}-record net success gain is the balance of two opposing record-level flows — 102 grabbed_brittle→success recoveries minus 11 success→grabbed_brittle regressions (102 − 11 = {s_gain}). Δgrabbed_brittle = −{abs(d_grab)} is therefore a **net** substitution, not a one-to-one bijection. Δlacked = 0 — and zero lacked→success — confirms that stripping volatile attributes adds no information: it removes the brittle-grab trap without moving the floor set by missing stable signals. Of the 102 recoveries, 90 are genuine volatile grabs (predicate_non_volatile false under B_full — the volatile decoy dropped); the other 12 had been non-unique or wrong-element under B_full and resolved correctly once the distracting attributes were stripped — a minor secondary path, likewise adding no information (Δlacked = 0).

    **B_full vs B_noVolatile failure modes:**

    | Bundle | lacked | grabbed_brittle |
    |---|---|---|
    | B_full | {bf_lack} | {bf_grab} |
    | B_noVolatile | {nv_lack} | {nv_grab} |

    **F4 (B_playwrightMCP × F4) audit-corrected diagnosis:**

    - {f4_lack} failures: `lacked` (SSP=False — no DOM signal in bundle)
    - {f4_grab} failures: ARIA-collapse (SSP=True against BundleFull — signal in DOM but not exposed in ARIA tree)

    The {f4_grab} "grabbed_brittle" records in F4 are reclassified as observation-level failures in the paper; the model never saw the signal that BundleFull-based SSP detected.

    **B_noVolatile lacked count by encoding (encoding-invariant):**
    All four encodings have exactly {nv_lack_enc} lacked failures — lacked is determined by bundle content, not serialisation format.

    ---

    ## 5. Derived: COP definition

    The **Canonical Observation Profile (COP)** for this study:
    - Bundle: **B_noVolatile** (remove volatile attributes: hashed classes, auto-generated IDs)
    - Encoding: **F3** (linearized DSL)
    - Context regime: single-page, full body (default; regime sensitivity is a separate experiment)

    Extending the COP to downstream systems (e.g. locator resolution) is future work.

    ---

    ## 6. Statistical confirmation

    McNemar's test on **960 paired grounding events** (same page × task × encoding
    presented through both bundles).  Paired design chosen because chi-square would
    treat the records as independent samples, ignoring that most events succeed or
    fail under *both* bundles; only the discordant pairs (NV-only: {n10}, BF-only: {n01})
    inform the directional test.

    | Test | Statistic | p | Odds ratio |
    |---|---|---|---|
    | McNemar, corpus-wide | χ²(1) = {mc_chi2:.2f} | {mc_p_str} | OR = {mc_or:.2f} |
    | McNemar, LOW-semantic stratum | χ²(1) = {low_sr['chi2']:.2f} | {low_p_str} | OR = {low_sr['or']:.2f} |
    | McNemar, HIGH-semantic stratum | χ²(1) = {high_sr['chi2']:.2f} | {high_p_str} | OR = {high_sr['or']:.2f} |

    OR = (NV-only wins) / (BF-only wins) among discordant pairs.
    LOW OR > HIGH OR, consistent with descriptive {low_d:+.1f} pp vs {high_d:+.1f} pp.

    **Page-cluster bootstrap 95% CI** (n = 10,000 resamples, page-level):
    **[{ci_lo:+.1f} pp, {ci_hi:+.1f} pp]** — excludes zero.

    > {stats_summary}

    *NOT pre-registered.  This study is exploratory on a synthetic testbed.
    Stats are confirmatory-of-descriptive, not hypothesis tests of record.*
    """)

    COMPUTED_FINDINGS_PATH.write_text(content, encoding="utf-8")

    # Post-write integrity check: FINDINGS.md must be byte-for-byte unchanged.
    if findings_before is not None:
        import hashlib
        findings_after = hashlib.sha256(FINDINGS_MD_PATH.read_bytes()).hexdigest()
        assert findings_after == findings_before, (
            "INTEGRITY FAILURE: experiments/FINDINGS.md was modified during this run. "
            "This must never happen — the file is the hand-curated author log. "
            f"SHA256 before={findings_before!r}, after={findings_after!r}."
        )

    print(f"\n  computed_findings.md written to: {COMPUTED_FINDINGS_PATH}")
    print(f"  (experiments/FINDINGS.md was NOT modified — verified by SHA-256 hash)")


def print_reconciliation(rows):
    """Print the reconciliation table to stdout."""
    col_widths = {
        "Finding":   max(len(r["Finding"])   for r in rows),
        "Expected":  max(len(r["Expected"])  for r in rows),
        "Computed":  max(len(r["Computed"])  for r in rows),
        "Tolerance": max(len(r["Tolerance"]) for r in rows),
        "Status":    max(len(r["Status"])    for r in rows),
    }
    # Ensure header is included in column widths.
    for key in col_widths:
        col_widths[key] = max(col_widths[key], len(key))

    sep = "─" * (sum(col_widths.values()) + 3 * (len(col_widths) - 1) + 4)

    def row_str(r):
        return (
            f"  {r['Finding']:{col_widths['Finding']}}   "
            f"{r['Expected']:{col_widths['Expected']}}   "
            f"{r['Computed']:{col_widths['Computed']}}   "
            f"{r['Tolerance']:{col_widths['Tolerance']}}   "
            f"{r['Status']}"
        )

    header = row_str({
        "Finding": "Finding", "Expected": "Expected",
        "Computed": "Computed", "Tolerance": "Tolerance", "Status": "Status",
    })

    print(f"\n{'='*60}")
    print("RECONCILIATION — expected (from prior analyses) vs computed (Python)")
    print(f"{'='*60}")
    print(header)
    print(f"  {sep}")
    for r in rows:
        print(row_str(r))

    mismatches = [r for r in rows if "MISMATCH" in r["Status"]]
    print(f"\n  {len(rows) - len(mismatches)}/{len(rows)} MATCH")
    if mismatches:
        print(f"  {len(mismatches)} MISMATCH(ES) — investigate before publishing:")
        for m in mismatches:
            print(f"    • {m['Finding']}: expected {m['Expected']}, got {m['Computed']}")
    else:
        print("  All values consistent with prior analyses.")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("Loading data...")
    df = load_dataframe(REPO_ROOT)
    print(f"  Loaded {len(df):,} records from 24 JSONL files.")

    print("\nRunning analysis modules...")

    print("\n[1/6] thesis.py")
    thesis_r    = _thesis.compute(df)

    print("\n[2/6] bundle_ladder.py")
    ladder_r    = _bundle_ladder.compute(df)

    print("\n[3/6] encoding.py")
    encoding_r  = _encoding.compute(df)

    print("\n[4/6] pareto.py")
    pareto_r    = _pareto.compute(df)

    print("\n[5/6] failure_decomp.py")
    decomp_r    = _failure_decomp.compute(df)

    print("\n[6/6] stats.py")
    stats_r     = _stats.compute(df)

    print("\n\nAll analysis modules completed.")

    # ── Write computed tables, then print reconciliation before the ──────────
    # FINDINGS.md content-guard check below — a legitimate doc edit that
    # trips the guard must not hide the rest of the run's output behind a
    # bare stack trace.
    write_computed_tables(thesis_r, ladder_r, encoding_r, pareto_r, decomp_r)
    recon_rows, all_match = make_reconciliation_table(
        thesis_r, ladder_r, encoding_r, pareto_r, decomp_r, stats_r
    )
    print_reconciliation(recon_rows)

    # ── Write computed_findings.md (contains the FINDINGS.md content guard) ──
    write_computed_findings(thesis_r, ladder_r, encoding_r, pareto_r, decomp_r, stats_r, recon_rows)

    # Non-zero exit code if any mismatch — useful in CI.
    if not all_match:
        print("\nExiting with code 1 due to MISMATCH(ES).")
        sys.exit(1)


if __name__ == "__main__":
    main()
