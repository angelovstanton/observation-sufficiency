"""
Short-hash sensitivity (zero LLM; the predicate itself is unchanged).

`VolatileClassRe` flags CSS-module class tokens `Name_xxxxx__hash` only when the middle
segment has ≥ 5 characters. This re-scores P5 treating as volatile any locator that contains
a token `Name_x__hash` with a 1–4 character middle segment not flagged by the predicate (the
112 (page, token) pairs of sensitivity_consistent.md §7):

    P5_sh = success AND NOT uses_short_hash_token(locator_raw)

A token matches as a whole token in locator_raw, bounded by a character outside [A-Za-z0-9_-];
the plain substring count of sensitivity_consistent.md §7 is reported as a control.

Comparisons (P5 and P5_sh): B_full→NV and B_full→NVC (960 pairs, F0–F3), B_full×F1→NV×F3 and
B_full×F1→NVC×F3 (240 pairs, the COP cells); overall and by D1b stratum. Statistics as in
sensitivity_consistent.md: McNemar (uncorrected χ² + exact p), OR = b/c with exact conditional
CI, page-clustered percentile bootstrap (10,000, seed 42).

Outputs: experiments/results/revision1/short_hash_sensitivity.{md,json}
"""
from __future__ import annotations

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import re
import json
import pathlib

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from load import load_dataframe                                      # noqa: E402
from revision1_diagnostics import (                                  # noqa: E402
    REPO, OUT_DIR, KEY, PRED_COLS, protected_state, jsonable, md_table, mcnemar, page_bootstrap, pct_ci,
)
from revision1_sensitivity_consistent import (                       # noqa: E402
    DOM_ENCODINGS, NVC, NV, BF, assemble_nvc, short_hash_tokens, target_strata, pred_rows, pred_headers,
    delta_stat,
)

PREDS = {"P5": "original five-condition predicate (success field)",
         "P5_sh": "P5 AND the locator contains no unflagged short-middle CSS-module class token"}


def token_pattern(tokens):
    if not tokens:
        return None
    alt = "|".join(re.escape(t) for t in sorted(tokens, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9_-])(?:{alt})(?![A-Za-z0-9_-])")


def block(frame):
    """P5 / P5_sh on one paired frame (_bf first, _nv second); bootstrap over its pages."""
    order = list(frame["page"].unique())
    out = {}
    for name in PREDS:
        res = mcnemar(frame[f"{name}_bf"], frame[f"{name}_nv"])
        g = frame.groupby("page", sort=False)
        arrays = {"bf": g[f"{name}_bf"].sum().reindex(order).to_numpy(dtype=float),
                  "nv": g[f"{name}_nv"].sum().reindex(order).to_numpy(dtype=float),
                  "n":  g[f"{name}_bf"].count().reindex(order).to_numpy(dtype=float)}
        res["boot_ci_lo_pp"], res["boot_ci_hi_pp"] = pct_ci(page_bootstrap(order, arrays, delta_stat))
        res["n_pages"] = len(order)
        res["definition"] = PREDS[name]
        out[name] = res
    return out


def main():
    before = protected_state()
    df = load_dataframe(REPO)
    nvc, nv, _, _ = assemble_nvc(df)
    df2 = pd.concat([df, nvc.assign(semantic_density=np.nan)], ignore_index=True)

    short = short_hash_tokens()
    by_page = {}
    for pg, t in short:
        by_page.setdefault(pg, []).append(t)
    pats = {pg: token_pattern(v) for pg, v in by_page.items()}

    def hits(page, loc):
        p = pats.get(page)
        return sorted(set(p.findall(str(loc or "")))) if p else []

    rec = df2[df2.bundle.isin([BF, NV, NVC]) & df2.encoding.isin(DOM_ENCODINGS)].copy()
    assert len(rec) == 2880
    rec["short_hits"] = [hits(p, l) for p, l in zip(rec.page, rec.locator_raw)]
    rec["uses_short"] = rec.short_hits.str.len() > 0
    rec["uses_short_substring"] = [any(t in str(l or "") for t in by_page.get(p, []))
                                   for p, l in zip(rec.page, rec.locator_raw)]
    rec["success"] = rec.success.astype(bool)
    rec["P5_sh"] = rec.success & ~rec.uses_short
    flag = rec.set_index(["bundle"] + KEY)[["uses_short", "P5_sh"]]

    # Per-bundle counts (control: substring counts = sensitivity_consistent.md §7)
    per_bundle = []
    for b in (BF, NV, NVC):
        r = rec[rec.bundle == b]
        per_bundle.append({
            "bundle": b, "n": len(r),
            "locators_with_token_bounded": int(r.uses_short.sum()),
            "locators_with_token_substring": int(r.uses_short_substring.sum()),
            "P5_success": int(r.success.sum()),
            "P5_success_using_token": int((r.success & r.uses_short).sum()),
            "P5_sh_success": int(r.P5_sh.sum()),
        })
    sub_ctrl = {BF: 43, NV: 48, NVC: 53}
    control_ok = all(d["locators_with_token_substring"] == sub_ctrl[d["bundle"]] for d in per_bundle)

    none_t, text_only = target_strata()
    no_attr = none_t | text_only

    def prep(pairs, first, second, enc_first=None, enc_second=None):
        def look(bundle, page, task, enc, rep, col):
            return bool(flag.loc[(bundle, page, task, enc, rep), col])
        e1 = pairs.encoding_bf if enc_first is None else [enc_first] * len(pairs)
        e2 = pairs.encoding_nv if enc_second is None else [enc_second] * len(pairs)
        pairs["P5_bf"] = pairs.success_bf.astype(bool)
        pairs["P5_nv"] = pairs.success_nv.astype(bool)
        pairs["P5_sh_bf"] = [look(first, p, t, e, r, "P5_sh")
                             for p, t, e, r in zip(pairs.page, pairs.task_id, e1, pairs.repetition)]
        pairs["P5_sh_nv"] = [look(second, p, t, e, r, "P5_sh")
                             for p, t, e, r in zip(pairs.page, pairs.task_id, e2, pairs.repetition)]
        pairs["no_attr"] = [(p, k) in no_attr for p, k in zip(pairs.page, pairs.task_id)]
        return pairs

    def full_pairs(second):
        a = df2[(df2.bundle == BF) & df2.encoding.isin(DOM_ENCODINGS)][KEY + PRED_COLS]
        b = df2[(df2.bundle == second) & df2.encoding.isin(DOM_ENCODINGS)][KEY + PRED_COLS]
        p = a.merge(b, on=KEY, suffixes=("_bf", "_nv"))
        p["encoding_bf"] = p["encoding_nv"] = p["encoding"]
        return prep(p, BF, second)

    def cop_pairs(second):
        k3 = ["page", "task_id", "repetition"]
        p = (df2[(df2.bundle == BF) & (df2.encoding == "F1")][k3 + PRED_COLS]
             .merge(df2[(df2.bundle == second) & (df2.encoding == "F3")][k3 + PRED_COLS], on=k3,
                    suffixes=("_bf", "_nv")))
        return prep(p, BF, second, "F1", "F3")

    comparisons = {
        "B_full → B_noVolatile (960, F0–F3)": full_pairs(NV),
        "B_full → NVC (960, F0–F3)": full_pairs(NVC),
        "B_full×F1 → B_noVolatile×F3 (240, published COP)": cop_pairs(NV),
        "B_full×F1 → NVC×F3 (240)": cop_pairs(NVC),
    }
    assert [len(v) for v in comparisons.values()] == [960, 960, 240, 240]
    groups = {"all": lambda f: np.ones(len(f), dtype=bool),
              "has_attribute_signal": lambda f: ~f["no_attr"],
              "no_attribute_signal (NONE + text-only)": lambda f: f["no_attr"]}
    results = {c: {g: block(fr[sel(fr)]) for g, sel in groups.items()} for c, fr in comparisons.items()}

    # Control: P5 rows reproduce sensitivity_consistent.json
    sc = json.loads((OUT_DIR / "sensitivity_consistent.json").read_text(encoding="utf-8"))
    ctrl = {
        "B_full → B_noVolatile (960, F0–F3)": sc["main_960_reference_NV"]["all"]["P5"],
        "B_full → NVC (960, F0–F3)": sc["main_960"]["all"]["P5"],
        "B_full×F1 → B_noVolatile×F3 (240, published COP)": sc["cop_240_reference_NV"]["all"]["P5"],
        "B_full×F1 → NVC×F3 (240)": sc["cop_240"]["all"]["P5"],
    }
    p5_control = {c: all(results[c]["all"]["P5"][k] == ctrl[c][k]
                         for k in ("b_second_only", "c_first_only", "n11_both", "n00_neither"))
                  and abs(results[c]["all"]["P5"]["boot_ci_lo_pp"] - ctrl[c]["boot_ci_lo_pp"]) < 1e-9
                  and abs(results[c]["all"]["P5"]["boot_ci_hi_pp"] - ctrl[c]["boot_ci_hi_pp"]) < 1e-9
                  for c in comparisons}

    # Per page: locators with a token / P5 successes lost, per bundle
    pages = sorted(by_page)
    per_page = []
    for pg in pages:
        row = {"page": pg, "distinct_tokens": len(by_page[pg])}
        for b in (BF, NV, NVC):
            r = rec[(rec.bundle == b) & (rec.page == pg)]
            row[f"{b}_locators"] = int(r.uses_short.sum())
            row[f"{b}_success_lost"] = int((r.success & r.uses_short).sum())
        per_page.append(row)

    affected = rec[rec.success & rec.uses_short].sort_values(["bundle"] + KEY)
    affected_rows = [{"bundle": r.bundle, "page": r.page, "task_id": r.task_id, "encoding": r.encoding,
                      "tokens": r.short_hits, "locator": r.locator_raw} for r in affected.itertuples()]

    # Report
    L = ["# Revision 1 — short-hash sensitivity (analysis only)", "",
         "Facts only. The success predicate is not changed; this is a post-hoc re-scoring. "
         "`P5_sh` = P5 AND the generated locator contains none of the class tokens of the form "
         "`Name_x__hash` with a 1–4 character middle segment (`^[A-Za-z]+_[A-Za-z0-9]{1,4}__[A-Za-z0-9]+$`) "
         f"that the predicate does not flag: {len(short)} distinct (page, token) pairs on {len(pages)} pages "
         "(DOM census, `observations/token_census.json`; same set as `sensitivity_consistent.md` §7). "
         "A token counts when it appears in `locator_raw` bounded by characters outside `[A-Za-z0-9_-]`.", "",
         "NVC = the 960-event B_noVolatileConsistent set of `sensitivity_consistent.md` (240 new_run + 720 "
         "original B_noVolatile records of byte-identical cells). Statistics: McNemar uncorrected χ² and exact p; "
         "OR = b/c with exact conditional 95% CI; page-clustered percentile bootstrap of Δ "
         "(10,000 replicates, seed 42).", "",
         "Controls: plain-substring locator counts equal §7 of `sensitivity_consistent.md` "
         f"(B_full 43, NV 48, NVC 53): {'yes' if control_ok else 'NO'}; P5 rows below equal "
         f"`sensitivity_consistent.json` (2×2 and bootstrap CI): "
         f"{'yes' if all(p5_control.values()) else 'NO ' + str(p5_control)}.", "",
         "## 1. Locators per bundle (F0–F3, 960 events each)", ""]
    L += md_table(["bundle", "locators with token (bounded)", "locators with token (substring)",
                   "P5 successes", "of which use a token", "P5_sh successes"],
                  [[d["bundle"], d["locators_with_token_bounded"], d["locators_with_token_substring"],
                    d["P5_success"], d["P5_success_using_token"], d["P5_sh_success"]] for d in per_bundle])
    n = 2
    for c in comparisons:
        first, second = c.split(" → ")[0], c.split(" → ")[1].split(" (")[0]
        L += ["", f"## {n}. {c}", ""]
        rows = []
        for g in groups:
            rows += pred_rows(results[c][g], first, second, label=f"{g} (n={results[c][g]['P5']['n']})")
        L += md_table(pred_headers(first, second, label="stratum"), rows)
        n += 1
    L += ["", f"## {n}. Per page (pages with at least one such token)", ""]
    L += md_table(["page", "distinct tokens"] + [f"{b} locators / P5 lost" for b in (BF, NV, NVC)],
                  [[r["page"], r["distinct_tokens"]] + [f"{r[f'{b}_locators']} / {r[f'{b}_success_lost']}"
                                                         for b in (BF, NV, NVC)] for r in per_page])
    L += ["", f"## {n + 1}. P5 successes that become failures under P5_sh ({len(affected_rows)})", ""]
    L += md_table(["bundle", "page", "task", "enc", "token(s)", "locator"],
                  [[a["bundle"], a["page"], a["task_id"], a["encoding"], ", ".join(f"`{t}`" for t in a["tokens"]),
                    f"`{str(a['locator']).replace('|', '¦')}`"] for a in affected_rows])

    after = protected_state()
    assert before == after, "protected files changed during the run"
    L += ["", f"Protected files (FINDINGS.md, 24 matrix, 71 axisc, 24 truth) unchanged: {len(before)} SHA-256 equal.", ""]

    (OUT_DIR / "short_hash_sensitivity.md").write_text("\n".join(L), encoding="utf-8", newline="\n")
    (OUT_DIR / "short_hash_sensitivity.json").write_text(json.dumps(jsonable({
        "tokens": short, "controls": {"substring_counts_equal_section7": control_ok, "p5_equal_sensitivity": p5_control},
        "per_bundle": per_bundle, "comparisons": results, "per_page": per_page, "affected_successes": affected_rows,
    }), indent=2) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
