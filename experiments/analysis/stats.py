"""
stats.py — formal statistical tests for this study's thesis finding.

Tests whether B_noVolatile's advantage over B_full in grounding success is
statistically significant, not a sampling artefact of the 24-page testbed.

--- Why McNemar, not chi-square ---

The test is paired.  Every grounding event (page × task × encoding ×
repetition) is presented to *both* bundles under identical conditions —
the same page DOM, the same task, the same encoding format.  Chi-square
would treat those 960 B_full records and 960 B_noVolatile records as
independent, missing that most events succeed under *both* bundles or fail
under *both*.  McNemar uses only the *discordant* pairs — events where the
bundles disagreed (NV succeeded but BF failed, or vice versa) — and asks:
is the imbalance between those two cells larger than chance?  The concordant
pairs (both succeed / both fail) carry no information about which bundle is
better.

--- Why cluster bootstrap (not record bootstrap) ---

Events within the same page are correlated: they share the same DOM
structure, the same stable vs volatile attributes, the same layout.
Resampling individual records would break that correlation and
underestimate uncertainty.  We resample at the PAGE level, keeping all 40
events for a sampled page together, so the bootstrap replicate reflects
the real variation across pages (the unit of experimental interest).

--- Statistical status ---

NOT pre-registered.  This is an exploratory study on a synthetic controlled
testbed.  These tests are confirmatory-of-descriptive (they verify that the
+9.48 pp gap is not a sampling artefact), not hypothesis tests of record.
Report accordingly.

Input: the 960 paired B_full / B_noVolatile DOM-encoding records.
Expected: McNemar p << 0.001, 95% CI excludes zero, both strata significant.
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
import numpy as np
import pandas as pd
from scipy.stats import chi2, wilcoxon, binomtest
from tabulate import tabulate

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from load import load_dataframe, DOM_ENCODINGS

BUNDLE_FULL = "B_full"
BUNDLE_NV   = "B_noVolatile"
N_BOOTSTRAP = 10_000
RNG_SEED    = 42


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge B_full and B_noVolatile records into paired rows.

    Each pair shares the same (page, task_id, encoding, repetition) — identical
    grounding event, different bundle.  Returns a DataFrame with one row per pair
    and columns success_bf, success_nv, semantic_density, page.
    """
    bf = df[
        (df["bundle"] == BUNDLE_FULL) & df["encoding"].isin(DOM_ENCODINGS)
    ][["page", "task_id", "encoding", "repetition", "success", "semantic_density"]].copy()

    nv = df[
        (df["bundle"] == BUNDLE_NV) & df["encoding"].isin(DOM_ENCODINGS)
    ][["page", "task_id", "encoding", "repetition", "success"]].copy()

    pairs = bf.merge(
        nv,
        on=["page", "task_id", "encoding", "repetition"],
        suffixes=("_bf", "_nv"),
    )
    return pairs


def _build_contingency(pairs: pd.DataFrame):
    """
    Build the 2×2 McNemar contingency from aligned pairs.

    Returns (n11, n10, n01, n00) where:
      n11 = both succeed
      n10 = NV succeeds, BF fails  (NV-only win — the "b" cell)
      n01 = BF succeeds, NV fails  (BF-only win — the "c" cell)
      n00 = both fail
    """
    both_succeed    = pairs["success_bf"] & pairs["success_nv"]
    nv_only         = ~pairs["success_bf"] & pairs["success_nv"]
    bf_only         = pairs["success_bf"] & ~pairs["success_nv"]
    both_fail       = ~pairs["success_bf"] & ~pairs["success_nv"]

    return int(both_succeed.sum()), int(nv_only.sum()), int(bf_only.sum()), int(both_fail.sum())


def _mcnemar_chi2(b: int, c: int):
    """
    McNemar chi-square statistic and two-sided p-value.

    Formula: chi2 = (b - c)^2 / (b + c), df=1.
    No continuity correction — appropriate when b+c is large enough (here
    the discordant total is expected to be hundreds, well above the n≥25
    rule of thumb for the uncorrected form).

    b = n10 (NV-only wins), c = n01 (BF-only wins).
    The discordant cells are ALL the test uses.
    """
    chi2_stat = (b - c) ** 2 / (b + c)
    p_value   = chi2.sf(chi2_stat, df=1)
    return float(chi2_stat), float(p_value)


def _odds_ratio(b: int, c: int) -> float:
    """
    Odds ratio from the McNemar discordant cells.

    OR = b/c = (NV-only wins) / (BF-only wins).
    Interpretation: for every discordant pair where BF won, OR pairs exist
    where NV won.  OR > 1 means NV is the winning bundle when the bundles
    disagree.
    """
    return b / c


def _or_label(odds_ratio: float) -> str:
    """Map an odds ratio to a rough qualitative label."""
    if odds_ratio < 1.5:
        return "negligible"
    elif odds_ratio < 2.5:
        return "small"
    elif odds_ratio < 5.0:
        return "medium"
    else:
        return "large"


def _cluster_bootstrap_ci(pairs: pd.DataFrame, n_boot: int, seed: int):
    """
    Bootstrap 95% CI on corpus-wide success delta (NV − BF in pp).

    Resamples at PAGE level (not record level) to preserve within-page
    correlation.  Each bootstrap replicate draws 24 pages with replacement;
    all 40 events for each drawn page are kept together.
    Returns (ci_lo_pp, ci_hi_pp, bootstrap_deltas_array).
    """
    pages    = pairs["page"].unique()
    n_pages  = len(pages)

    # Pre-group by page for fast lookup in the bootstrap loop.
    page_groups = {p: pairs[pairs["page"] == p] for p in pages}

    rng    = np.random.default_rng(seed)
    deltas = np.empty(n_boot)

    for i in range(n_boot):
        sampled_pages = rng.choice(pages, size=n_pages, replace=True)
        boot = pd.concat(
            [page_groups[p] for p in sampled_pages],
            ignore_index=True,
        )
        nv_rate = boot["success_nv"].mean()
        bf_rate = boot["success_bf"].mean()
        deltas[i] = (nv_rate - bf_rate) * 100

    ci_lo = float(np.percentile(deltas, 2.5))
    ci_hi = float(np.percentile(deltas, 97.5))
    return ci_lo, ci_hi, deltas


def _page_level_sensitivity(pairs: pd.DataFrame) -> dict:
    """
    Page-level inferential sensitivity: treat the PAGE (not the event) as the inferential unit.

    The McNemar test and bootstrap above operate on the 960 event-pairs.  A
    skeptical reviewer may argue that records within a page are correlated and
    the inferential unit should therefore be the page, not the event.  This
    aggregates to the 24 per-page (B_full, B_noVolatile) success counts and runs
    two page-level tests on the per-page deltas:
      - a sign test on how many of the non-tied pages favour B_noVolatile;
      - a paired Wilcoxon signed-rank test on the 24 per-page success-count deltas.

    ADDITIVE and self-contained: it does not touch the McNemar/bootstrap path, adds
    no assertion, and feeds nothing into run_all.py's reconciliation.  It returns
    scalars for printing only.  (Wilcoxon on raw counts and on per-page success
    RATES gives the same signed-rank p-value, since rate = count / 40 is a
    monotone rescaling; the count form is reported.)
    """
    by_page = pairs.groupby("page")[["success_bf", "success_nv"]].sum()
    delta   = by_page["success_nv"] - by_page["success_bf"]

    n_nv_favoring = int((delta > 0).sum())
    n_bf_favoring = int((delta < 0).sum())
    n_ties        = int((delta == 0).sum())
    n_nonzero     = n_nv_favoring + n_bf_favoring

    sign_p       = binomtest(n_nv_favoring, n_nonzero, 0.5, alternative="two-sided").pvalue
    wilcoxon_res = wilcoxon(by_page["success_nv"], by_page["success_bf"])

    return {
        "n_pages":           int(len(by_page)),
        "nv_favoring_pages": n_nv_favoring,
        "bf_favoring_pages": n_bf_favoring,
        "tied_pages":        n_ties,
        "n_nonzero":         n_nonzero,
        "sign_test_p":       float(sign_p),
        "wilcoxon_stat":     float(wilcoxon_res.statistic),
        "wilcoxon_p":        float(wilcoxon_res.pvalue),
    }


# ── Main compute function ─────────────────────────────────────────────────────

def compute(df: pd.DataFrame) -> dict:
    """
    Run formal statistical tests on the B_full vs B_noVolatile comparison.
    Returns a dict of scalar results for run_all.py's reconciliation table.
    """

    # ── Build paired dataset ───────────────────────────────────────────────
    #
    # 960 pairs: 24 pages × 10 tasks × 4 DOM encodings × 1 repetition.
    # Each pair = same grounding event through both bundles.
    #
    pairs = _build_pairs(df)

    assert len(pairs) == 960, (
        f"Expected 960 pairs (24p × 10t × 4enc × 1rep); got {len(pairs)}.  "
        f"Check that both bundles have complete data."
    )

    # ── Corpus-wide 2×2 contingency ───────────────────────────────────────
    n11, n10, n01, n00 = _build_contingency(pairs)
    total_pairs = n11 + n10 + n01 + n00

    assert total_pairs == 960, (
        f"Contingency cells sum to {total_pairs}, expected 960"
    )

    # n10 − n01 must equal the thesis.py net success delta (+91).
    # NV has 617 successes, BF has 526 → net difference = +91.
    # The only way to get a net +91 is n10 − n01 = 91.
    assert n10 - n01 == 91, (
        f"Discordant net (n10 − n01) = {n10 - n01}, expected 91 "
        f"(= thesis.py NV success 617 − BF success 526).  "
        f"Pairing key may be misspecified."
    )

    # ── McNemar test — corpus-wide ─────────────────────────────────────────
    #
    # b = n10 (NV-only wins), c = n01 (BF-only wins).
    # H0: P(NV wins | discordant pair) = 0.5, i.e. n10 == n01 in expectation.
    #
    b, c = n10, n01
    chi2_stat, p_value = _mcnemar_chi2(b, c)
    or_corpus          = _odds_ratio(b, c)
    or_label_corpus    = _or_label(or_corpus)

    # OR=9.27 is a canonical headline (FINDINGS.md) that the
    # reconciliation table guards only directionally via the p-value.  Pin it
    # here so a drift in the discordant split (b/c = 102/11) can't pass silently.
    assert abs(or_corpus - 9.27) < 0.05, (
        f"Corpus odds ratio {or_corpus:.2f} differs from canonical 9.27 "
        f"(discordant b/c = {b}/{c}).  Pairing or classification may have drifted."
    )

    # ── McNemar by semantic stratum ────────────────────────────────────────
    #
    # LOW pages have fewer stable semantic anchors; the descriptive delta is
    # larger there (see delta_pp per stratum).  If the statistical signal also
    # holds separately within each stratum, the finding is robust to stratum.
    #
    stratum_results = {}
    for stratum in ("LOW", "HIGH"):
        stratum_pairs = pairs[pairs["semantic_density"] == stratum]
        s11, s10, s01, s00 = _build_contingency(stratum_pairs)
        s_chi2, s_p = _mcnemar_chi2(s10, s01)
        s_or        = _odds_ratio(s10, s01) if s01 > 0 else float("inf")
        # Descriptive delta for this stratum, computed rather than hardcoded:
        # the summary prose cites it, and a fixed literal goes stale the moment
        # the corpus is reclassified.
        s_delta_pp = (stratum_pairs["success_nv"].mean()
                      - stratum_pairs["success_bf"].mean()) * 100
        stratum_results[stratum] = {
            "n11": s11, "n10": s10, "n01": s01, "n00": s00,
            "chi2": s_chi2, "p": s_p, "or": s_or, "delta_pp": s_delta_pp,
        }

    # Both strata should be significant at conventional α=0.05.
    for stratum in ("LOW", "HIGH"):
        assert stratum_results[stratum]["p"] < 0.05, (
            f"McNemar not significant in {stratum} stratum "
            f"(p={stratum_results[stratum]['p']:.4f}).  "
            f"LOW should show a large effect (+15.0 pp), HIGH a smaller one (+4.0 pp)."
        )

    # LOW OR should exceed HIGH OR (stronger effect where semantic anchors are scarcer).
    assert stratum_results["LOW"]["or"] > stratum_results["HIGH"]["or"], (
        f"Expected LOW OR ({stratum_results['LOW']['or']:.2f}) > "
        f"HIGH OR ({stratum_results['HIGH']['or']:.2f}) — "
        f"low-semantic pages should show a stronger discordant imbalance"
    )

    # ── Cluster bootstrap 95% CI ───────────────────────────────────────────
    #
    # Resample 24 pages with replacement N_BOOTSTRAP times.
    # Using page-level resampling because DOM events within one page share
    # structure and are not independent; record-level resampling would
    # produce artificially narrow CIs.
    #
    print(f"\n  Running cluster bootstrap (n={N_BOOTSTRAP:,}, seed={RNG_SEED})...")
    ci_lo, ci_hi, boot_deltas = _cluster_bootstrap_ci(pairs, N_BOOTSTRAP, RNG_SEED)

    # The CI must exclude zero — if it doesn't, the data do not support
    # the claim of a positive corpus-wide benefit.
    assert ci_lo > 0, (
        f"Bootstrap 95% CI lower bound = {ci_lo:.2f} pp, expected > 0.  "
        f"CI includes zero — the corpus-wide advantage is not reliably positive."
    )

    # ── Print tables ──────────────────────────────────────────────────────

    print(f"\n{'='*60}")
    print("STATS: corpus-wide 2×2 McNemar contingency")
    print(f"{'='*60}")
    contingency_display = [
        ["",              "BF succeeds", "BF fails", "Row total"],
        ["NV succeeds",   n11,           n10,        n11+n10],
        ["NV fails",      n01,           n00,        n01+n00],
        ["Column total",  n11+n01,       n10+n00,    total_pairs],
    ]
    print(tabulate(contingency_display, tablefmt="pipe", headers="firstrow"))
    print(f"\n  Discordant cells: NV-only wins (b) = {b},  BF-only wins (c) = {c}")
    print(f"  Net NV advantage: b − c = {b - c}  (== thesis.py success delta +91  ✓)")

    print(f"\n{'='*60}")
    print("STATS: McNemar test — corpus-wide")
    print(f"{'='*60}")
    p_display = f"{p_value:.2e}" if p_value < 0.001 else f"{p_value:.4f}"
    print(f"  chi2(1) = {chi2_stat:.2f},  p = {p_display}")
    print(f"  Odds ratio (discordant): OR = {or_corpus:.2f}  ({or_label_corpus} effect)")
    print(f"  Interpretation: NV wins {or_corpus:.1f}× more often than BF among discordant pairs")

    print(f"\n{'='*60}")
    print("STATS: McNemar by semantic stratum")
    print(f"{'='*60}")
    stratum_rows = []
    for stratum in ("LOW", "HIGH"):
        sr = stratum_results[stratum]
        sp_display = f"{sr['p']:.2e}" if sr["p"] < 0.001 else f"{sr['p']:.4f}"
        stratum_rows.append({
            "Stratum":  stratum,
            "Pairs":    sr["n11"] + sr["n10"] + sr["n01"] + sr["n00"],
            "NV-only":  sr["n10"],
            "BF-only":  sr["n01"],
            "chi2(1)":  f"{sr['chi2']:.2f}",
            "p":        sp_display,
            "OR":       f"{sr['or']:.2f}",
        })
    print(tabulate(stratum_rows, headers="keys", tablefmt="pipe", showindex=False))

    print(f"\n{'='*60}")
    print(f"STATS: cluster bootstrap 95% CI  (n={N_BOOTSTRAP:,}, page-level resampling)")
    print(f"{'='*60}")
    boot_mean = float(np.mean(boot_deltas))
    boot_sd   = float(np.std(boot_deltas))
    print(f"  Bootstrap mean delta: {boot_mean:+.2f} pp")
    print(f"  Bootstrap SD:         {boot_sd:.2f} pp")
    print(f"  95% CI:  [{ci_lo:+.2f} pp,  {ci_hi:+.2f} pp]  (excludes zero: {ci_lo > 0})")

    # ── Page-level inferential sensitivity ──────────────────────
    #
    # NEW, additive: the PAGE — not the event — as the inferential unit.  Does not
    # alter the McNemar/bootstrap results above or any reconciled value; reported
    # for robustness only.  Not fed into run_all.py.
    #
    page_sens = _page_level_sensitivity(pairs)
    print(f"\n{'='*60}")
    print("STATS: page-level sensitivity (inferential unit = page, n=24)")
    print(f"{'='*60}")
    print(f"  Pages favouring B_noVolatile: {page_sens['nv_favoring_pages']}/{page_sens['n_pages']}"
          f"  (B_full: {page_sens['bf_favoring_pages']}, ties: {page_sens['tied_pages']})")
    print(f"  Sign test (non-tied n={page_sens['n_nonzero']}):        p = {page_sens['sign_test_p']:.3e}")
    print(f"  Paired Wilcoxon (24 per-page deltas): W = {page_sens['wilcoxon_stat']:.1f}, "
          f"p = {page_sens['wilcoxon_p']:.3e}")

    # ── Plain-language summary ─────────────────────────────────────────────
    low_sr  = stratum_results["LOW"]
    high_sr = stratum_results["HIGH"]
    low_p_str  = f"< 0.001" if low_sr["p"]  < 0.001 else f"= {low_sr['p']:.3f}"
    high_p_str = f"< 0.001" if high_sr["p"] < 0.001 else f"= {high_sr['p']:.3f}"
    corpus_p_str = f"< 0.001" if p_value < 0.001 else f"= {p_value:.3f}"

    summary = (
        f"McNemar's test on 960 paired grounding events (same page x task x encoding "
        f"through both bundles) confirms that B_noVolatile's advantage over B_full is "
        f"statistically significant (chi2(1) = {chi2_stat:.2f}, p {corpus_p_str}; "
        f"OR = {or_corpus:.2f}, {or_label_corpus} effect by discordant-cell ratio). "
        f"The effect holds in both semantic strata: LOW-semantic pages "
        f"(chi2(1) = {low_sr['chi2']:.2f}, p {low_p_str}, OR = {low_sr['or']:.2f}) "
        f"and HIGH-semantic pages "
        f"(chi2(1) = {high_sr['chi2']:.2f}, p {high_p_str}, OR = {high_sr['or']:.2f}), "
        f"with the stronger OR on LOW-semantic pages consistent with the larger "
        f"descriptive gap ({low_sr['delta_pp']:+.1f} pp vs {high_sr['delta_pp']:+.1f} pp). "
        f"A page-cluster bootstrap (n = {N_BOOTSTRAP:,} resamples, resampling at page "
        f"level to preserve within-page event correlation) yields a 95% CI on the "
        f"corpus success delta of [{ci_lo:+.1f} pp, {ci_hi:+.1f} pp], excluding zero."
    )

    print(f"\n{'='*60}")
    print("STATS: plain-language summary (for paper adaptation)")
    print(f"{'='*60}")
    # Wrap at 72 chars for readability
    import textwrap
    for line in textwrap.wrap(summary, width=72):
        print(f"  {line}")

    return {
        # Contingency
        "n11":             n11,
        "n10":             n10,
        "n01":             n01,
        "n00":             n00,
        "total_pairs":     total_pairs,
        # McNemar corpus-wide
        "mcnemar_chi2":    chi2_stat,
        "mcnemar_p":       p_value,
        "odds_ratio":      or_corpus,
        # McNemar by stratum
        "low_chi2":        stratum_results["LOW"]["chi2"],
        "low_p":           stratum_results["LOW"]["p"],
        "low_or":          stratum_results["LOW"]["or"],
        "high_chi2":       stratum_results["HIGH"]["chi2"],
        "high_p":          stratum_results["HIGH"]["p"],
        "high_or":         stratum_results["HIGH"]["or"],
        # Bootstrap CI
        "ci_lo_pp":        ci_lo,
        "ci_hi_pp":        ci_hi,
        "boot_mean_pp":    boot_mean,
        "boot_sd_pp":      boot_sd,
        # For computed_findings.md
        "summary":         summary,
        "corpus_p_str":    corpus_p_str,
    }


if __name__ == "__main__":
    repo_root = pathlib.Path(__file__).parent.parent.parent
    df = load_dataframe(repo_root)
    compute(df)
