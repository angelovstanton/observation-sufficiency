"""Exploratory bootstrap CIs for Tables 2 and 5.

Existing gpt-4.1 corpus records only (experiments/runs/matrix_page_*.jsonl, one generation per
event); not in the registered plan. Zero LLM calls, zero network.

  (a) Table 2: 960 paired events (F0–F3), B_full → each reduced bundle.
  (b) Table 5: 240 paired events within B_noVolatile, F1 → F0 / F2 / F3.

P5 = success (five-condition predicate); P_now = condition 1 ∧ 2 (unique match ∧ matches
oracle), substituted for `success` before the imported pair builders run. Statistics come from
revision1_diagnostics: McNemar (uncorrected χ², exact p, OR = b/c with exact conditional CI)
and the page-clustered percentile bootstrap (10,000 replicates, seed 42, fresh generator per
statistic). Controls run first; any mismatch stops before an output is written.

Outputs: experiments/results/revision1/table_cis.{md,json}
Run: python -B experiments/analysis/revision1_table_cis.py
"""

import hashlib
import json
import pathlib
import re
import sys

sys.dont_write_bytecode = True
from revision1_diagnostics import (  # noqa: E402
    N_BOOT, OUT_DIR, REPO, RUNS, SEED, Controls, build_encoding_pairs, build_pairs, fmt_or,
    fmt_p, jsonable, load_dataframe, mcnemar, md_table, page_bootstrap, pct_ci,
    protected_state, published_stats,
)

SCRIPT = pathlib.Path(__file__).resolve()
HOLM_MD = OUT_DIR / "holm_bfull_family.md"
BATCH_MD = OUT_DIR / "batch_analysis.md"
DIAG_JSON = OUT_DIR / "diagnostics.json"
OUT_MD = OUT_DIR / "table_cis.md"
OUT_JSON = OUT_DIR / "table_cis.json"

TITLE = "# EXPLORATORY — CIs for Tables 2 and 5 (existing records only; not in the registered plan)"
TABLE2 = ["B_noVolatile", "B_noState", "B_noSemantic", "B_identityCore", "B_minimalCore"]
TABLE5 = ["F0", "F2", "F3"]
PREDS = ["P5", "P_now"]


# per_page_success / delta_stat are closures inside revision1_diagnostics.main() and
# cannot be imported; these are the same bodies, with page_order passed explicitly.
# Control "local bootstrap == stats._cluster_bootstrap_ci" pins them to stats.py.
def per_page_success(p, bf_col, nv_col, page_order):
    g = p.groupby("page", sort=False)
    return {"bf": g[bf_col].sum().reindex(page_order).to_numpy(dtype=float),
            "nv": g[nv_col].sum().reindex(page_order).to_numpy(dtype=float),
            "n":  g[bf_col].count().reindex(page_order).to_numpy(dtype=float)}


delta_stat = lambda t: (t["nv"] / t["n"] - t["bf"] / t["n"]) * 100  # noqa: E731


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def with_predicate(df, pred):
    """Corpus frame whose `success` column carries the requested predicate."""
    if pred == "P5":
        return df
    out = df.copy()
    out["success"] = (out["predicate_unique_match"].astype(bool)
                      & out["predicate_matches_oracle"].astype(bool))
    return out


def compare(pairs, table, label, first, second, pred):
    page_order = list(pairs["page"].unique())
    r = mcnemar(pairs["success_bf"], pairs["success_nv"])
    draws = page_bootstrap(page_order, per_page_success(pairs, "success_bf", "success_nv", page_order),
                           delta_stat)
    r["boot_ci_lo_pp"], r["boot_ci_hi_pp"] = pct_ci(draws)
    r.update(table=table, comparison=label, first=first, second=second, predicate=pred,
             n_pages=len(page_order))
    return r


def parse_md_rows(path, first_cell_pattern):
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("| "):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if re.fullmatch(first_cell_pattern, cells[0]):
                rows.setdefault(cells[0], cells)
    return rows


def main():
    before = protected_state()
    df = load_dataframe(REPO)
    assert set(df["model"]) == {"gpt-4.1"} and set(df["repetition"]) == {0}

    results = {pred: [] for pred in PREDS}
    for pred in PREDS:
        frame = with_predicate(df, pred)
        ref_keys = None
        for second in TABLE2:
            pairs = build_pairs(frame, "B_full", second)
            assert len(pairs) == 960
            keys = list(map(tuple, pairs[["page", "task_id", "encoding", "repetition"]].to_numpy()))
            assert ref_keys is None or keys == ref_keys, "Table 2 rows do not share the same 960 events"
            ref_keys = keys
            results[pred].append(compare(pairs, "Table 2", f"B_full → {second}", "B_full", second, pred))
        for enc in TABLE5:
            pairs = build_encoding_pairs(frame, "B_noVolatile", "F1", enc)
            assert len(pairs) == 240
            results[pred].append(compare(pairs, "Table 5", f"B_noVolatile: F1 → {enc}", "F1", enc, pred))
    p5 = {r["comparison"]: r for r in results["P5"]}
    pnow = {r["comparison"]: r for r in results["P_now"]}

    # Controls
    ctl = Controls()
    hl = p5["B_full → B_noVolatile"]
    ctl.check("B_full→B_noVolatile Δ pp (2 dp)", f"{hl['delta_pp']:+.2f}", "+9.48")
    ctl.check("B_full→B_noVolatile CI (2 dp)",
              f"[{hl['boot_ci_lo_pp']:+.2f}, {hl['boot_ci_hi_pp']:+.2f}]", "[+4.90, +15.52]")
    ctl.check("B_full→B_noVolatile b/c", f"{hl['b_second_only']}/{hl['c_first_only']}", "102/11")
    ci_lo, ci_hi, _ = published_stats._cluster_bootstrap_ci(published_stats._build_pairs(df), N_BOOT, SEED)
    ctl.check("local bootstrap == stats._cluster_bootstrap_ci (lo, 1e-9)",
              round(hl["boot_ci_lo_pp"], 9), round(ci_lo, 9))
    ctl.check("local bootstrap == stats._cluster_bootstrap_ci (hi, 1e-9)",
              round(hl["boot_ci_hi_pp"], 9), round(ci_hi, 9))

    batch_rows = [[c.strip() for c in line.strip().strip("|").split("|")]
                  for line in BATCH_MD.read_text(encoding="utf-8").splitlines()
                  if line.startswith("| (d) gpt-4.1 B_noVolatile F2 vs F1, rep 1 | overall |")]
    batch_by_pred = {cells[2]: cells for cells in batch_rows}
    assert len(batch_rows) == 2 and set(batch_by_pred) == {"P5", "P_now"}, \
        "batch_analysis.md (d) rep 1 overall rows not found"
    f2 = p5["B_noVolatile: F1 → F2"]
    ctl.check("F1→F2 (B_noVolatile) Δ pp (2 dp)", f"{f2['delta_pp']:+.2f}", "-12.08")
    ctl.check("F1→F2 (B_noVolatile) b/c", f"{f2['b_second_only']}/{f2['c_first_only']}", "4/33")
    for pred, r in (("P5", f2), ("P_now", pnow["B_noVolatile: F1 → F2"])):
        cells = batch_by_pred[pred]
        ctl.check(f"F1→F2 (B_noVolatile) {pred} CI == batch_analysis.md (d) rep 1",
                  f"[{r['boot_ci_lo_pp']:+.2f}, {r['boot_ci_hi_pp']:+.2f}]", cells[7])
        ctl.check(f"F1→F2 (B_noVolatile) {pred} Δ, b/c == batch_analysis.md (d) rep 1",
                  f"{r['delta_pp']:+.2f} {r['b_second_only']}/{r['c_first_only']}",
                  f"{cells[6]} {cells[8]}")

    holm = parse_md_rows(HOLM_MD, r"B_full → B_\w+|B_noVolatile: F1 → F\d")
    for r in results["P5"]:
        cells = holm.get(r["comparison"])
        ctl.check(f"{r['comparison']} Δ, b/c == holm_bfull_family.md",
                  f"{r['delta_pp']:+.2f} {r['b_second_only']}/{r['c_first_only']}",
                  None if cells is None else f"{cells[1]} {cells[2]}/{cells[3]}")

    d1_now = json.loads(DIAG_JSON.read_text(encoding="utf-8"))["D1"]["predicates"]["P_now"]
    hn = pnow["B_full → B_noVolatile"]
    ctl.check("B_full→B_noVolatile P_now b/c, Δ, CI == diagnostics.json D1 (full precision)",
              [hn["b_second_only"], hn["c_first_only"], hn["delta_pp"], hn["boot_ci_lo_pp"], hn["boot_ci_hi_pp"]],
              [d1_now["b_second_only"], d1_now["c_first_only"], d1_now["delta_pp"],
               d1_now["boot_ci_lo_pp"], d1_now["boot_ci_hi_pp"]])
    ctl.enforce()
    if protected_state() != before:
        raise SystemExit("[guard] evidence files changed during the run; no outputs written")

    # Outputs
    headers = ["comparison (second − first)", "n pairs", "first %", "second %", "Δ pp", "95% CI (pp)",
               "b (second-only)", "c (first-only)", "OR = b/c [exact 95% CI]", "p χ²", "p exact"]

    def table_rows(rows):
        return [[r["comparison"], r["n"], f"{r['rate_first_pct']:.1f}", f"{r['rate_second_pct']:.1f}",
                 f"{r['delta_pp']:+.2f}", f"[{r['boot_ci_lo_pp']:+.2f}, {r['boot_ci_hi_pp']:+.2f}]",
                 r["b_second_only"], r["c_first_only"],
                 f"{fmt_or(r['odds_ratio'])} [{fmt_or(r['or_ci_lo'])}, {fmt_or(r['or_ci_hi'])}]",
                 fmt_p(r["p"]), fmt_p(r["p_exact"])] for r in rows]

    inputs = [SCRIPT] + [REPO / "experiments" / "analysis" / n for n in
                         ("revision1_diagnostics.py", "load.py", "stats.py", "bundle_ladder.py", "cross_model.py")]
    inputs += [HOLM_MD, BATCH_MD, DIAG_JSON] + sorted(RUNS.glob("matrix_page_*.jsonl"))
    input_sha = {p.relative_to(REPO).as_posix(): sha256(p) for p in inputs}

    md = [TITLE, "",
          "Run: `python -B experiments/analysis/revision1_table_cis.py`. Zero LLM calls, zero network; reads existing "
          "records only and modifies no existing file.", "",
          "Data: gpt-4.1, main corpus (`experiments/runs/matrix_page_*.jsonl`, 6,000 records, one generation per "
          "event). (a) Table 2: 960 paired events (24 pages × 10 tasks × F0–F3), first = B_full. "
          "(b) Table 5: 240 paired events within B_noVolatile (24 pages × 10 tasks), first = F1.", "",
          "Conventions: Δ = second − first (pp); b = second-only successes, c = first-only. 95% CI = "
          f"page-clustered percentile bootstrap, {N_BOOT:,} replicates, seed {SEED}, fresh generator per "
          "statistic, same draw sequence as `stats.py`. OR = b/c with exact conditional 95% CI "
          "(Clopper–Pearson on b/(b+c)). p χ² = uncorrected McNemar; p exact = binomial. No multiplicity "
          "adjustment. P5 = five-condition predicate (`success`); P_now = condition 1 ∧ 2 (unique match ∧ "
          "matches oracle). Statistics imported from `revision1_diagnostics.py`; `per_page_success` and "
          "`delta_stat` are closures inside its `main()`, so their bodies are restated here and pinned to "
          "`stats._cluster_bootstrap_ci` by a control.", "",
          "## Controls (all passed before any output was written)", ""]
    md += md_table(["control", "recomputed", "reference", "ok"],
                   [[c["control"], c["recomputed"], c["published"], "yes" if c["ok"] else "NO"]
                    for c in ctl.rows])
    for pred, desc in (("P5", "P5 (primary)"), ("P_now", "P_now (condition 1 ∧ 2)")):
        md += ["", f"## Results — {desc}", ""]
        md += md_table(headers, table_rows(results[pred]))
    md += ["", "## Input SHA-256", "", "| Input | SHA-256 |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in input_sha.items()]

    R = {"meta": {"script": "experiments/analysis/revision1_table_cis.py", "status": "EXPLORATORY",
                  "model": "gpt-4.1", "corpus": "experiments/runs/matrix_page_*.jsonl (6,000 records)",
                  "n_boot": N_BOOT, "seed": SEED, "delta": "second − first, pp",
                  "b": "second-only successes", "c": "first-only successes"},
         "controls": ctl.rows, "results": results, "input_sha256": input_sha}
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    OUT_JSON.write_text(json.dumps(jsonable(R), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
